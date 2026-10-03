# GST Reconciliation Tool 📊🇮🇳

> **An AI-Assisted, Deterministic Indian GST Reconciliation Engine**  
> Compares company internal **Purchase Registers (PR)** with supplier **GSTR-2B** government portal records, flags discrepancies, calculates Input Tax Credit (ITC) at risk in Indian Rupees (₹), and provides an interactive auditor review queue.

---

## 1. What This Project Does (In Simple Words)

In India, when a business buys goods or services, it pays Goods and Services Tax (GST) to the seller. The business can claim this tax back from the government as **Input Tax Credit (ITC)**—*but only if the seller actually reports that invoice on the government GST portal (GSTR-2B)*.

Every month, finance teams must compare two separate lists of purchases:
1. **List 1: Purchase Register (PR)** — The company’s internal accounting books (what we bought).
2. **List 2: GSTR-2B** — The official government tax portal records (what suppliers reported they sold us).

In the real world, these two lists almost never match cleanly because:
- **Supplier name variations**: `Tata Consultancy Services Ltd` vs `TATA CONSULTANCY SERVICES PRIVATE LIMITED`.
- **Invoice number formatting differences**: ERP systems format invoice numbers differently (e.g., `INV/23-24/0045` vs `45` vs `23-24/45`).
- **Wrong amounts or rounding**: Supplier keyed in ₹11,500 instead of ₹11,800.
- **Wrong GST tax rate**: Charged 12% instead of 18%.
- **Wrong tax period / month**: Invoice dated in May, but supplier uploaded it in July.
- **Missing invoices**: Supplier completely forgot to file the invoice.

### Why This Tool Matters:
If a company claims ITC for an invoice that is missing or incorrect in GSTR-2B, the government charges hefty interest (18% p.a.) and penalty under Section 16(2)(aa) of the CGST Act.  
This tool **automates the reconciliation in seconds**, pinpoints exactly how much ITC is at risk in Rupees, and provides human auditors with a live review interface.

---

## 2. Core Architectural Principle

> ⚖️ **The Cardinal Rule**:  
> **Python does ALL exact matching and ALL financial arithmetic. The AI only handles messy textual variations and NEVER performs arithmetic.**

```
+-----------------------------------------------------------------------------------+
|                            CSV INPUTS (PR & GSTR-2B)                              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 1: Vectorized Data Cleaning & Preprocessing (Pandas)                        |
| - Strips corporate entity suffixes (Pvt Ltd, Private Limited, LLP, etc.)          |
| - Standardizes invoice numbers (strips prefixes, slashes, dashes, leading zeros)  |
| - Validates and normalizes financial columns (Decimal currency rounding)          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 2: Vectorized Exact Match (Fast Pandas Merge)                               |
| Key: (Supplier GSTIN + Normalized Invoice No + Exact Amount)                      |
| -> Resolves 75% to 85% of invoices in milliseconds with ZERO AI calls!            |
| -> Marked as MATCHED, ITC at Risk = ₹0.00                                         |
+-----------------------------------------------------------------------------------+
                                         |
                     [Unmatched Invoices Remaining]
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 3: Blocked Rapidfuzz Candidate Shortlisting                                 |
| - Blocking on same GSTIN or same State Code / Name prefix (scalable to 10k rows)   |
| - Scores invoice numbers, names, and amounts using token sort ratio               |
| - If no candidate exists at all -> Immediate MISSING_IN_2B (no AI needed)         |
| - If candidate exists -> Shortlists Top 3 candidate rows                          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 4: Gemini AI Batch Evaluation + SQLite Caching                              |
| - Check SQLite cache (hash of query + candidate rows)                             |
| - Batch remaining cache misses (~10 items per Gemini API call)                    |
| - Structured JSON Prompt (prompts/match_prompt.txt) -> Strict JSON array          |
| - Confidence Score (0-100) and Discrepancy Classification                        |
| - Fallback: Built-in offline heuristic if API key is not yet set or API fails     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| STAGE 5: Strict Python Financial Audit & Human Review Queue                       |
| - Confidence >= 80% -> Decision accepted                                          |
| - Confidence < 80%  -> Tagged as NEEDS_REVIEW (requires auditor sign-off)         |
| - Python calculates Total ITC at Risk (sum of tax in problem rows) via Decimal    |
| - Generates supplier risk rankings and discrepancy breakdowns                     |
+-----------------------------------------------------------------------------------+
```

---

## 3. Technology Stack (100% Free & Open Source)

- **Backend**:
  - **Python 3.10+ / 3.11+**
  - **FastAPI**: Modern, asynchronous web framework with OpenAPI documentation
  - **Pandas**: Vectorized exact matching and financial data manipulation
  - **Rapidfuzz**: High-speed C++ based fuzzy string comparison with blocking
  - **google-genai**: Official Google Gemini SDK for LLM discrepancy auditing
  - **SQLite**: Zero-configuration embedded database for caching AI decisions
  - **python-dotenv**: Environment variable isolation
  - **Pytest**: Automated testing suite

- **Frontend**:
  - **React 18** (Vite build system, Vanilla JavaScript)
  - **Tailwind CSS**: Modern dark-mode styling with glassmorphism
  - **Lucide React**: Clean, accessible vector icons
  - **Recharts**: Interactive SVG charts visualizing ITC at risk by supplier

---

## 4. Setup Steps for Windows

### Prerequisites
1. **Python 3.10 or 3.11+**: Ensure Python is installed and added to PATH.
2. **Node.js 18+ or 20+**: Ensure `node` and `npm` are installed.

### Step 1: Clone or Open the Workspace
```powershell
cd c:\Users\aadit\OneDrive\Desktop\GST_INVOICE
```

### Step 2: Set Up Python Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r backend/requirements.txt
```

### Step 3: Install Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

### Step 4: Configure Gemini API Key (Optional)
The project includes a robust offline heuristic fallback, so you can run and test everything immediately even without an API key!

To enable real Gemini 2.5 Flash calls:
1. Get a free API key at [Google AI Studio](https://aistudio.google.com/).
2. Open `backend/.env` (or copy `.env.example` to `.env`):
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
PORT=8000
HOST=127.0.0.1
```

---

## 5. How to Run

### Run the Backend (FastAPI + Uvicorn)
From the project root:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```
- API Base URL: `http://127.0.0.1:8000`
- Interactive API Docs (Swagger): `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/api/health`

### Run the Frontend (Vite Dev Server)
In a second terminal window:
```powershell
cd frontend
npm run dev
```
- Open your browser at: `http://localhost:5173`

---

## 6. How to Run the Tests & Evaluation

### Run Automated Unit Tests (Pytest)
Tests text normalization, invoice number handling, vectorized exact matching, and financial calculations:
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_reconcile.py -v
```

### Run the 15-Dataset Benchmark Evaluation
Executes the reconciliation pipeline across all 15 reproducible datasets (sample_01 to sample_15) and generates `evaluation_results.md`:
```powershell
.\.venv\Scripts\python.exe backend/evaluate.py
```

### Evaluation Benchmark Highlights:
- **Total Invoices Audited**: `4,715`
- **Weighted Status Accuracy**: `93.64%`
- **Weighted Mismatch Categorization Accuracy**: `91.94%`
- **Runtime on 1,000 Invoices**: `< 3.2 seconds`

---

## 7. API Endpoints Reference

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/api/health` | Returns server health, active Gemini model, and mode. |
| `POST` | `/api/reconcile` | Upload two CSV files (`pr_file`, `gstr2b_file`). Returns audit summary and rows. |
| `GET` | `/api/sample/{n}` | Loads pre-generated sample pair `n` (1-15) for instant demo. |
| `POST` | `/api/review` | Human auditor confirms (`APPROVE`) or flags (`REJECT`) a `NEEDS_REVIEW` row. Recalculates totals live. |
| `GET` | `/api/export` | Downloads the current reconciliation audit session as a CSV file. |
| `POST` | `/api/export` | Downloads specific filtered or reviewed rows as a CSV file. |

---

## 8. Limitations & Next Steps

1. **PDF / Scanned Invoice Input**:
   - *Limitation*: Currently consumes structured CSV files exported from ERP systems (Tally, SAP, Zoho Books) and the GST Portal.
   - *Next Step*: Add Gemini Multimodal OCR support to parse scanned invoice PDFs or camera photos directly into structured records.
2. **MCP Tool Integration (Model Context Protocol)**:
   - *Limitation*: Requires user to trigger reconciliation via web UI or REST API.
   - *Next Step*: Package the reconciliation pipeline as a standard Model Context Protocol (MCP) server so AI agents (like Claude or Gemini Desktop) can run reconciliations directly from desktop chat prompts.
3. **Automated Vendor Email Drafts**:
   - *Limitation*: Human auditors must manually follow up with suppliers who failed to file invoices.
   - *Next Step*: Add an automated "Draft Vendor Notice" button that generates formal dispute emails with invoice details, dates, and blocked ITC amounts.

---

## 9. Interview Talking Points (Key Technical Decisions)

When explaining this project in an engineering interview, emphasize:
- **Separation of Concerns**: Python handles deterministic business logic and financial calculations using `Decimal`. LLMs are non-deterministic and should never be trusted with ledger arithmetic.
- **Scalability with Blocking**: Full fuzzy matching has $O(N \times M)$ complexity. By applying blocking (matching on GSTIN / State Code / prefix first), we keep candidate pools small, enabling 1,000-row reconciliations in under 3.2 seconds.
- **Cost & Token Optimization**: 75-85% of invoices match exactly in Stage 2. Only true edge cases reach the AI. Batched requests (~10 per call) and SHA-256 SQLite caching reduce API calls by >90%.
- **Resilience**: The system never crashes if Gemini API rate limits are hit or if the key is missing; it gracefully falls back to rapidfuzz heuristic analysis and flags low confidence for human review.
