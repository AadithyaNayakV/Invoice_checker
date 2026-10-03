"""
GST Reconciliation Engine
Performs multi-stage reconciliation between Purchase Register (PR) and GSTR-2B:
1. Vectorized preprocessing and cleaning (names, invoice numbers, tax values).
2. Vectorized exact matching (GSTIN + Normalized Invoice No + Total Amount).
3. Blocked rapidfuzz candidate retrieval for unmatched records.
4. Batch Gemini AI / Heuristic evaluation with SQLite caching.
5. Strict Python-based financial calculation of Input Tax Credit (ITC) at risk.
"""

import re
import time
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
from rapidfuzz import fuzz, process

try:
    from .ai_matcher import match_unmatched_batch
except ImportError:
    from ai_matcher import match_unmatched_batch


# Setup logger with timestamps
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gst_reconcile.engine")

# Legal entities and noise words in Indian business names
LEGAL_TERMS_REGEX = re.compile(
    r"\b(PVT\s+LTD|PRIVATE\s+LIMITED|PVT\s+LIMITED|PVT|LIMITED|LTD|LLP|INC|CORP|CO|ENTERPRISES|TRADERS|COMPANY)\b",
    re.IGNORECASE
)


def clean_supplier_name(name: Any) -> str:
    """
    Cleans supplier name for robust matching:
    1. Converts to string and uppercase.
    2. Strips common corporate suffixes (PVT LTD, PRIVATE LIMITED, etc.).
    3. Strips non-alphanumeric punctuation and excess spaces.
    """
    if pd.isna(name) or name is None:
        return ""
    text = str(name).upper().strip()
    text = LEGAL_TERMS_REGEX.sub("", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_invoice_number(inv: Any) -> str:
    """
    Normalizes invoice numbers across different ERP formats:
    - Strips prefixes like 'INV/', 'INV-', 'BILL/'
    - Removes slashes, dashes, spaces, special chars
    - Strips leading zeros from numeric components (e.g., 'INV/23-24/0045' -> '232445', '45' -> '45')
    """
    if pd.isna(inv) or inv is None:
        return ""
    raw = str(inv).strip().upper()
    # Remove common prefix tokens
    raw = re.sub(r"^(INV|BILL|TAX|EXP|INVOICE)[\/\-_:\s]*", "", raw)
    if not raw:
        return ""
    # Split by separators
    parts = [p for p in re.split(r"[\/\-_:\s\.]+", raw) if p]
    if not parts:
        return ""

    norm_parts = []
    for p in parts:
        if p.isdigit():
            norm_parts.append(p.lstrip("0") or "0")
        else:
            norm_parts.append(re.sub(r"^0+", "", p) or "0")
    return "".join(norm_parts)



def round_curr(val: Any) -> float:
    """Safely converts and rounds currency values to 2 decimal places."""
    try:
        if pd.isna(val) or val is None or val == "":
            return 0.0
        d = Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(d)
    except Exception:
        return 0.0


def standardize_columns(df: pd.DataFrame, source_type: str = "PR") -> pd.DataFrame:
    """
    Standardizes column names and validates expected fields.
    Maps various real-world invoice column names into unified keys.
    """
    df = df.copy()
    col_map = {}
    for col in df.columns:
        norm_c = re.sub(r"[_\s]+", "_", str(col).strip().lower())
        if norm_c in ["invoice_no", "inv_no", "invoice_num", "bill_no", "inv_num"]:
            col_map[col] = "invoice_number"
        elif norm_c in ["supplier_gstin", "gst_no", "gstin_uin", "gst_number"]:
            col_map[col] = "gstin"
        elif norm_c in ["supplier_name", "party_name", "vendor_name", "trade_name", "legal_name"]:
            col_map[col] = "supplier_name"
        elif norm_c in ["inv_date", "date", "bill_date"]:
            col_map[col] = "invoice_date"
        elif norm_c in ["taxable_amt", "taxable_value", "taxable"]:
            col_map[col] = "taxable_value"
        elif norm_c in ["total_tax_amount", "tax_amount", "tax"]:
            col_map[col] = "total_tax"
        elif norm_c in ["invoice_amount", "grand_total", "total_value", "invoice_value"]:
            col_map[col] = "total_amount"
        elif norm_c in ["gst_rate", "rate", "tax_rate"]:
            col_map[col] = "rate"

    df = df.rename(columns=col_map)

    # Ensure required columns exist with default empty/zero values
    defaults = {
        "invoice_number": "",
        "gstin": "",
        "supplier_name": "UNKNOWN",
        "invoice_date": "",
        "taxable_value": 0.0,
        "cgst": 0.0,
        "sgst": 0.0,
        "igst": 0.0,
        "total_tax": 0.0,
        "total_amount": 0.0,
        "rate": 18.0
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = default_val

    # Ensure id exists
    if "id" not in df.columns:
        df["id"] = [f"{source_type}_{i+1}" for i in range(len(df))]
    else:
        df["id"] = df["id"].astype(str)

    # Format numeric fields
    for money_col in ["taxable_value", "cgst", "sgst", "igst", "total_tax", "total_amount", "rate"]:
        df[money_col] = df[money_col].apply(round_curr)

    # If total_tax is 0 but component taxes exist, compute total_tax
    mask_calc_tax = (df["total_tax"] == 0.0) & ((df["cgst"] + df["sgst"] + df["igst"]) > 0.0)
    df.loc[mask_calc_tax, "total_tax"] = (df.loc[mask_calc_tax, "cgst"] +
                                          df.loc[mask_calc_tax, "sgst"] +
                                          df.loc[mask_calc_tax, "igst"]).apply(round_curr)

    # If total_amount is 0, compute from taxable_value + total_tax
    mask_calc_amt = (df["total_amount"] == 0.0) & (df["taxable_value"] > 0.0)
    df.loc[mask_calc_amt, "total_amount"] = (df.loc[mask_calc_amt, "taxable_value"] +
                                             df.loc[mask_calc_amt, "total_tax"]).apply(round_curr)

    # Clean text columns
    df["gstin"] = df["gstin"].astype(str).str.strip().str.upper()
    df["clean_name"] = df["supplier_name"].apply(clean_supplier_name)
    df["normalized_invoice_number"] = df["invoice_number"].apply(normalize_invoice_number)
    df["invoice_date"] = df["invoice_date"].astype(str).str.strip()

    return df


def find_top_candidates(pr_row: Dict[str, Any], gstr2b_df: pd.DataFrame, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Shortlists up to top_k candidate rows from GSTR-2B using blocking:
    - Blocking Rule 1: Same GSTIN (fast & accurate).
    - Blocking Rule 2: If none, same first 2 chars of GSTIN (same state) or first 3 chars of name.
    - Uses rapidfuzz to score candidates based on invoice number and supplier name similarity.
    """
    gstin = pr_row["gstin"]
    pr_inv = pr_row["normalized_invoice_number"]
    pr_name = pr_row["clean_name"]
    pr_amt = pr_row["total_amount"]

    # Block 1: Candidates with identical GSTIN
    pool = gstr2b_df[gstr2b_df["gstin"] == gstin]

    # Block 2: If no same GSTIN, look for matching state code or similar name start
    if pool.empty:
        state_code = gstin[:2] if len(gstin) >= 2 else ""
        name_prefix = pr_name[:3] if len(pr_name) >= 3 else ""
        pool = gstr2b_df[
            (gstr2b_df["gstin"].str.startswith(state_code)) |
            (gstr2b_df["clean_name"].str.startswith(name_prefix))
        ]

    if pool.empty:
        return []

    scored_candidates = []
    for _, cand in pool.iterrows():
        c_inv = cand["normalized_invoice_number"]
        c_name = cand["clean_name"]
        c_amt = cand["total_amount"]

        # Calculate similarity scores
        name_score = fuzz.token_sort_ratio(pr_name, c_name)
        inv_score = fuzz.ratio(pr_inv, c_inv)

        # Proximity score for amounts
        amt_diff_pct = abs(pr_amt - c_amt) / max(pr_amt, 1.0)
        amt_proximity = max(0, 100 - (amt_diff_pct * 100))

        # Combined weighted score
        composite_score = (0.50 * inv_score) + (0.30 * name_score) + (0.20 * amt_proximity)

        # Threshold to qualify as a reasonable candidate
        if composite_score > 35 or inv_score > 60 or (gstin == cand["gstin"] and amt_proximity > 70):
            cand_dict = cand.to_dict()
            cand_dict["similarity_score"] = round(composite_score, 1)
            scored_candidates.append(cand_dict)

    # Sort descending by composite score
    scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored_candidates[:top_k]


def reconcile_dataframes(pr_df: pd.DataFrame, gstr2b_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Main reconciliation pipeline:
    1. Preprocesses and normalizes PR and GSTR-2B dataframes.
    2. Vectorized exact match on (gstin + normalized_invoice_number + total_amount).
    3. Blocked rapidfuzz candidate retrieval for unmatched records.
    4. Batch Gemini AI / Heuristic evaluation with SQLite caching.
    5. Python calculations for ITC at risk and status breakdown.
    """
    start_time = time.time()
    logger.info("Starting GST Reconciliation pipeline...")

    # Stage 1: Clean and standardize
    t0 = time.time()
    pr_clean = standardize_columns(pr_df, source_type="PR")
    gstr2b_clean = standardize_columns(gstr2b_df, source_type="2B")
    logger.info(f"Stage 1 (Data Preprocessing) completed in {time.time() - t0:.3f}s. PR: {len(pr_clean)}, 2B: {len(gstr2b_clean)} rows.")

    # Stage 2: Vectorized Exact Match
    t0 = time.time()
    # Create exact match keys
    pr_clean["amount_key"] = pr_clean["total_amount"].apply(lambda x: f"{x:.2f}")
    gstr2b_clean["amount_key"] = gstr2b_clean["total_amount"].apply(lambda x: f"{x:.2f}")

    # Identify exact matches via merge
    merge_cols = ["gstin", "normalized_invoice_number", "amount_key"]
    # Drop duplicates on merge keys in 2B for 1-to-1 match
    gstr2b_dedup = gstr2b_clean.drop_duplicates(subset=merge_cols, keep="first")

    exact_matched = pr_clean.merge(
        gstr2b_dedup[merge_cols + ["id", "invoice_number", "total_amount", "total_tax", "invoice_date"]],
        on=merge_cols,
        how="inner",
        suffixes=("", "_2b")
    )

    matched_pr_ids = set(exact_matched["id"].tolist())
    matched_2b_ids = set(exact_matched["id_2b"].tolist())

    logger.info(f"Stage 2 (Vectorized Exact Match) found {len(matched_pr_ids)} exact matches in {time.time() - t0:.3f}s.")

    # Build output records for exact matches
    results = []
    for _, row in exact_matched.iterrows():
        results.append({
            "id": row["id"],
            "pr_row_id": row["id"],
            "candidate_2b_id": row["id_2b"],
            "gstin": row["gstin"],
            "supplier_name": row["supplier_name"],
            "invoice_number": row["invoice_number"],
            "invoice_date": row["invoice_date"],
            "taxable_value": row["taxable_value"],
            "total_tax": row["total_tax"],
            "total_amount": row["total_amount"],
            "b2_invoice_number": row["invoice_number_2b"],
            "b2_amount": row["total_amount_2b"],
            "b2_tax": row["total_tax_2b"],
            "b2_date": row["invoice_date_2b"],
            "status": "MATCHED",
            "mismatch_type": "NONE",
            "confidence": 100,
            "itc_at_risk": 0.0,
            "reason": "Exact match on GSTIN, normalized invoice number, and total amount."
        })

    # Stage 3: Candidate retrieval for unmatched PR rows
    t0 = time.time()
    unmatched_pr = pr_clean[~pr_clean["id"].isin(matched_pr_ids)]
    unmatched_2b = gstr2b_clean[~gstr2b_clean["id"].isin(matched_2b_ids)]

    logger.info(f"Stage 3: Shortlisting candidates for {len(unmatched_pr)} unmatched PR rows against {len(unmatched_2b)} 2B rows...")

    batch_ai_payload = []
    unmatched_index_map = []  # Maps payload index back to PR row

    for _, pr_row in unmatched_pr.iterrows():
        candidates = find_top_candidates(pr_row.to_dict(), unmatched_2b, top_k=3)
        if not candidates:
            # Immediate MISSING_IN_2B without calling AI
            results.append({
                "id": pr_row["id"],
                "pr_row_id": pr_row["id"],
                "candidate_2b_id": None,
                "gstin": pr_row["gstin"],
                "supplier_name": pr_row["supplier_name"],
                "invoice_number": pr_row["invoice_number"],
                "invoice_date": pr_row["invoice_date"],
                "taxable_value": pr_row["taxable_value"],
                "total_tax": pr_row["total_tax"],
                "total_amount": pr_row["total_amount"],
                "b2_invoice_number": "-",
                "b2_amount": 0.0,
                "b2_tax": 0.0,
                "b2_date": "-",
                "status": "MISMATCHED",
                "mismatch_type": "MISSING_IN_2B",
                "confidence": 95,
                "itc_at_risk": round_curr(pr_row["total_tax"]),
                "reason": "Invoice missing in supplier GSTR-2B portal records. ITC cannot be claimed."
            })
        else:
            batch_ai_payload.append({
                "query": pr_row.to_dict(),
                "candidates": candidates
            })
            unmatched_index_map.append((pr_row.to_dict(), candidates))

    logger.info(f"Stage 3 completed in {time.time() - t0:.3f}s. {len(batch_ai_payload)} rows sent to AI matcher.")

    # Stage 4: Batch AI Reconciliation
    if batch_ai_payload:
        t0 = time.time()
        ai_decisions = match_unmatched_batch(batch_ai_payload)
        logger.info(f"Stage 4 (AI / Heuristic Reconciliation) finished in {time.time() - t0:.3f}s.")

        # Process AI decisions and perform strict Python financial calculations
        for (pr_row_dict, candidates), decision in zip(unmatched_index_map, ai_decisions):
            conf = int(decision.get("confidence", 50))
            mismatch_type = decision.get("mismatch_type", "NEEDS_REVIEW")
            reason = decision.get("reason", "")
            cand_id = decision.get("best_candidate_id")

            # Find matching candidate row if any
            cand_row = next((c for c in candidates if str(c.get("id")) == str(cand_id)), None) if cand_id else None

            pr_tax = round_curr(pr_row_dict["total_tax"])
            b2_tax = round_curr(cand_row["total_tax"]) if cand_row else 0.0
            b2_amt = round_curr(cand_row["total_amount"]) if cand_row else 0.0
            b2_inv = cand_row["invoice_number"] if cand_row else "-"
            b2_date = cand_row["invoice_date"] if cand_row else "-"

            # Rule 8: If confidence is below 80, status = "NEEDS_REVIEW"
            if conf < 80:
                status = "NEEDS_REVIEW"
                itc_risk = pr_tax  # Until reviewed, credit is at risk
            elif mismatch_type == "NONE" and decision.get("same_invoice"):
                status = "MATCHED"
                itc_risk = 0.0
            else:
                status = "MISMATCHED"
                if mismatch_type == "MISSING_IN_2B":
                    itc_risk = pr_tax
                elif mismatch_type in ("RATE_MISMATCH", "AMOUNT_DIFF"):
                    # Discrepancy amount in tax
                    itc_risk = round_curr(max(0.0, pr_tax - b2_tax)) if b2_tax > 0 else pr_tax
                elif mismatch_type == "DATE_PERIOD":
                    # Timing difference; tax is delayed or blocked for current period
                    itc_risk = pr_tax
                else:
                    itc_risk = 0.0 if mismatch_type == "NAME_DIFF" else pr_tax

            results.append({
                "id": pr_row_dict["id"],
                "pr_row_id": pr_row_dict["id"],
                "candidate_2b_id": cand_id,
                "gstin": pr_row_dict["gstin"],
                "supplier_name": pr_row_dict["supplier_name"],
                "invoice_number": pr_row_dict["invoice_number"],
                "invoice_date": pr_row_dict["invoice_date"],
                "taxable_value": pr_row_dict["taxable_value"],
                "total_tax": pr_tax,
                "total_amount": round_curr(pr_row_dict["total_amount"]),
                "b2_invoice_number": b2_inv,
                "b2_amount": b2_amt,
                "b2_tax": b2_tax,
                "b2_date": b2_date,
                "status": status,
                "mismatch_type": mismatch_type,
                "confidence": conf,
                "itc_at_risk": itc_risk,
                "reason": reason
            })

    # Stage 5: Financial calculations (using Python Decimal / rounding, NEVER AI)
    t0 = time.time()
    summary = calculate_financial_summary(results)
    total_elapsed = time.time() - start_time
    logger.info(f"Stage 5 (Summary & Totals) finished in {time.time() - t0:.3f}s. Total pipeline time: {total_elapsed:.3f}s.")

    return {
        "summary": summary,
        "results": results,
        "elapsed_seconds": round(total_elapsed, 2)
    }


def calculate_financial_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates summary metrics:
    - total_itc_at_risk (₹): sum of tax of all problem rows
    - total_records
    - counts by status: MATCHED, MISMATCHED, NEEDS_REVIEW
    - counts by mismatch_type
    - itc_at_risk_by_supplier: sorted list of top suppliers with highest ITC at risk
    """
    total_records = len(results)
    total_itc_risk = Decimal("0.00")
    status_counts = {"MATCHED": 0, "MISMATCHED": 0, "NEEDS_REVIEW": 0}
    type_counts = {}
    supplier_risk = {}

    for row in results:
        status = row.get("status", "NEEDS_REVIEW")
        status_counts[status] = status_counts.get(status, 0) + 1

        m_type = row.get("mismatch_type", "UNKNOWN")
        type_counts[m_type] = type_counts.get(m_type, 0) + 1

        risk_val = Decimal(str(row.get("itc_at_risk", 0.0) or 0.0))
        total_itc_risk += risk_val

        supplier = row.get("supplier_name", "UNKNOWN")
        if risk_val > 0:
            if supplier not in supplier_risk:
                supplier_risk[supplier] = {
                    "supplier_name": supplier,
                    "gstin": row.get("gstin", ""),
                    "itc_at_risk": Decimal("0.00"),
                    "invoice_count": 0
                }
            supplier_risk[supplier]["itc_at_risk"] += risk_val
            supplier_risk[supplier]["invoice_count"] += 1

    # Convert supplier risks to list sorted by highest risk
    supplier_list = []
    for s_name, data in supplier_risk.items():
        supplier_list.append({
            "supplier_name": s_name,
            "gstin": data["gstin"],
            "itc_at_risk": float(data["itc_at_risk"].quantize(Decimal("0.01"))),
            "invoice_count": data["invoice_count"]
        })
    supplier_list.sort(key=lambda x: x["itc_at_risk"], reverse=True)

    return {
        "total_records": total_records,
        "total_itc_at_risk": float(total_itc_risk.quantize(Decimal("0.01"))),
        "status_counts": status_counts,
        "mismatch_counts": type_counts,
        "itc_by_supplier": supplier_list[:10]  # Top 10 for bar chart
    }
