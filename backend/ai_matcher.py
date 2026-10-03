"""
AI Matcher for GST Reconciliation
Uses Google Gemini API via `google-genai` library with batching, SQLite caching,
retry logic, rate-limit pauses, strict JSON parsing, and graceful offline heuristic fallback.
"""

import os
import json
import re
import time
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

try:
    from .db import compute_cache_key, get_cached_match, set_cached_match
except ImportError:
    from db import compute_cache_key, get_cached_match, set_cached_match


# Configure logger
logger = logging.getLogger("gst_reconcile.ai_matcher")
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "match_prompt.txt")


def load_system_prompt() -> str:
    """Loads the system matching prompt instructions from prompts/match_prompt.txt."""
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "You are an Indian GST reconciliation auditor. Output strict JSON array only."


def get_gemini_client():
    """
    Initializes and returns the Gemini client if a valid API key is present.
    Returns None if the key is missing or placeholder.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key in ("your_gemini_api_key_here", "TODO", "YOUR_API_KEY"):
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize google-genai client: {e}")
        return None


def get_model_name() -> str:
    """Returns the Gemini model name configured in .env, defaulting to gemini-2.5-flash."""
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"


def offline_heuristic_evaluate(query_row: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Intelligent heuristic fallback used when Gemini API key is not yet set or API fails.
    Simulates expert auditor matching using rapidfuzz and discrepancy rules,
    guaranteeing that the system never crashes and can be tested without an API key.
    """
    row_id = query_row.get("row_id") or query_row.get("id")
    if not candidates:
        return {
            "row_id": row_id,
            "best_candidate_id": None,
            "same_invoice": False,
            "confidence": 95,
            "mismatch_type": "MISSING_IN_2B",
            "reason": "No corresponding invoice found in GSTR-2B portal records."
        }

    best_candidate = candidates[0]
    cand_id = best_candidate.get("id")
    score = best_candidate.get("similarity_score", 0)

    q_amt = float(query_row.get("total_amount", 0.0) or 0.0)
    c_amt = float(best_candidate.get("total_amount", 0.0) or 0.0)
    amt_diff = abs(q_amt - c_amt)

    q_tax = float(query_row.get("total_tax", 0.0) or 0.0)
    c_tax = float(best_candidate.get("total_tax", 0.0) or 0.0)
    tax_diff = abs(q_tax - c_tax)

    q_date = str(query_row.get("invoice_date", ""))
    c_date = str(best_candidate.get("invoice_date", ""))

    q_inv = str(query_row.get("normalized_invoice_number", ""))
    c_inv = str(best_candidate.get("normalized_invoice_number", ""))

    q_gstin = str(query_row.get("gstin", "")).upper()
    c_gstin = str(best_candidate.get("gstin", "")).upper()

    same_gstin = (q_gstin == c_gstin)
    same_inv = (q_inv == c_inv or q_inv in c_inv or c_inv in q_inv)

    # Classification rules
    if same_gstin and same_inv and amt_diff < 0.01 and tax_diff < 0.01:
        # Same invoice, possibly name variant
        return {
            "row_id": row_id,
            "best_candidate_id": cand_id,
            "same_invoice": True,
            "confidence": 92,
            "mismatch_type": "NAME_DIFF",
            "reason": f"GSTIN and invoice #{q_inv} match. Minor supplier legal name variation."
        }
    elif same_gstin and same_inv and amt_diff >= 0.01:
        return {
            "row_id": row_id,
            "best_candidate_id": cand_id,
            "same_invoice": True,
            "confidence": 88,
            "mismatch_type": "AMOUNT_DIFF",
            "reason": f"Invoice #{q_inv} matches, but amount differs: PR ₹{q_amt:.2f} vs 2B ₹{c_amt:.2f} (diff ₹{amt_diff:.2f})."
        }
    elif same_gstin and same_inv and amt_diff < 0.01 and tax_diff >= 0.01:
        return {
            "row_id": row_id,
            "best_candidate_id": cand_id,
            "same_invoice": True,
            "confidence": 85,
            "mismatch_type": "RATE_MISMATCH",
            "reason": f"Invoice #{q_inv} matches on value, but GST tax amount differs (PR ₹{q_tax:.2f} vs 2B ₹{c_tax:.2f})."
        }
    elif same_gstin and (q_date[:7] != c_date[:7]) and (amt_diff < 0.01 or same_inv):
        return {
            "row_id": row_id,
            "best_candidate_id": cand_id,
            "same_invoice": True,
            "confidence": 82,
            "mismatch_type": "DATE_PERIOD",
            "reason": f"Same invoice #{q_inv}, but recorded in different calendar months ({q_date} vs {c_date})."
        }
    elif score >= 75 and same_gstin:
        return {
            "row_id": row_id,
            "best_candidate_id": cand_id,
            "same_invoice": True,
            "confidence": 75,  # <80 so flagged for NEEDS_REVIEW
            "mismatch_type": "NAME_DIFF",
            "reason": f"High candidate similarity ({score:.0f}%), manual audit recommended."
        }
    else:
        return {
            "row_id": row_id,
            "best_candidate_id": None,
            "same_invoice": False,
            "confidence": 60,
            "mismatch_type": "MISSING_IN_2B",
            "reason": "Discrepancy too high to confirm match automatically; missing in GSTR-2B."
        }


def extract_json_from_response(text: str) -> Optional[List[Dict[str, Any]]]:
    """Extracts and parses JSON array from model text response, tolerating markdown fences."""
    text = text.strip()
    # Remove markdown code fences if present
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find the outermost array brackets
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        text = text[start:end+1]

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warning(f"JSON decode failed on response: {e}")
    return None


def call_gemini_batch(batch_items: List[Dict[str, Any]], model_name: str, client) -> List[Dict[str, Any]]:
    """
    Calls Gemini API with retries, timeout, and rate-limit delay for a single batch (~10 items).
    Falls back to offline heuristic for any item that fails.
    """
    system_prompt = load_system_prompt()
    user_payload = []

    for item in batch_items:
        q = item["query"]
        candidates = item["candidates"]
        user_payload.append({
            "row_id": q.get("row_id") or q.get("id"),
            "query_row": {
                "gstin": q.get("gstin"),
                "supplier_name": q.get("clean_name", q.get("supplier_name")),
                "invoice_number": q.get("normalized_invoice_number", q.get("invoice_number")),
                "invoice_date": q.get("invoice_date"),
                "taxable_value": q.get("taxable_value"),
                "total_tax": q.get("total_tax"),
                "total_amount": q.get("total_amount")
            },
            "candidates": [
                {
                    "candidate_id": c.get("id"),
                    "gstin": c.get("gstin"),
                    "supplier_name": c.get("clean_name", c.get("supplier_name")),
                    "invoice_number": c.get("normalized_invoice_number", c.get("invoice_number")),
                    "invoice_date": c.get("invoice_date"),
                    "taxable_value": c.get("taxable_value"),
                    "total_tax": c.get("total_tax"),
                    "total_amount": c.get("total_amount"),
                    "similarity_score": c.get("similarity_score")
                }
                for c in candidates
            ]
        })

    prompt_text = f"{system_prompt}\n\nINPUT BATCH TO RECONCILE:\n{json.dumps(user_payload, indent=2)}"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling Gemini API (model: {model_name}, attempt {attempt+1}/{max_retries}, items: {len(batch_items)})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_text
            )
            if response and response.text:
                parsed = extract_json_from_response(response.text)
                if parsed:
                    # Map parsed list to batch items
                    results_map = {str(item.get("row_id")): item for item in parsed}
                    output_results = []
                    for b_item in batch_items:
                        r_id = str(b_item["query"].get("row_id") or b_item["query"].get("id"))
                        if r_id in results_map:
                            res = results_map[r_id]
                            # Validate fields
                            output_results.append({
                                "row_id": b_item["query"].get("row_id") or b_item["query"].get("id"),
                                "best_candidate_id": res.get("best_candidate_id"),
                                "same_invoice": bool(res.get("same_invoice", False)),
                                "confidence": int(res.get("confidence", 50)),
                                "mismatch_type": res.get("mismatch_type", "NEEDS_REVIEW"),
                                "reason": str(res.get("reason", "AI audited reconciliation."))
                            })
                        else:
                            # Item omitted in AI output -> fallback
                            output_results.append(offline_heuristic_evaluate(b_item["query"], b_item["candidates"]))
                    # Sleep slightly to respect free tier rate limits
                    time.sleep(1.0)
                    return output_results
        except Exception as e:
            logger.warning(f"Gemini API attempt {attempt+1} failed: {e}")
            time.sleep(2.0 * (attempt + 1))  # Exponential backoff

    # If all retries fail, fall back to offline heuristic for the entire batch
    logger.warning("All Gemini retries failed. Falling back to rapidfuzz heuristic.")
    return [offline_heuristic_evaluate(b["query"], b["candidates"]) for b in batch_items]


def match_unmatched_batch(batch_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Main entry point for reconciling unmatched items.
    1. Checks SQLite cache for each item.
    2. Sends cache misses in batches of ~10 to Gemini (or offline fallback).
    3. Saves new results to SQLite cache.
    4. Returns complete list of decisions.
    """
    client = get_gemini_client()
    model_name = get_model_name()

    final_results = [None] * len(batch_requests)
    cache_miss_indices = []
    cache_miss_keys = []

    # Step 1: Check cache
    for idx, item in enumerate(batch_requests):
        cache_key = compute_cache_key(item["query"], item["candidates"])
        cached = get_cached_match(cache_key)
        if cached:
            # Attach row_id
            cached["row_id"] = item["query"].get("row_id") or item["query"].get("id")
            final_results[idx] = cached
        else:
            cache_miss_indices.append(idx)
            cache_miss_keys.append(cache_key)

    if not cache_miss_indices:
        return final_results

    # Step 2: Batch process cache misses (chunks of 10)
    chunk_size = 10
    for chunk_start in range(0, len(cache_miss_indices), chunk_size):
        chunk_indices = cache_miss_indices[chunk_start:chunk_start + chunk_size]
        chunk_items = [batch_requests[i] for i in chunk_indices]
        chunk_keys = [cache_miss_keys[chunk_start + i] for i in range(len(chunk_indices))]

        if client:
            chunk_results = call_gemini_batch(chunk_items, model_name, client)
        else:
            # No API key provided: use offline heuristic
            chunk_results = [offline_heuristic_evaluate(item["query"], item["candidates"]) for item in chunk_items]

        # Step 3: Store in cache and populate final_results
        for orig_idx, c_key, res in zip(chunk_indices, chunk_keys, chunk_results):
            final_results[orig_idx] = res
            set_cached_match(c_key, res, model_name=model_name if client else "heuristic-fallback")

    return final_results
