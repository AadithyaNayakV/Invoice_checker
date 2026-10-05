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
    Normalizes invoice numbers by extracting only the LAST numeric component:
    - INV/24-25/0043 -> 43
    - 0043 -> 43
    - 43 -> 43
    Does not join the financial-year digits.
    """
    if pd.isna(inv) or inv is None:
        return ""
    s = str(inv).strip()
    if not s:
        return ""
    digits = re.findall(r"\d+", s)
    if digits:
        return str(int(digits[-1]))
    return s.upper()



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
def extract_month_period(date_str: Any) -> Optional[str]:
    """Extracts YYYY-MM period from date string for tax period comparison."""
    if not date_str:
        return None
    s = str(date_str).strip()
    m = re.search(r"\b\d{1,2}[\/\-](\d{1,2})[\/\-](\d{4})\b", s)
    if m:
        return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    m2 = re.search(r"\b(\d{4})[\/\-](\d{1,2})[\/\-]\d{1,2}\b", s)
    if m2:
        return f"{int(m2.group(1)):04d}-{int(m2.group(2)):02d}"
    return None


def find_top_candidates(pr_row: Dict[str, Any], gstr2b_df: pd.DataFrame, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Shortlists up to top_k candidate rows from GSTR-2B:
    - Only sends rows to AI if GSTIN matches and candidate has similar invoice number or amount.
    - Never pairs different invoice numbers just because dates are in different months.
    - If no candidate qualifies, returns empty list.
    """
    gstin = pr_row["gstin"]
    pr_inv = pr_row["normalized_invoice_number"]
    pr_amt = pr_row["total_amount"]
    pr_name = pr_row["clean_name"]

    # Must match GSTIN
    pool = gstr2b_df[gstr2b_df["gstin"] == gstin]
    if pool.empty:
        return []

    scored_candidates = []
    for _, cand in pool.iterrows():
        c_inv = cand["normalized_invoice_number"]
        c_amt = cand["total_amount"]
        c_name = cand["clean_name"]

        # Calculate invoice similarity
        inv_score = fuzz.ratio(pr_inv, c_inv)
        is_inv_similar = (inv_score >= 60) or (pr_inv and c_inv and (pr_inv in c_inv or c_inv in pr_inv))

        # Amount proximity
        amt_diff_pct = abs(pr_amt - c_amt) / max(pr_amt, 1.0)
        is_amt_similar = (amt_diff_pct <= 0.10)

        # Disallow pairing completely different invoice numbers unless amount is similar
        if not (is_inv_similar or is_amt_similar):
            continue

        name_score = fuzz.token_sort_ratio(pr_name, c_name)
        amt_proximity = max(0, 100 - (amt_diff_pct * 100))
        composite_score = (0.50 * inv_score) + (0.30 * name_score) + (0.20 * amt_proximity)

        cand_dict = cand.to_dict()
        cand_dict["similarity_score"] = round(composite_score, 1)
        scored_candidates.append(cand_dict)

    scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored_candidates[:top_k]


def reconcile_dataframes(pr_df: pd.DataFrame, gstr2b_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Main GST reconciliation pipeline:
    1. Preprocesses and standardizes PR and GSTR-2B dataframes.
    2. Matches on GSTIN + normalized invoice number first:
       - Enforces one-to-one matching: each GSTR-2B row can be matched to only ONE purchase register row.
       - If a second book row matches the same 2B row, marks DUPLICATE_IN_BOOKS.
       - If same GSTIN and invoice but different amount or rate, marks AMOUNT_DIFF or RATE_MISMATCH.
       - If same invoice but different month, marks WRONG_PERIOD.
    3. For PR rows without exact GSTIN+invoice in 2B:
       - Only sends to AI if GSTIN matches and candidate has similar invoice number or amount.
       - If no candidate, marks MISSING_IN_2B.
    4. Reports rows that are in GSTR-2B but not in the books as EXTRA_IN_2B (0 ITC at risk).
    5. Calculates ITC at risk: sum of total tax for problem rows.
    """
    start_time = time.time()
    logger.info("Starting GST Reconciliation pipeline...")

    # Stage 1: Clean and standardize
    t0 = time.time()
    pr_clean = standardize_columns(pr_df, source_type="PR")
    gstr2b_clean = standardize_columns(gstr2b_df, source_type="2B")
    logger.info(f"Stage 1 (Data Preprocessing) completed in {time.time() - t0:.3f}s. PR: {len(pr_clean)}, 2B: {len(gstr2b_clean)} rows.")

    # Stage 2: 1-to-1 match on GSTIN + normalized invoice number first
    t0 = time.time()
    matched_2b_ids = set()
    b2_by_gstin_inv = {}
    for _, b2_row in gstr2b_clean.iterrows():
        key = (b2_row["gstin"], b2_row["normalized_invoice_number"])
        b2_by_gstin_inv.setdefault(key, []).append(b2_row.to_dict())

    results = []
    unmatched_pr = []

    for _, pr_row in pr_clean.iterrows():
        p_dict = pr_row.to_dict()
        key = (p_dict["gstin"], p_dict["normalized_invoice_number"])
        candidates = b2_by_gstin_inv.get(key, [])

        unmatched_cand = None
        already_matched_cand = None
        for c in candidates:
            if c["id"] not in matched_2b_ids:
                unmatched_cand = c
                break
            else:
                already_matched_cand = c

        if unmatched_cand:
            # One-to-one match
            c = unmatched_cand
            matched_2b_ids.add(c["id"])

            pr_tax = round_curr(p_dict["total_tax"])
            b2_tax = round_curr(c["total_tax"])
            pr_val = round_curr(p_dict["taxable_value"])
            b2_val = round_curr(c["taxable_value"])
            pr_amt = round_curr(p_dict["total_amount"])
            b2_amt = round_curr(c["total_amount"])
            pr_rate = float(p_dict["rate"])
            b2_rate = float(c["rate"])

            pr_period = extract_month_period(p_dict["invoice_date"])
            b2_period = extract_month_period(c["invoice_date"])

            # Hierarchy of discrepancy detection:
            # 1. Rate mismatch
            if abs(pr_rate - b2_rate) > 0.01:
                status = "MISMATCHED"
                mismatch_type = "RATE_MISMATCH"
                itc_risk = pr_tax
                reason = f"GST rate mismatch: {pr_rate:.0f}% in books vs {b2_rate:.0f}% in GSTR-2B."
                confidence = 100
            # 2. Amount difference (taxable value or total amount diff > 1.0)
            elif abs(pr_val - b2_val) > 1.0 or abs(pr_amt - b2_amt) > 1.0:
                status = "MISMATCHED"
                mismatch_type = "AMOUNT_DIFF"
                itc_risk = pr_tax
                reason = f"Amount difference: Taxable ₹{pr_val:,.2f} in books vs ₹{b2_val:,.2f} in GSTR-2B."
                confidence = 100
            # 3. Wrong period (different month)
            elif pr_period and b2_period and pr_period != b2_period:
                status = "MISMATCHED"
                mismatch_type = "WRONG_PERIOD"
                itc_risk = pr_tax
                reason = f"Invoice dated in different tax month: {p_dict['invoice_date']} in books vs {c['invoice_date']} in GSTR-2B."
                confidence = 100
            # 4. Supplier legal name difference
            elif p_dict["clean_name"] != c["clean_name"]:
                status = "MATCHED"
                mismatch_type = "NAME_DIFF"
                itc_risk = 0.0
                reason = "Minor supplier name spelling variation; valid match."
                confidence = 95
            else:
                status = "MATCHED"
                mismatch_type = "NONE"
                itc_risk = 0.0
                reason = "Exact match on GSTIN, normalized invoice number, and tax amount."
                confidence = 100

            results.append({
                "id": p_dict["id"],
                "pr_row_id": p_dict["id"],
                "candidate_2b_id": c["id"],
                "gstin": p_dict["gstin"],
                "supplier_name": p_dict["supplier_name"],
                "invoice_number": p_dict["invoice_number"],
                "invoice_date": p_dict["invoice_date"],
                "taxable_value": pr_val,
                "total_tax": pr_tax,
                "total_amount": pr_amt,
                "b2_invoice_number": c["invoice_number"],
                "b2_amount": b2_amt,
                "b2_tax": b2_tax,
                "b2_date": c["invoice_date"],
                "status": status,
                "mismatch_type": mismatch_type,
                "confidence": confidence,
                "itc_at_risk": itc_risk,
                "reason": reason
            })
        elif already_matched_cand:
            # Second book row matches the same 2B row -> DUPLICATE_IN_BOOKS
            c = already_matched_cand
            pr_tax = round_curr(p_dict["total_tax"])
            results.append({
                "id": p_dict["id"],
                "pr_row_id": p_dict["id"],
                "candidate_2b_id": c["id"],
                "gstin": p_dict["gstin"],
                "supplier_name": p_dict["supplier_name"],
                "invoice_number": p_dict["invoice_number"],
                "invoice_date": p_dict["invoice_date"],
                "taxable_value": round_curr(p_dict["taxable_value"]),
                "total_tax": pr_tax,
                "total_amount": round_curr(p_dict["total_amount"]),
                "b2_invoice_number": c["invoice_number"],
                "b2_amount": round_curr(c["total_amount"]),
                "b2_tax": round_curr(c["total_tax"]),
                "b2_date": c["invoice_date"],
                "status": "MISMATCHED",
                "mismatch_type": "DUPLICATE_IN_BOOKS",
                "confidence": 100,
                "itc_at_risk": pr_tax,
                "reason": "Duplicate invoice found in purchase register; GSTR-2B row already matched."
            })
        else:
            unmatched_pr.append(p_dict)

    logger.info(f"Stage 2 completed in {time.time() - t0:.3f}s. Remaining unmatched PR rows: {len(unmatched_pr)}")

    # Stage 3: Candidate retrieval for unmatched PR rows
    t0 = time.time()
    unmatched_2b = gstr2b_clean[~gstr2b_clean["id"].isin(matched_2b_ids)]

    batch_ai_payload = []
    unmatched_index_map = []

    for p_dict in unmatched_pr:
        candidates = find_top_candidates(p_dict, unmatched_2b, top_k=3)
        if not candidates:
            # Immediate MISSING_IN_2B without calling AI
            pr_tax = round_curr(p_dict["total_tax"])
            results.append({
                "id": p_dict["id"],
                "pr_row_id": p_dict["id"],
                "candidate_2b_id": None,
                "gstin": p_dict["gstin"],
                "supplier_name": p_dict["supplier_name"],
                "invoice_number": p_dict["invoice_number"],
                "invoice_date": p_dict["invoice_date"],
                "taxable_value": round_curr(p_dict["taxable_value"]),
                "total_tax": pr_tax,
                "total_amount": round_curr(p_dict["total_amount"]),
                "b2_invoice_number": "-",
                "b2_amount": 0.0,
                "b2_tax": 0.0,
                "b2_date": "-",
                "status": "MISMATCHED",
                "mismatch_type": "MISSING_IN_2B",
                "confidence": 95,
                "itc_at_risk": pr_tax,
                "reason": "Invoice missing in supplier GSTR-2B portal records. ITC cannot be claimed."
            })
        else:
            batch_ai_payload.append({
                "query": p_dict,
                "candidates": candidates
            })
            unmatched_index_map.append((p_dict, candidates))

    logger.info(f"Stage 3 completed in {time.time() - t0:.3f}s. {len(batch_ai_payload)} rows sent to AI matcher.")

    # Stage 4: Batch AI / Heuristic Reconciliation
    if batch_ai_payload:
        t0 = time.time()
        ai_decisions = match_unmatched_batch(batch_ai_payload)
        logger.info(f"Stage 4 (AI / Heuristic Reconciliation) finished in {time.time() - t0:.3f}s.")

        for (p_dict, candidates), decision in zip(unmatched_index_map, ai_decisions):
            conf = int(decision.get("confidence", 50))
            mismatch_type = decision.get("mismatch_type", "NEEDS_REVIEW")
            reason = decision.get("reason", "")
            cand_id = decision.get("best_candidate_id")

            cand_row = next((c for c in candidates if str(c.get("id")) == str(cand_id)), None) if cand_id else None
            if cand_row and cand_row["id"] not in matched_2b_ids:
                matched_2b_ids.add(cand_row["id"])

            pr_tax = round_curr(p_dict["total_tax"])
            b2_tax = round_curr(cand_row["total_tax"]) if cand_row else 0.0
            b2_amt = round_curr(cand_row["total_amount"]) if cand_row else 0.0
            b2_inv = cand_row["invoice_number"] if cand_row else "-"
            b2_date = cand_row["invoice_date"] if cand_row else "-"

            if conf < 80:
                status = "NEEDS_REVIEW"
                itc_risk = pr_tax
            elif mismatch_type == "NONE" and decision.get("same_invoice"):
                status = "MATCHED"
                itc_risk = 0.0
            elif mismatch_type == "NAME_DIFF":
                status = "MATCHED"
                itc_risk = 0.0
            else:
                status = "MISMATCHED"
                itc_risk = pr_tax

            results.append({
                "id": p_dict["id"],
                "pr_row_id": p_dict["id"],
                "candidate_2b_id": cand_id,
                "gstin": p_dict["gstin"],
                "supplier_name": p_dict["supplier_name"],
                "invoice_number": p_dict["invoice_number"],
                "invoice_date": p_dict["invoice_date"],
                "taxable_value": round_curr(p_dict["taxable_value"]),
                "total_tax": pr_tax,
                "total_amount": round_curr(p_dict["total_amount"]),
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

    # Stage 5: Report rows that are in GSTR-2B but not in the books as EXTRA_IN_2B
    for _, b2_row in gstr2b_clean.iterrows():
        if b2_row["id"] not in matched_2b_ids:
            results.append({
                "id": f"2B_{b2_row['id']}",
                "pr_row_id": None,
                "candidate_2b_id": b2_row["id"],
                "gstin": b2_row["gstin"],
                "supplier_name": b2_row["supplier_name"],
                "invoice_number": "-",
                "invoice_date": "-",
                "taxable_value": 0.0,
                "total_tax": 0.0,
                "total_amount": 0.0,
                "b2_invoice_number": b2_row["invoice_number"],
                "b2_amount": round_curr(b2_row["total_amount"]),
                "b2_tax": round_curr(b2_row["total_tax"]),
                "b2_date": b2_row["invoice_date"],
                "status": "MISMATCHED",
                "mismatch_type": "EXTRA_IN_2B",
                "confidence": 100,
                "itc_at_risk": 0.0,
                "reason": "Invoice present in GSTR-2B portal but missing in purchase register (please check)."
            })

    # Stage 6: Financial calculations
    t0 = time.time()
    summary = calculate_financial_summary(results)
    total_elapsed = time.time() - start_time
    logger.info(f"Stage 6 (Summary & Totals) finished in {time.time() - t0:.3f}s. Total pipeline time: {total_elapsed:.3f}s.")

    return {
        "summary": summary,
        "results": results,
        "elapsed_seconds": round(total_elapsed, 2)
    }


def calculate_financial_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates summary metrics:
    - total_itc_at_risk (₹): Python sum of total tax for MISSING_IN_2B, AMOUNT_DIFF, RATE_MISMATCH, DUPLICATE_IN_BOOKS, WRONG_PERIOD.
      Not for NAME_DIFF, invoice-format differences, or EXTRA_IN_2B.
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

        # Only sum ITC at risk for discrepancy problem types, never for EXTRA_IN_2B, NAME_DIFF, or format differences (NONE)
        if m_type in ("MISSING_IN_2B", "AMOUNT_DIFF", "RATE_MISMATCH", "DUPLICATE_IN_BOOKS", "WRONG_PERIOD", "NEEDS_REVIEW"):
            risk_val = Decimal(str(row.get("itc_at_risk", 0.0) or 0.0))
        else:
            risk_val = Decimal("0.00")

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
        "itc_by_supplier": supplier_list[:10]
    }
