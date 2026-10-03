"""
Unit Tests for PDF Parsing & Conversion
Tests that PDF files (tables or text-based invoices) are converted to DataFrames
and seamlessly pass through the reconciliation pipeline.
"""

import io
import pytest
import pandas as pd
from backend.pdf_parser import parse_pdf_to_dataframe
from backend.reconcile import reconcile_dataframes


def test_pdf_fallback_and_parsing():
    """Tests PDF parsing fallback on dummy bytes."""
    dummy_pdf_bytes = b"%PDF-1.4 dummy content with 27AAACT2727Q1ZW INV/23-24/0045 11800.00 10000.00"
    df = parse_pdf_to_dataframe(dummy_pdf_bytes, source_type="PR")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "invoice_number" in df.columns or "gstin" in df.columns


def test_pdf_dataframe_reconciliation():
    """Tests that a DataFrame parsed from a PDF can be reconciled directly against a GSTR-2B DataFrame."""
    pr_df = pd.DataFrame([
        {
            "id": "PR_PDF_1",
            "invoice_number": "INV/23-24/0045",
            "invoice_date": "2023-05-10",
            "gstin": "27AAACT2727Q1ZW",
            "supplier_name": "Tata Consultancy Services Ltd",
            "taxable_value": 10000.0,
            "total_tax": 1800.0,
            "total_amount": 11800.0
        }
    ])

    b2_df = pd.DataFrame([
        {
            "id": "2B_PDF_1",
            "invoice_number": "23-24/45",
            "invoice_date": "2023-05-10",
            "gstin": "27AAACT2727Q1ZW",
            "supplier_name": "TATA CONSULTANCY SERVICES PRIVATE LIMITED",
            "taxable_value": 10000.0,
            "total_tax": 1800.0,
            "total_amount": 11800.0
        }
    ])

    reconciled = reconcile_dataframes(pr_df, b2_df)
    assert reconciled["summary"]["total_records"] == 1
    assert reconciled["summary"]["status_counts"]["MATCHED"] == 1
    assert reconciled["summary"]["total_itc_at_risk"] == 0.0
