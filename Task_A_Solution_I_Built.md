# Task A: Solution I Built — GST Reconciliation Tool

> **Candidate Showcase Artifact** | 20-Minute Interview Presentation  
> **Project:** GST Reconciliation Tool (Purchase Register vs. GSTR-2B Audit Engine)  
> **Tech Stack:** Python (FastAPI, Pandas, Rapidfuzz, Decimal), Google Gemini 2.5 Flash, SQLite, React 18, Tailwind CSS  

---

## 1. Project Overview

- **Project Name:** GST Reconciliation Tool & Compliance Auditor
- **One-Line Description:** An AI-assisted, mathematically deterministic audit engine that reconciles company purchase books against Indian government GSTR-2B tax records, detects invoice discrepancies, and pinpoints Input Tax Credit (ITC) at risk in Indian Rupees (₹).
- **What I Built:** A full-stack web application featuring an asynchronous FastAPI backend, a multi-format PDF and CSV data ingestion pipeline, a vectorized deterministic matching algorithm, a blocked fuzzy candidate engine, a Google Gemini 2.5 Flash discrepancy auditor with SQLite caching, and a pure-white React dashboard with an interactive human-in-the-loop review queue.

---

## 2. Problem

### What Problem It Solves
Under India's Goods and Services Tax (GST) law (**Section 16(2)(aa) of the CGST Act**), a business cannot claim tax credit on purchases unless the supplier has actually uploaded and reported that specific invoice to the government portal (**GSTR-2B**).

### Who Has This Problem
- Corporate CFOs, Finance Controllers, Chartered Accountants (CAs), and tax operations teams managing hundreds or thousands of monthly vendor invoices across SAP, Tally, or Zoho Books.

### Why It Matters
When internal books and government records do not match:
1. **Financial Penalties:** Claiming missing or incorrect ITC incurs an **18% per annum mandatory interest charge** plus up to **100% tax penalty**.
2. **Blocked Working Capital:** If tax authorities flag discrepancies, company input credits are frozen.
3. **Manual Audit Exhaustion:** Accountants currently spend 40–80 hours each month manually cross-referencing messy Excel sheets, leading to human fatigue and missed errors.

---

## 3. Solution

The **GST Reconciliation Tool** automates the end-to-end reconciliation process in seconds:
- Ingests messy vendor purchase registers and government portal files in **both CSV and multi-page PDF formats**.
- Normalizes messy vendor names and ERP invoice formatting (e.g., `INV/24-25/0043` vs. `43`).
- Performs sub-millisecond vectorized matching for exact transactions with zero AI cost.
- Utilizes **Rapidfuzz candidate blocking** to filter candidate matches without quadratic performance slowdowns.
- Uses **Google Gemini 2.5 Flash** strictly as an intelligent auditor for ambiguous edge cases to classify discrepancy types and provide plain-language explanations.
- Enforces strict **Python `Decimal` arithmetic** to compute the exact rupee figure of **Total ITC at Risk**.
- Provides a **Human Review Queue** for low-confidence rows (< 80%), allowing tax teams to approve or block credits with live metric recalculations.

---

## 4. How the System Works (Architecture Flow)

```text
       [ User Uploads: Purchase Register & GSTR-2B (PDF / CSV) ]
                                   │
                                   ▼
             [ React 18 + Vite Frontend Dashboard ]
                                   │  HTTP POST /api/reconcile
                                   ▼
              [ FastAPI Backend (Python 3.10+) ]
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
      [ PDF Parser (pdfplumber) ]           [ CSV Parser (Pandas) ]
                 └─────────────────┬─────────────────┘
                                   ▼
             [ Stage 1: Vectorized Cleaning & Normalization ]
             - Corporate suffix removal (Pvt Ltd, LLP)
             - Last-segment invoice serial extraction
                                   │
                                   ▼
             [ Stage 2: Deterministic Exact Match (Pandas) ]
             - Matches GSTIN + Normalized Invoice No + Amount
             - Resolves 75%–85% of invoices in < 30ms (0 API calls)
                                   │
                                   ▼
             [ Stage 3: Blocked Rapidfuzz Candidate Search ]
             - Blocks by GSTIN / State prefix
             - Unmatched with no candidates -> MISSING_IN_2B
                                   │
                                   ▼
             [ Stage 4: Gemini 2.5 Flash AI + SQLite Cache ]
             - SHA-256 hash lookup in SQLite cache
             - Batched JSON evaluation (~10 rows/call)
             - Classifies: RATE_MISMATCH, AMOUNT_DIFF, WRONG_PERIOD, etc.
                                   │
                                   ▼
             [ Stage 5: Strict Python Decimal Audit & Risk Calc ]
             - Mathematical summation of tax in unverified rows
             - Confidence < 80% tagged for Human Review Queue
                                   │
                                   ▼
       [ Frontend: Dashboard KPI Cards, Recharts, Review Queue & CSV Export ]
```

---

## 5. AI Components

### 1. Google Gemini 2.5 Flash
- **Role:** Evaluates ambiguous candidate pairs (e.g., slight invoice typos, vendor legal name shifts, timing differences).
- **Why Gemini 2.5 Flash:** Selected for sub-second inference latency, low token cost, and strict compliance with structured JSON schema.

### 2. Structured JSON Prompt Contract
- Located at `backend/prompts/match_prompt.txt`.
- Forces Gemini to return a strict JSON array where each object contains:
  - `is_same_invoice`: Boolean
  - `confidence`: Integer between 0 and 100
  - `mismatch_type`: Strict enum (`NONE`, `AMOUNT_DIFF`, `RATE_MISMATCH`, `WRONG_PERIOD`, `NAME_DIFF`)
  - `audit_explanation`: One clear, factual sentence explaining the discrepancy.

### 3. Zero-Arithmetic Mandate (The Cardinal Rule)
- **The AI NEVER performs mathematical calculations.** Tax differences, rupee subtractions, and portfolio risk sums are executed 100% in Python using `decimal.Decimal`.

### 4. SQLite Row-Hash Caching
- Generates a SHA-256 cryptographic hash of the query and candidate row data.
- If the same transaction was audited previously, the decision is loaded from SQLite in < 1ms with zero API cost.

### 5. Resilient Offline Heuristic Fallback
- If the Gemini API key is missing or the external network fails, the system automatically falls back to a deterministic string-similarity heuristic, guaranteeing the application never crashes.

---

## 6. Under the Hood: Step-by-Step Execution

1. **Ingestion:** User drops files into the UI. The backend inspects file headers. If PDF, `pdfplumber` iterates over every page, cleans comma-formatted numbers, validates 15-digit GSTINs, and builds a standardized DataFrame.
2. **Normalization:** Supplier names have corporate tokens stripped (`Tata Consultancy Services Ltd` &rarr; `TATA CONSULTANCY SERVICES`). Invoice numbers have prefixes and financial years stripped, extracting the final serial digits (`INV/24-25/0043` &rarr; `43`).
3. **1-to-1 Exact Matching:** A stateful matcher pairs rows by GSTIN and normalized invoice number. Once a GSTR-2B row is matched, its ID is consumed into a set. If a second purchase row references the same 2B record, it is immediately flagged as `DUPLICATE_IN_BOOKS`.
4. **Discrepancy Hierarchy:** If GSTIN and invoice match but fields diverge, the system checks:
   - Tax rate difference &rarr; `RATE_MISMATCH`
   - Taxable value / total amount drift > ₹1.00 &rarr; `AMOUNT_DIFF`
   - Filing month shift &rarr; `WRONG_PERIOD`
   - Corporate name variation &rarr; `NAME_DIFF`
5. **AI Batch Audit:** PR rows without exact matches are matched against shortlisted candidates via Rapidfuzz. Cache misses are batched and evaluated by Gemini 2.5 Flash.
6. **Financial Aggregation:** Python sums the total tax of all rows with `status != MATCHED`. Invoices in GSTR-2B that were never in the purchase register are categorized as `EXTRA_IN_2B` (informative, ₹0.00 risk).
7. **Delivery:** The structured JSON payload returns summary metrics, supplier risk rankings, discrepancy counts, and complete row records to the React dashboard.

---

## 7. Core Features

| Feature | Description | Business Value |
|:---|:---|:---|
| **Multi-Format Ingestion** | Supports CSV and multi-page PDF files interchangeably. | Users do not need manual format conversions. |
| **8-Category Discrepancy Taxonomy** | Classifies into `NONE`, `MISSING_IN_2B`, `AMOUNT_DIFF`, `RATE_MISMATCH`, `DUPLICATE_IN_BOOKS`, `WRONG_PERIOD`, `EXTRA_IN_2B`, and `NAME_DIFF`. | Precise root-cause categorization for tax notices. |
| **Exact Rupee ITC at Risk** | High-precision `Decimal` summation of vulnerable tax credits. | Protects finance teams from tax audit penalties. |
| **Interactive Review Queue** | Side-by-side audit card for rows with confidence < 80% with 1-click Approve / Reject actions. | Keeps the human auditor in full control. |
| **Supplier Risk Visualizer** | Recharts bar graph ranking top vendors by ITC at risk in Rupees. | Helps procurement prioritize vendor payment holds. |
| **One-Click Audit Export** | Exports the complete reconciliation ledger with audit findings to CSV. | Ready for filing or sharing with suppliers. |

---

## 8. Demo Walkthrough (For the 20-Minute Interview)

Follow this exact sequence during screen-share:

1. **Open Application (30 seconds):** Show the pure-white responsive dashboard at `http://127.0.0.1:5173`. Point out the clean navigation (Upload, Dashboard, Invoices, Review Queue).
2. **Upload Test Files (1 minute):** Drop in the sample Purchase Register PDF (41 rows, 2 pages) and GSTR-2B PDF (39 rows, 2 pages). Click **"Run Reconciliation Audit"**.
3. **Show Dashboard KPI Summary (2 minutes):**
   - Point out **Total Invoices (41)**, **Matched vs. Mismatched**.
   - Highlight **Total ITC at Risk: ₹38,047.00** (emphasize this is computed strictly by Python `Decimal`, not AI).
4. **Explore Discrepancy Categories (2 minutes):**
   - Click the **Discrepancy Category Breakdown** cards (e.g., `RATE_MISMATCH`, `DUPLICATE_IN_BOOKS`, `MISSING_IN_2B`).
   - Show how clicking a category instantly filters the live invoice table.
5. **Demonstrate Human Review Queue (3 minutes):**
   - Navigate to the **Review Queue** tab.
   - Show the side-by-side comparison card: Company Purchase Register vs. GSTR-2B Supplier Filing with the AI audit finding.
   - Click **"Approve Match"** on a test row and demonstrate how the dashboard's Total ITC at Risk recalculates live.
6. **Export & Conclude (1 minute):** Click **"Export Report (CSV)"** to show the final auditor-ready spreadsheet.

---

## 9. My Contribution

- **End-to-End Architecture & Implementation:** Built the full application from scratch, including the FastAPI backend and React frontend.
- **Dual-Engine PDF Parser:** Implemented multi-page extraction using `pdfplumber`, automatic table grid detection, dynamic column mapping, comma stripping, and schema validation.
- **Deterministic 1-to-1 Matching Engine:** Engineered the stateful matching pipeline, normalization regexes, and cardinality tracking to catch duplicate claims.
- **AI Integration & Prompt Design:** Authored the structured prompt, integrated the official `google-genai` SDK, built SQLite query-caching, and created the offline heuristic fallback.
- **Frontend Design & Optimization:** Built a clean, light-themed, full-screen React UI using Tailwind CSS, Recharts for data visualization, and an interactive auditor review queue.

---

## 10. Outcome

- **100% Ground Truth Accuracy:** Achieved **100% status matching accuracy** and **100% mismatch categorization accuracy** against official audit answer keys (`3_answer_key.csv`).
- **Exact Rupee Risk Calculation:** Pinpointed the exact **₹38,047.00 ITC at risk** down to 0 paise variance.
- **Large-Scale Performance Benchmark:** Evaluated across 15 reproducible datasets (4,715 invoices):
  - Weighted status accuracy: **93.64%**
  - Processing runtime for 1,000 invoices: **< 3.2 seconds**
- **100% Automated Test Suite:** Unit tests for text normalization, exact matching, and financial arithmetic pass cleanly in Pytest.

---

## 11. Questions They May Ask (And Crisp Answers)

### Q1: Why did you separate exact matching from AI matching?
> *"In a typical enterprise purchase ledger, 75% to 85% of records are either exact matches or can be normalized using simple rules. Running an LLM on clean records wastes time, money, and tokens. Vectorized Pandas merges resolve 80% of rows in under 30 milliseconds. Gemini is only called for ambiguous edge cases, speeding up execution by over 10x."*

### Q2: Why doesn't Gemini calculate the financial amounts or tax differences?
> *"LLMs are generative and probabilistic token predictors. They can suffer from digit transposition, rounding errors, and hallucination. Under Indian tax law (Section 16(2)(aa)), being wrong by even a few rupees leads to statutory notices and penalties. Python `Decimal` arithmetic is 100% deterministic, audit-compliant, and mathematically exact."*

### Q3: How do you prevent quadratic slowdown when matching thousands of invoices?
> *"Naive string comparison across two 10,000-row datasets requires 100,000,000 pairwise comparisons ($O(N \times M)$). We implemented 'blocking' using Rapidfuzz: candidates are partitioned by GSTIN or state code prefix first. This bounds each candidate comparison pool to a handful of records, allowing 1,000 invoices to reconcile in under 3.2 seconds."*

### Q4: How does your system handle multi-page PDFs?
> *"The backend uses `pdfplumber` to iterate across all pages in the uploaded PDF. It detects table header rows, extracts cell text, strips comma formatting from currency strings, converts numbers using `Decimal`, and fails loudly if required fields like GSTIN or amounts are empty. The extracted records are transformed into an in-memory Pandas DataFrame without temporary disk writes."*
