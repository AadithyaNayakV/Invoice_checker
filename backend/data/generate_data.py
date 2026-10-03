"""
Synthetic Data Generator for GST Reconciliation Tool
Generates 15 realistic sample datasets (sample_01 to sample_15) varying from 30 to 1000 rows.
Includes:
- purchase_register.csv: Company internal purchase records
- gstr2b.csv: Supplier reported tax portal records
- answer_key.csv: Ground-truth audit validation answers

Planted discrepancies:
- Exact matches (75-85%)
- Name spelling variations (Pvt Ltd vs Private Limited)
- Invoice number format differences (INV/23-24/0045 vs 45)
- Small amount differences (typos/discrepancies in taxable value or rounding)
- GST rate mismatch (e.g. 18% in PR vs 12% in 2B)
- Missing in 2B (supplier never filed on government portal)
- Date in wrong period/month
- Duplicate entries
"""

import os
import csv
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Set fixed seeds for deterministic reproducibility
random.seed(42)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# 25 Realistic Indian suppliers with realistic GSTINs
SUPPLIER_CATALOG = [
    {"name": "Tata Consultancy Services Ltd", "alt_name": "TATA CONSULTANCY SERVICES PRIVATE LIMITED", "gstin": "27AAACT2727Q1ZW", "state": "27"},
    {"name": "Infosys Limited", "alt_name": "INFOSYS TECHNOLOGIES LTD", "gstin": "29AAACI4567A1Z3", "state": "29"},
    {"name": "Reliance Retail Private Limited", "alt_name": "RELIANCE RETAIL LTD", "gstin": "27AABCR1234D1ZA", "state": "27"},
    {"name": "Larsen & Toubro Ltd", "alt_name": "L & T LIMITED", "gstin": "27AAACL0123M1Z8", "state": "27"},
    {"name": "Mahindra & Mahindra Logistics Pvt Ltd", "alt_name": "MAHINDRA LOGISTICS LIMITED", "gstin": "27AAACM8890K1Z1", "state": "27"},
    {"name": "Bajaj Electricals Ltd", "alt_name": "BAJAJ ELECTRICALS PVT LTD", "gstin": "27AAACB2345H1Z5", "state": "27"},
    {"name": "Godrej Consumer Products Ltd", "alt_name": "GODREJ CONSUMER PRODUCTS LIMITED", "gstin": "27AAACG9876E1Z9", "state": "27"},
    {"name": "Wipro Technologies Pvt Ltd", "alt_name": "WIPRO LIMITED", "gstin": "29AAACW1122J1Z7", "state": "29"},
    {"name": "Hindustan Unilever Ltd", "alt_name": "HINDUSTAN UNILEVER PRIVATE LIMITED", "gstin": "27AAACH1111B1Z2", "state": "27"},
    {"name": "Asian Paints Limited", "alt_name": "ASIAN PAINTS PVT LTD", "gstin": "27AAACA0001F1Z4", "state": "27"},
    {"name": "Havells India Limited", "alt_name": "HAVELLS INDIA PRIVATE LIMITED", "gstin": "07AAACH2233P1ZC", "state": "07"},
    {"name": "UltraTech Cement Ltd", "alt_name": "ULTRATECH CEMENT LIMITED", "gstin": "27AAACU3344R1Z0", "state": "27"},
    {"name": "Bharat Petroleum Corp Ltd", "alt_name": "BPCL LIMITED", "gstin": "27AAACB0002G1Z6", "state": "27"},
    {"name": "Dabur India Limited", "alt_name": "DABUR INDIA PVT LTD", "gstin": "07AAACD5566T1ZE", "state": "07"},
    {"name": "Titan Company Ltd", "alt_name": "TITAN COMPANY LIMITED", "gstin": "29AAACT6677K1Z8", "state": "29"},
    {"name": "Apollo Tyres Ltd", "alt_name": "APOLLO TYRES PRIVATE LIMITED", "gstin": "32AAACA7788L1ZA", "state": "32"},
    {"name": "Maruti Suzuki India Ltd", "alt_name": "MARUTI SUZUKI INDIA LIMITED", "gstin": "06AAACM9900N1ZG", "state": "06"},
    {"name": "Adani Enterprises Ltd", "alt_name": "ADANI ENTERPRISES PRIVATE LIMITED", "gstin": "24AAACA3322C1ZK", "state": "24"},
    {"name": "Sun Pharmaceutical Industries Ltd", "alt_name": "SUN PHARMA LTD", "gstin": "24AAACS4433D1ZM", "state": "24"},
    {"name": "Cipla Limited", "alt_name": "CIPLA PVT LTD", "gstin": "27AAACC5544E1ZO", "state": "27"},
    {"name": "Britannia Industries Ltd", "alt_name": "BRITANNIA INDUSTRIES PRIVATE LIMITED", "gstin": "19AAACB6655F1ZQ", "state": "19"},
    {"name": "Vedanta Resources Ltd", "alt_name": "VEDANTA LIMITED", "gstin": "08AAACV7766G1ZS", "state": "08"},
    {"name": "Hero MotoCorp Ltd", "alt_name": "HERO MOTOCORP PRIVATE LIMITED", "gstin": "07AAACH8877H1ZU", "state": "07"},
    {"name": "Zomato Private Limited", "alt_name": "ZOMATO LIMITED", "gstin": "07AAACZ9988J1ZW", "state": "07"},
    {"name": "Swiggy Bundl Technologies Pvt Ltd", "alt_name": "BUNDL TECHNOLOGIES PRIVATE LIMITED", "gstin": "29AAGCB1234K1ZY", "state": "29"}
]

GST_RATES = [5.0, 12.0, 18.0, 28.0]
BUYER_STATE = "27"  # Maharashtra

# Sizes for 15 sample datasets
SAMPLE_SIZES = [
    30,    # sample_01
    35,    # sample_02
    40,    # sample_03
    50,    # sample_04
    60,    # sample_05
    100,   # sample_06
    150,   # sample_07
    200,   # sample_08
    200,   # sample_09
    250,   # sample_10
    300,   # sample_11
    500,   # sample_12
    800,   # sample_13
    1000,  # sample_14
    1000   # sample_15
]


def random_date(start_date: date, end_date: date) -> str:
    """Generates a random ISO date between start and end."""
    delta = (end_date - start_date).days
    r_days = random.randint(0, delta)
    return (start_date + timedelta(days=r_days)).isoformat()


def calculate_tax(taxable: Decimal, rate: Decimal, is_interstate: bool):
    """Calculates CGST, SGST, IGST, total_tax, and total_amount."""
    tax_factor = rate / Decimal("100")
    total_tax = (taxable * tax_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if is_interstate:
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = total_tax
    else:
        cgst = (total_tax / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = total_tax - cgst
        igst = Decimal("0.00")
    total_amount = (taxable + total_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return cgst, sgst, igst, total_tax, total_amount


def generate_sample_dataset(sample_num: int, num_rows: int):
    """Generates purchase_register.csv, gstr2b.csv, and answer_key.csv for a sample."""
    sample_dir = os.path.join(DATA_DIR, f"sample_{sample_num:02d}")
    os.makedirs(sample_dir, exist_ok=True)

    pr_rows = []
    gstr2b_rows = []
    answer_rows = []

    start_date = date(2023, 4, 1)
    end_date = date(2024, 3, 31)

    # Calculate exact matches count (around 80%)
    exact_match_ratio = random.uniform(0.78, 0.84)
    exact_count = int(num_rows * exact_match_ratio)
    problem_count = num_rows - exact_count

    # Distribute problem types
    # Types: NAME_DIFF, INV_FORMAT, AMOUNT_DIFF, RATE_MISMATCH, MISSING_IN_2B, DATE_PERIOD
    mismatch_pool = [
        "NAME_DIFF",
        "INV_FORMAT",
        "AMOUNT_DIFF",
        "RATE_MISMATCH",
        "MISSING_IN_2B",
        "DATE_PERIOD"
    ]

    assigned_types = ["EXACT"] * exact_count
    for i in range(problem_count):
        assigned_types.append(mismatch_pool[i % len(mismatch_pool)])
    random.shuffle(assigned_types)

    inv_counter = 1000 + (sample_num * 1000)

    for idx, issue_type in enumerate(assigned_types):
        pr_id = f"PR_{idx+1:04d}"
        cand_2b_id = f"2B_{idx+1:04d}"
        inv_counter += 1

        supplier = random.choice(SUPPLIER_CATALOG)
        is_interstate = (supplier["state"] != BUYER_STATE)
        base_rate = Decimal(str(random.choice(GST_RATES)))
        taxable_val = Decimal(str(random.randint(50, 5000) * 100))  # 5,000 to 500,000 INR
        inv_date_str = random_date(start_date, end_date)

        cgst, sgst, igst, total_tax, total_amount = calculate_tax(taxable_val, base_rate, is_interstate)

        # Baseline invoice numbers
        inv_serial = f"{inv_counter}"
        pr_inv_num = f"INV/23-24/{inv_serial}"
        b2_inv_num = pr_inv_num

        pr_supplier_name = supplier["name"]
        b2_supplier_name = supplier["name"]

        b2_date_str = inv_date_str
        b2_taxable = taxable_val
        b2_rate = base_rate
        b2_cgst, b2_sgst, b2_igst, b2_tax, b2_amount = cgst, sgst, igst, total_tax, total_amount

        # Default expectation
        expected_status = "MATCHED"
        expected_mismatch = "NONE"
        expected_itc_risk = Decimal("0.00")

        if issue_type == "EXACT":
            expected_status = "MATCHED"
            expected_mismatch = "NONE"
            expected_itc_risk = Decimal("0.00")

        elif issue_type == "NAME_DIFF":
            # Same invoice & amounts, but supplier legal name variation
            b2_supplier_name = supplier["alt_name"]
            expected_status = "MATCHED"
            expected_mismatch = "NAME_DIFF"
            expected_itc_risk = Decimal("0.00")

        elif issue_type == "INV_FORMAT":
            # Format discrepancy: INV/23-24/0045 vs 45
            b2_inv_num = inv_serial
            expected_status = "MATCHED"
            expected_mismatch = "NONE"
            expected_itc_risk = Decimal("0.00")

        elif issue_type == "AMOUNT_DIFF":
            # Small amount difference in supplier filing
            amt_diff = Decimal(str(random.choice([250.0, 500.0, 1200.0, 350.0])))
            b2_taxable = max(Decimal("100.00"), taxable_val - amt_diff)
            b2_cgst, b2_sgst, b2_igst, b2_tax, b2_amount = calculate_tax(b2_taxable, base_rate, is_interstate)
            expected_status = "MISMATCHED"
            expected_mismatch = "AMOUNT_DIFF"
            expected_itc_risk = (total_tax - b2_tax).quantize(Decimal("0.01"))

        elif issue_type == "RATE_MISMATCH":
            # Wrong tax rate applied
            alt_rates = [r for r in GST_RATES if Decimal(str(r)) != base_rate]
            b2_rate = Decimal(str(random.choice(alt_rates)))
            b2_cgst, b2_sgst, b2_igst, b2_tax, b2_amount = calculate_tax(taxable_val, b2_rate, is_interstate)
            expected_status = "MISMATCHED"
            expected_mismatch = "RATE_MISMATCH"
            expected_itc_risk = max(Decimal("0.00"), total_tax - b2_tax).quantize(Decimal("0.01"))

        elif issue_type == "MISSING_IN_2B":
            # Supplier did not report invoice to GST portal
            expected_status = "MISMATCHED"
            expected_mismatch = "MISSING_IN_2B"
            expected_itc_risk = total_tax

        elif issue_type == "DATE_PERIOD":
            # Different month/quarter (shift date by 60 days)
            orig_d = date.fromisoformat(inv_date_str)
            new_d = orig_d + timedelta(days=60)
            b2_date_str = new_d.isoformat()
            expected_status = "MISMATCHED"
            expected_mismatch = "DATE_PERIOD"
            expected_itc_risk = total_tax

        # Build Purchase Register record
        pr_rows.append({
            "id": pr_id,
            "invoice_number": pr_inv_num,
            "invoice_date": inv_date_str,
            "gstin": supplier["gstin"],
            "supplier_name": pr_supplier_name,
            "taxable_value": f"{taxable_val:.2f}",
            "rate": f"{base_rate:.1f}",
            "cgst": f"{cgst:.2f}",
            "sgst": f"{sgst:.2f}",
            "igst": f"{igst:.2f}",
            "total_tax": f"{total_tax:.2f}",
            "total_amount": f"{total_amount:.2f}"
        })

        # Build GSTR-2B record (if not missing in 2B)
        if issue_type != "MISSING_IN_2B":
            gstr2b_rows.append({
                "id": cand_2b_id,
                "invoice_number": b2_inv_num,
                "invoice_date": b2_date_str,
                "gstin": supplier["gstin"],
                "supplier_name": b2_supplier_name,
                "taxable_value": f"{b2_taxable:.2f}",
                "rate": f"{b2_rate:.1f}",
                "cgst": f"{b2_cgst:.2f}",
                "sgst": f"{b2_sgst:.2f}",
                "igst": f"{b2_igst:.2f}",
                "total_tax": f"{b2_tax:.2f}",
                "total_amount": f"{b2_amount:.2f}"
            })

        # Build ground-truth answer key
        answer_rows.append({
            "pr_row_id": pr_id,
            "candidate_2b_id": cand_2b_id if issue_type != "MISSING_IN_2B" else "",
            "invoice_number": pr_inv_num,
            "supplier_name": pr_supplier_name,
            "gstin": supplier["gstin"],
            "expected_status": expected_status,
            "expected_mismatch_type": expected_mismatch,
            "expected_itc_at_risk": f"{expected_itc_risk:.2f}"
        })

    # Shuffle GSTR-2B so order does not reveal match
    random.shuffle(gstr2b_rows)

    # Write Purchase Register CSV
    pr_path = os.path.join(sample_dir, "purchase_register.csv")
    with open(pr_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "invoice_number", "invoice_date", "gstin", "supplier_name",
            "taxable_value", "rate", "cgst", "sgst", "igst", "total_tax", "total_amount"
        ])
        writer.writeheader()
        writer.writerows(pr_rows)

    # Write GSTR-2B CSV
    b2_path = os.path.join(sample_dir, "gstr2b.csv")
    with open(b2_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "invoice_number", "invoice_date", "gstin", "supplier_name",
            "taxable_value", "rate", "cgst", "sgst", "igst", "total_tax", "total_amount"
        ])
        writer.writeheader()
        writer.writerows(gstr2b_rows)

    # Write Answer Key CSV
    ans_path = os.path.join(sample_dir, "answer_key.csv")
    with open(ans_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pr_row_id", "candidate_2b_id", "invoice_number", "supplier_name",
            "gstin", "expected_status", "expected_mismatch_type", "expected_itc_at_risk"
        ])
        writer.writeheader()
        writer.writerows(answer_rows)


import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print(f"Generating 15 reproducible sample GST reconciliation datasets in {DATA_DIR}...")
    for i, size in enumerate(SAMPLE_SIZES, start=1):
        generate_sample_dataset(i, size)
        print(f"  [OK] sample_{i:02d} ({size} rows) generated.")
    print("All 15 sample pairs and ground-truth answer keys successfully generated!")


if __name__ == "__main__":
    main()

