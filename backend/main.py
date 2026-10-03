"""
FastAPI Server for GST Reconciliation Tool
Exposes REST endpoints for:
- Uploading and reconciling PR vs GSTR-2B CSVs
- One-click loading of built-in sample datasets
- Human review queue approvals/rejections with live recalculations
- CSV export of audit reconciliation results
- Health and model status checks
"""

import os
import io
import csv
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, StreamingResponse
import pandas as pd

try:
    from .reconcile import reconcile_dataframes, calculate_financial_summary
    from .ai_matcher import get_gemini_client, get_model_name
    from .pdf_parser import parse_pdf_to_dataframe
except ImportError:
    from reconcile import reconcile_dataframes, calculate_financial_summary
    from ai_matcher import get_gemini_client, get_model_name
    from pdf_parser import parse_pdf_to_dataframe


logger = logging.getLogger("gst_reconcile.api")


def load_file_data(filename: str, content: bytes, source_type: str = "PR") -> pd.DataFrame:
    """Parses uploaded file content as PDF or CSV into a standardized DataFrame."""
    fname = (filename or "").lower()
    if fname.endswith(".pdf"):
        logger.info(f"Parsing uploaded {source_type} PDF: {filename}")
        return parse_pdf_to_dataframe(content, source_type=source_type)
    else:
        logger.info(f"Parsing uploaded {source_type} CSV: {filename}")
        return pd.read_csv(io.BytesIO(content))


app = FastAPI(
    title="GST Reconciliation Tool API",
    description="Automated GST Purchase Register vs GSTR-2B discrepancy detection engine.",
    version="1.0.0"
)

# Enable CORS for React frontend (Vite default port 5173 and standard web ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# In-memory storage for the latest reconciliation session
latest_session = {
    "summary": None,
    "results": []
}


@app.get("/api/health")
def health_check():
    """Health check endpoint showing model configuration and client status."""
    client = get_gemini_client()
    return {
        "status": "healthy",
        "gemini_model": get_model_name(),
        "gemini_connected": client is not None,
        "mode": "Gemini 2.5 Flash API" if client is not None else "Offline Heuristic Fallback (API Key Pending)"
    }


@app.post("/api/reconcile")
async def reconcile_files(
    pr_file: UploadFile = File(..., description="Purchase Register CSV or PDF"),
    gstr2b_file: UploadFile = File(..., description="GSTR-2B CSV or PDF")
):
    """
    Uploads two files (Purchase Register and GSTR-2B, in CSV or PDF format),
    converts PDFs internally as required,
    runs the automated reconciliation pipeline, and returns the financial summary and audited rows.
    """
    try:
        pr_content = await pr_file.read()
        b2_content = await gstr2b_file.read()

        pr_df = load_file_data(pr_file.filename, pr_content, source_type="PR")
        b2_df = load_file_data(gstr2b_file.filename, b2_content, source_type="2B")

        logger.info(f"Reconciling uploaded files: PR ({len(pr_df)} rows), 2B ({len(b2_df)} rows)")
        reconciled = reconcile_dataframes(pr_df, b2_df)


        # Store in latest session
        latest_session["summary"] = reconciled["summary"]
        latest_session["results"] = reconciled["results"]

        return reconciled
    except Exception as e:
        logger.error(f"Reconciliation error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to reconcile uploaded files: {str(e)}")


@app.get("/api/sample/{n}")
def load_sample_dataset(n: int):
    """
    Loads pre-generated sample pair number n (1 to 15) and runs reconciliation.
    Allows instant demonstration without manually selecting files.
    """
    sample_dir_name = f"sample_{n:02d}"
    sample_path = os.path.join(DATA_DIR, sample_dir_name)
    pr_path = os.path.join(sample_path, "purchase_register.csv")
    b2_path = os.path.join(sample_path, "gstr2b.csv")

    if not (os.path.exists(pr_path) and os.path.exists(b2_path)):
        raise HTTPException(
            status_code=404,
            detail=f"Sample '{sample_dir_name}' not found. Please run the data generator first."
        )

    try:
        pr_df = pd.read_csv(pr_path)
        b2_df = pd.read_csv(b2_path)
        reconciled = reconcile_dataframes(pr_df, b2_df)

        # Update latest session
        latest_session["summary"] = reconciled["summary"]
        latest_session["results"] = reconciled["results"]

        reconciled["sample_id"] = sample_dir_name
        return reconciled
    except Exception as e:
        logger.error(f"Error processing sample {n}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process sample {n}: {str(e)}")


@app.post("/api/review")
def review_decision(payload: Dict[str, Any] = Body(...)):
    """
    Human auditor confirms or rejects a row in the NEEDS_REVIEW queue.
    Accepts row_id, action ('APPROVE' or 'REJECT'), and optional full current results list.
    Recalculates total ITC at risk and category metrics instantly.
    """
    row_id = str(payload.get("row_id"))
    action = str(payload.get("action", "")).upper()
    results = payload.get("results") or latest_session["results"]

    if not row_id or action not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=400, detail="Invalid payload. Required: row_id and action ('APPROVE'|'REJECT')")

    target_row = None
    for r in results:
        if str(r.get("id")) == row_id or str(r.get("pr_row_id")) == row_id:
            target_row = r
            break

    if not target_row:
        raise HTTPException(status_code=404, detail=f"Row ID '{row_id}' not found in active session.")

    if action == "APPROVE":
        target_row["status"] = "MATCHED"
        target_row["mismatch_type"] = "NONE"
        target_row["itc_at_risk"] = 0.0
        target_row["confidence"] = 100
        target_row["reason"] = "Approved by human auditor. Validated as eligible ITC."
    elif action == "REJECT":
        target_row["status"] = "MISMATCHED"
        target_row["confidence"] = 100
        # If no specific risk calculated, default to total tax
        target_row["itc_at_risk"] = target_row.get("total_tax", 0.0)
        target_row["reason"] = "Rejected by human auditor. Tax credit withheld due to discrepancy."

    # Recalculate summary in pure Python
    updated_summary = calculate_financial_summary(results)
    latest_session["summary"] = updated_summary
    latest_session["results"] = results

    return {
        "status": "success",
        "updated_row": target_row,
        "summary": updated_summary,
        "results": results
    }


def generate_csv_string(results: List[Dict[str, Any]]) -> str:
    """Formats reconciliation result list into RFC 4180 compliant CSV."""
    output = io.StringIO()
    fields = [
        "pr_row_id", "status", "mismatch_type", "confidence", "itc_at_risk",
        "supplier_name", "gstin", "invoice_number", "invoice_date",
        "taxable_value", "total_tax", "total_amount",
        "candidate_2b_id", "b2_invoice_number", "b2_date", "b2_amount", "b2_tax",
        "reason"
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in results:
        writer.writerow(row)
    return output.getvalue()


@app.get("/api/export")
def export_csv_get():
    """Exports the current reconciliation session results as a downloadable CSV."""
    results = latest_session.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="No reconciliation data to export. Please run reconciliation first.")

    csv_data = generate_csv_string(results)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gst_reconciliation_report.csv"}
    )


@app.post("/api/export")
def export_csv_post(payload: List[Dict[str, Any]] = Body(...)):
    """Exports provided filtered or audited results as a downloadable CSV."""
    if not payload:
        raise HTTPException(status_code=400, detail="No rows provided for export.")

    csv_data = generate_csv_string(payload)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gst_reconciliation_report.csv"}
    )
