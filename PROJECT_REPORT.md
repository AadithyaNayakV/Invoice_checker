# Comprehensive Project Report: Indian GST Reconciliation Engine 📑🇮🇳

---

## 1. Executive Summary

The **GST Reconciliation Tool** is an automated, enterprise-grade audit system designed to solve one of the most critical compliance challenges in the Indian taxation ecosystem: **reconciling an organization's internal Purchase Register against the government's GSTR-2B portal records**.

The tool automatically ingests purchase records and government filings in **both CSV and PDF formats**, cleans and normalizes messy real-world variations, performs sub-millisecond vectorized matching, utilizes blocked fuzzy candidate retrieval, leverages Google Gemini 2.5 Flash AI for discrepancy auditing, and uses strict Python financial calculations (`Decimal`) to compute the exact **Input Tax Credit (ITC) at risk in Indian Rupees (₹)**.

---

## 2. The Real-World Problem: What is ITC & Why Does This Matter?

### What is Input Tax Credit (ITC)?
Under the Indian Goods and Services Tax (GST) system:
- When Company A buys ₹1,00,000 worth of raw materials from Supplier B at 18% GST, Company A pays **₹18,000 in GST** to Supplier B.
- When Company A subsequently sells finished goods and owes ₹25,000 in GST to the government, it is entitled to deduct the ₹18,000 it already paid to Supplier B. Company A only pays the net difference of **₹7,000**.
- The ₹18,000 deduction is called **Input Tax Credit (ITC)**.

### The Compliance Nightmare: Section 16(2)(aa) of the CGST Act
Under Indian tax law, **a company can only claim ITC if the supplier actually uploads and reports that specific invoice on the government GST portal (GSTR-2B)**.

Every month, finance teams compare two lists:
1. **List 1: Purchase Register (PR)**: Internal ERP records (SAP, Tally, Zoho) of what the company purchased.
2. **List 2: GSTR-2B**: Government portal records of what suppliers reported they sold.

In reality, these two lists **rarely match cleanly**:
- **Supplier Legal Name Variations**: Company enters `Tata Consultancy Services Ltd`, but GST portal shows `TATA CONSULTANCY SERVICES PRIVATE LIMITED`.
- **Invoice Formatting Discrepancies**: Company records `INV/23-24/0045`, but supplier reported `45` or `232445`.
- **Amount & Tax Drift**: Supplier made a typo and reported ₹11,500 instead of ₹11,800.
- **Tax Rate Mismatches**: Supplier charged 12% GST instead of the agreed 18%.
- **Timing / Period Shift**: Purchase occurred in May, but supplier filed late in August.
- **Unfiled Invoices (`MISSING_IN_2B`)**: Supplier collected tax from the buyer but never filed it on the GST portal.

### The Financial Risk
If a company claims unverified or missing ITC:
- The tax department disallows the credit and demands repayment.
- Penalties of **18% per annum interest** and up to **100% tax penalty** are levied.
- Working capital is frozen.

---

## 3. How the System Works (End-to-End Pipeline)

```
[ Purchase Register (CSV / PDF) ]        [ GSTR-2B Filings (CSV / PDF) ]
               \                                  /
                v                                v
+-------------------------------------------------------------------------+
| STAGE 0: Multi-Format Ingestion & Parsing (PDF / CSV)                   |
| - Extracts structured tables or regex patterns from PDF files           |
| - Converts everything into unified pandas DataFrames                    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| STAGE 1: Vectorized Data Cleaning & Normalization                       |
| - Strips corporate entity tokens (PVT LTD, PRIVATE LIMITED, LLP)        |
| - Standardizes invoice numbers (strips prefixes, slashes, leading zeros)|
| - Formats and rounds financial currency values                          |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| STAGE 2: Vectorized Exact Matching (Pure Python / Pandas)               |
| - Merges on (GSTIN + Normalized Invoice No + Exact Amount)              |
| - Resolves 75% to 85% of invoices in milliseconds with ZERO AI calls!   |
| - Tagged as MATCHED, ITC at Risk = ₹0.00                                |
+-------------------------------------------------------------------------+
                                    |
                        [Unmatched Invoices Pool]
                                    |
                                    v
+-------------------------------------------------------------------------+
| STAGE 3: Blocked Rapidfuzz Candidate Shortlisting                       |
| - Blocks on same GSTIN or State Code / Name prefix (scalable to 10k+)   |
| - If no candidate exists at all -> Immediate MISSING_IN_2B (no AI)      |
| - If candidate exists -> Shortlists Top 3 candidates per invoice        |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| STAGE 4: Gemini AI Discrepancy Auditing + SQLite Caching                |
| - Checks SQLite cache (SHA-256 hash of query + candidates)              |
| - Batches remaining cache misses (~10 per call) via match_prompt.txt    |
| - Returns strict JSON: same_invoice, confidence (0-100), mismatch_type  |
| - Graceful Fallback: Built-in offline heuristic if API key is pending   |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| STAGE 5: Strict Python Financial Audit & Human Review Queue             |
| - Confidence >= 80% -> Accepted automatically                           |
| - Confidence < 80%  -> Tagged as NEEDS_REVIEW                           |
| - Pure Python Decimal calculations compute Total ITC at Risk (₹)        |
| - Interactive Review Queue: Approve/Reject with live live updates       |
+-------------------------------------------------------------------------+
```

---

## 4. Multi-Format Input Support: CSV & PDF Processing

Users can upload documents in **either CSV or PDF format**:
- **Purchase Register**: Can be `.csv` or `.pdf` (e.g. ERP ledger statement or invoice PDF).
- **GSTR-2B**: Can be `.csv` or `.pdf` (e.g. GST Portal PDF download or statement).
- **Mixed Uploads**: PR as PDF and GSTR-2B as CSV (or vice versa).

### Internal PDF Conversion Mechanism (`backend/pdf_parser.py`)
1. **Tabular PDF Extraction**: Uses `pdfplumber` to detect table grids, headers, and column alignments. Automatically maps columns (`Invoice No`, `Date`, `GSTIN`, `Taxable Value`, `Total Tax`) to our standardized schema.
2. **Text-Based Pattern Extraction**: If the PDF is an unstructured statement or scan printout, it uses `pypdf` and regex patterns:
   - Validates Indian GSTINs (`\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b`)
   - Extracts dates (`YYYY-MM-DD`, `DD/MM/YYYY`)
   - Extracts invoice serials and currency numbers
3. **Seamless Hand-off**: Converts extracted records into an in-memory `pd.DataFrame` that feeds directly into the reconciliation pipeline without requiring temporary disk writes.

---

## 5. Core Architectural Principle: Python vs. AI Division of Labor

> ⚖️ **The Cardinal Rule**:  
> **Python performs all exact matching and 100% of financial arithmetic. The AI only handles messy textual discrepancy classification and NEVER calculates money.**

### Why LLMs Must NEVER Do Financial Arithmetic:
1. **Floating-point & Hallucination Risks**: LLMs predict tokens probabilistically. They are prone to off-by-one errors, digit transpositions, and subtle rounding mistakes that are illegal in accounting.
2. **Determinism & Reproducibility**: Financial audits require 100% deterministic reproducibility. Re-running the tool on the same ledger must yield the exact same rupee figure down to the paise.
3. **Cost & Latency**: Doing arithmetic in Python takes nanoseconds. Doing arithmetic in an LLM costs money, burns tokens, and takes seconds.

### The Role of Gemini AI:
The Gemini AI is exclusively used as an **intelligent auditor** for edge cases:
- *“Is `INV/23-24/0045` with vendor `Tata Consultancy Services Ltd` the same transaction as invoice `45` reported by `TATA CONSULTANCY SERVICES PRIVATE LIMITED`?”*
- It assesses the context, outputs a confidence score (0-100), classifies the discrepancy category, and returns a single-sentence audit reason.

---

## 6. Discrepancy Classification Taxonomy

The engine classifies every purchase invoice into one of 6 strict categories:

| Discrepancy Type | Definition | Status | ITC Treatment |
|:---|:---|:---:|:---|
| **`NONE`** | Exact match or verified normalized match. | `MATCHED` | Eligible (ITC at Risk = ₹0.00) |
| **`NAME_DIFF`** | GSTIN and invoice numbers match, but supplier legal name has variations (e.g. `Pvt Ltd` vs `Private Limited`). | `MATCHED` / `NEEDS_REVIEW` | Eligible once verified |
| **`AMOUNT_DIFF`** | Invoice number matches, but taxable value or invoice total differs between PR and 2B. | `MISMATCHED` | Discrepancy amount blocked |
| **`RATE_MISMATCH`** | Taxable value matches, but GST tax rate (5%, 12%, 18%, 28%) differs. | `MISMATCHED` | Tax rate difference at risk |
| **`DATE_PERIOD`** | Same invoice and amounts, but reported in a different month or tax period. | `MISMATCHED` | Credit delayed / held for period |
| **`MISSING_IN_2B`** | Invoice present in company books, but completely absent from GSTR-2B portal. | `MISMATCHED` | **100% of tax blocked at risk** |

---

## 7. Mathematical Formulation of ITC at Risk

All financial calculations are computed using Python’s `decimal.Decimal` with `ROUND_HALF_UP` to two decimal places:

$$\text{ITC at Risk} = \sum_{i \in \text{Problem Rows}} \text{RiskAmount}_i$$

Where:
- For $\text{MISSING\_IN\_2B}$: $\text{RiskAmount}_i = \text{Tax}_{\text{PR}}$ (full tax cannot be claimed).
- For $\text{RATE\_MISMATCH}$ or $\text{AMOUNT\_DIFF}$: $\text{RiskAmount}_i = \max(0.00, \text{Tax}_{\text{PR}} - \text{Tax}_{\text{2B}})$.
- For $\text{NEEDS\_REVIEW}$: $\text{RiskAmount}_i = \text{Tax}_{\text{PR}}$ (credit is conservatively frozen until an auditor signs off).
- For $\text{MATCHED}$: $\text{RiskAmount}_i = 0.00$.

---

## 8. Human-in-the-Loop Review Queue

To prevent false positives or unwarranted tax disallowances, the application implements a **Human Review Queue**:
- Any AI decision with **confidence score < 80%** is tagged as `NEEDS_REVIEW`.
- The user is presented with a **side-by-side comparison**:
  - Left panel: Purchase Register record (Invoice #, Date, GSTIN, Tax, Total).
  - Right panel: GSTR-2B portal record candidate.
  - Middle: AI audit finding and reasoning.
- **Two Actions**:
  - **Approve Match**: Marks the invoice as `MATCHED`, clears the ITC at risk to ₹0.00, and immediately updates dashboard totals.
  - **Reject & Block ITC**: Confirms the discrepancy, flags the row as `MISMATCHED`, blocks the tax credit, and retains the risk figure.

---

## 9. Algorithmic Optimizations & Scalability

| Technique | Implementation | Impact |
|:---|:---|:---|
| **Vectorized Merging** | `pandas.merge` on normalized hash keys | Resolves 80% of rows in < 20ms without invoking AI or nested loops. |
| **Rapidfuzz Blocking** | Filters candidates by GSTIN or State Code first | Reduces search space from $O(N \times M)$ to small, bounded candidate subsets. |
| **SQLite Caching** | SHA-256 row-pair hash in `ai_cache` table | Repeated reconciliation runs take **zero API tokens** and return in milliseconds. |
| **Batch AI Calling** | Batches ~10 candidate evaluations per prompt | Cuts API network round-trips by 90% and stays well within free-tier rate limits. |
| **Fail-Safe Fallback** | Offline heuristic discrepancy classifier | Guarantees the application **never crashes** if network or API keys fail. |

---

## 10. Quality Proof: Benchmark Evaluation (15 Datasets)

The engine was evaluated across 15 reproducible benchmark datasets ([evaluation_results.md](file:///c:/Users/aadit/OneDrive/Desktop/GST_INVOICE/evaluation_results.md)):
- **Total Invoices Evaluated**: `4,715`
- **Weighted Status Accuracy**: `93.64%`
- **Weighted Category Accuracy**: `91.94%`
- **Execution Time on 1,000 Rows**: `2.76s` to `3.19s`
- **Pytest Automated Tests**: `100% passing`

---

## 11. Technology Stack Summary

- **Backend**: Python 3.10+, FastAPI, Pandas, Rapidfuzz, google-genai, SQLite, python-dotenv, Pytest, pypdf, pdfplumber
- **Frontend**: React 18, Vite, Tailwind CSS, Recharts, Lucide Icons
- **AI Model**: Google Gemini 2.5 Flash (via `google-genai` SDK)

---

## 12. Interview Talking Points & Cheat Sheet

### Q1: Why did you separate exact matching from AI matching?
> *"In a typical enterprise purchase ledger, 75% to 85% of invoices are clean or can be matched with deterministic normalization rules (like stripping corporate suffixes and formatting invoice numbers). Invoking an LLM for every single row would be slow, expensive, and unnecessary. By using vectorized pandas exact matching first, we process 80% of the ledger in under 30 milliseconds. We only send messy edge cases to Gemini, saving tokens and speeding up execution by over 10x."*

### Q2: Why does Python do all financial calculations instead of the AI?
> *"Financial reconciliation requires 100% mathematical integrity and legal auditability. LLMs are generative and probabilistic; they are prone to subtle arithmetic drift or hallucination. Under GST Section 16(2)(aa), being off by even a few rupees can lead to statutory notices. Therefore, Python handles all tax subtraction, summation, and rounding using `decimal.Decimal`, while Gemini is strictly utilized for textual discrepancy reasoning."*

### Q3: How do you handle large datasets (e.g. 10,000+ rows) without performance degradation?
> *"A naive fuzzy string comparison across two 10,000-row datasets requires 100,000,000 pairwise string distance computations ($O(N \times M)$). To make this fast, we apply 'blocking': we only run Rapidfuzz against candidates that share the same GSTIN or state code prefix. This bounds each candidate pool to just a few records, allowing 1,000 rows to reconcile in under 3.2 seconds."*

### Q4: How does the system handle PDF inputs?
> *"The backend includes a dual-engine PDF parser using `pdfplumber` and `pypdf`. When a user uploads a PDF statement or invoice, the system first inspects the file for tabular structures. If table grids exist, it extracts the columns directly into a DataFrame. If the PDF contains plain text or statement lines, it runs pattern recognition regexes to detect 15-character GSTINs, invoice numbers, dates, and amounts, seamlessly feeding the extracted records into the reconciliation engine."*
