# GST Reconciliation Tool - Quality & Performance Benchmark

This document presents the rigorous evaluation of the **GST Reconciliation Tool** across 15 reproducible benchmark datasets ranging from small batches (30 rows) to large corporate ledgers (1,000 rows).

## Executive Summary

- **Total Invoices Audited**: `4,715`
- **Status Matching Accuracy**: `93.64%`
- **Mismatch Categorization Accuracy**: `91.94%`
- **True Ground-Truth ITC at Risk**: `₹14,428,442.00`
- **Algorithm Calculated ITC at Risk**: `₹10,169,237.00`
- **ITC Monetary Variance**: `₹4,259,205.00` (`29.52%` error)

## Dataset Breakdown (15 Samples)

| Sample ID | Size (Rows) | Runtime (s) | Status Accuracy | Category Accuracy | Ground Truth ITC (₹) | Predicted ITC (₹) | Error (₹) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `sample_01` | 30 | 0.171s | 93.33% | 93.33% | ₹25,534.00 | ₹16,390.00 | ₹9,144.00 |
| `sample_02` | 35 | 0.155s | 94.29% | 94.29% | ₹89,940.50 | ₹11,046.50 | ₹78,894.00 |
| `sample_03` | 40 | 0.191s | 92.5% | 95.0% | ₹166,576.00 | ₹150,551.00 | ₹16,025.00 |
| `sample_04` | 50 | 0.23s | 94.0% | 94.0% | ₹205,265.50 | ₹156,413.50 | ₹48,852.00 |
| `sample_05` | 60 | 0.247s | 93.33% | 93.33% | ₹205,536.00 | ₹184,000.00 | ₹21,536.00 |
| `sample_06` | 100 | 0.389s | 93.0% | 94.0% | ₹232,548.00 | ₹90,650.00 | ₹141,898.00 |
| `sample_07` | 150 | 0.418s | 94.67% | 94.67% | ₹571,059.00 | ₹493,802.00 | ₹77,257.00 |
| `sample_08` | 200 | 0.669s | 93.0% | 92.5% | ₹525,497.50 | ₹439,888.50 | ₹85,609.00 |
| `sample_09` | 200 | 0.636s | 93.5% | 93.5% | ₹677,370.00 | ₹306,457.00 | ₹370,913.00 |
| `sample_10` | 250 | 0.819s | 94.0% | 92.8% | ₹914,003.00 | ₹520,682.00 | ₹393,321.00 |
| `sample_11` | 300 | 0.777s | 94.67% | 93.0% | ₹1,114,170.50 | ₹719,354.50 | ₹394,816.00 |
| `sample_12` | 500 | 1.56s | 92.8% | 90.0% | ₹1,692,527.50 | ₹976,499.50 | ₹716,028.00 |
| `sample_13` | 800 | 2.374s | 93.38% | 91.12% | ₹2,438,578.00 | ₹1,889,068.00 | ₹549,510.00 |
| `sample_14` | 1000 | 2.768s | 94.3% | 92.5% | ₹2,764,293.00 | ₹2,170,511.00 | ₹593,782.00 |
| `sample_15` | 1000 | 3.192s | 93.3% | 91.0% | ₹2,805,543.50 | ₹2,043,923.50 | ₹761,620.00 |

## Per-Mismatch Type Classification Metrics

| Discrepancy Type | Support (Invoices) | Precision (%) | Recall (%) | F1-Score (%) | Description |
|:---|:---:|:---:|:---:|:---:|:---|
| **AMOUNT_DIFF** | 152 | 50.33% | 100.00% | 66.96% | Discrepancy in taxable value or bill amount |
| **DATE_PERIOD** | 146 | 0.00% | 0.00% | 0.00% | Invoices filed in different tax periods/months |
| **MISSING_IN_2B** | 148 | 100.00% | 43.24% | 60.38% | Supplier failed to report invoice to government |
| **NAME_DIFF** | 158 | 0.00% | 0.00% | 0.00% | Legal corporate name variations (Pvt Ltd vs Ltd) |
| **NONE** | 3961 | 92.61% | 96.11% | 94.33% | Exact matches and standard normalized invoices |
| **RATE_MISMATCH** | 150 | 0.00% | 0.00% | 0.00% | GST rate discrepancies (5% / 12% / 18% / 28%) |

## Key Architectural Takeaways for Interview

1. **Vectorized Exact Match First**: Exact matches (75-85% of records) are matched in sub-millisecond pandas vectorized merges without invoking AI.
2. **Rapidfuzz Blocking**: Unmatched candidates are shortlisted using state-code and GSTIN blocking, scaling smoothly even at 1,000+ rows.
3. **Strict Python Financial Integrity**: All tax and ITC calculations use Python `Decimal` (never generative AI arithmetic).
4. **Robust Offline Heuristic Fallback**: Zero runtime crash risk when API keys or network are unavailable.
5. **SQLite Caching**: Zero-cost repeated reconciliations via cryptographic row hashing.
