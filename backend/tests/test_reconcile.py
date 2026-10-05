"""
Unit Tests for GST Reconciliation Logic
Tests normalization, exact matching, and financial ITC-at-risk calculations.
"""

import pytest
import pandas as pd
from decimal import Decimal
from backend.reconcile import (
    clean_supplier_name,
    normalize_invoice_number,
    round_curr,
    standardize_columns,
    reconcile_dataframes,
    calculate_financial_summary
)


class TestNormalization:
    """Tests text and invoice normalization logic."""

    def test_clean_supplier_name_variants(self):
        # Corporate suffix stripping & uppercase
        assert clean_supplier_name("Tata Consultancy Services Ltd") == "TATA CONSULTANCY SERVICES"
        assert clean_supplier_name("Infosys Private Limited") == "INFOSYS"
        assert clean_supplier_name("Reliance Retail Pvt Ltd") == "RELIANCE RETAIL"
        assert clean_supplier_name("Larsen & Toubro Limited") == "LARSEN TOUBRO"
        assert clean_supplier_name("Wipro Technologies LLP") == "WIPRO TECHNOLOGIES"
        assert clean_supplier_name(None) == ""

    def test_normalize_invoice_number(self):
        # Extracts only the last number part, without joining financial year digits
        assert normalize_invoice_number("INV/24-25/0043") == "43"
        assert normalize_invoice_number("INV/23-24/0045") == "45"
        assert normalize_invoice_number("INV-0012") == "12"
        assert normalize_invoice_number("43") == "43"
        assert normalize_invoice_number("0043") == "43"
        assert normalize_invoice_number("00045") == "45"
        assert normalize_invoice_number("BILL/2023/99") == "99"
        assert normalize_invoice_number("0") == "0"
        assert normalize_invoice_number("") == ""


class TestExactMatching:
    """Tests vectorized exact matching logic."""

    def test_vectorized_exact_match(self):
        pr_data = pd.DataFrame([
            {
                "id": "PR_1",
                "invoice_number": "INV/23-24/0045",
                "invoice_date": "2023-05-10",
                "gstin": "27AAACT2727Q1ZW",
                "supplier_name": "Tata Consultancy Services Ltd",
                "taxable_value": 10000.0,
                "total_tax": 1800.0,
                "total_amount": 11800.0
            }
        ])

        b2_data = pd.DataFrame([
            {
                "id": "2B_1",
                "invoice_number": "23-24/45",  # Equivalent normalized: 232445
                "invoice_date": "2023-05-10",
                "gstin": "27AAACT2727Q1ZW",
                "supplier_name": "TATA CONSULTANCY SERVICES PRIVATE LIMITED",
                "taxable_value": 10000.0,
                "total_tax": 1800.0,
                "total_amount": 11800.0
            }
        ])

        result = reconcile_dataframes(pr_data, b2_data)
        rows = result["results"]

        assert len(rows) == 1
        assert rows[0]["status"] == "MATCHED"
        assert rows[0]["mismatch_type"] == "NONE"
        assert rows[0]["confidence"] == 100
        assert rows[0]["itc_at_risk"] == 0.0

    def test_missing_in_2b(self):
        pr_data = pd.DataFrame([
            {
                "id": "PR_1",
                "invoice_number": "INV/2023/999",
                "invoice_date": "2023-06-15",
                "gstin": "27AAACB0002G1Z6",
                "supplier_name": "Bharat Petroleum Corp Ltd",
                "taxable_value": 50000.0,
                "total_tax": 9000.0,
                "total_amount": 59000.0
            }
        ])

        # Empty 2B pool
        b2_data = pd.DataFrame(columns=["id", "invoice_number", "gstin", "supplier_name", "taxable_value", "total_tax", "total_amount"])

        result = reconcile_dataframes(pr_data, b2_data)
        rows = result["results"]

        assert len(rows) == 1
        assert rows[0]["status"] == "MISMATCHED"
        assert rows[0]["mismatch_type"] == "MISSING_IN_2B"
        assert rows[0]["itc_at_risk"] == 9000.0


class TestMoneyCalculations:
    """Tests strict Python-based financial calculation of ITC at risk."""

    def test_summary_and_itc_calculation(self):
        rows = [
            {
                "id": "1",
                "status": "MATCHED",
                "mismatch_type": "NONE",
                "itc_at_risk": 0.0,
                "supplier_name": "Supplier A",
                "gstin": "27A",
                "total_tax": 100.0
            },
            {
                "id": "2",
                "status": "MISMATCHED",
                "mismatch_type": "MISSING_IN_2B",
                "itc_at_risk": 550.50,
                "supplier_name": "Supplier B",
                "gstin": "27B",
                "total_tax": 550.50
            },
            {
                "id": "3",
                "status": "NEEDS_REVIEW",
                "mismatch_type": "AMOUNT_DIFF",
                "itc_at_risk": 200.25,
                "supplier_name": "Supplier B",
                "gstin": "27B",
                "total_tax": 1200.25
            }
        ]

        summary = calculate_financial_summary(rows)

        assert summary["total_records"] == 3
        # 550.50 + 200.25 = 750.75
        assert summary["total_itc_at_risk"] == 750.75
        assert summary["status_counts"]["MATCHED"] == 1
        assert summary["status_counts"]["MISMATCHED"] == 1
        assert summary["status_counts"]["NEEDS_REVIEW"] == 1

        # Check supplier grouping
        assert len(summary["itc_by_supplier"]) == 1
        assert summary["itc_by_supplier"][0]["supplier_name"] == "Supplier B"
        assert summary["itc_by_supplier"][0]["itc_at_risk"] == 750.75
        assert summary["itc_by_supplier"][0]["invoice_count"] == 2
