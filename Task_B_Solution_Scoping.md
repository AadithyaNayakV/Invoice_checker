# Task B: Solution Scoping — GST Reconciliation Tool

> **Candidate Showcase Artifact** | 20-Minute Interview Presentation  
> **Topic:** How I Scoped, Designed, and Architected an AI-Assisted Compliance Solution  
> **Project:** GST Reconciliation Tool & Compliance Auditor  

---

## 1. Problem Statement

Under India's Goods and Services Tax (GST) regime, businesses can only claim **Input Tax Credit (ITC)** on vendor purchases if their suppliers have properly filed those invoices on the government GST portal (**GSTR-2B**). 

In practice, company internal accounting books (**Purchase Registers**) and government portal files (**GSTR-2B**) diverge significantly due to:
- Diverse ERP invoice numbering schemes (e.g., `INV/23-24/0043` vs. `43`)
- Vendor legal name variations (e.g., `Tata Consultancy Services Ltd` vs. `TATA CONSULTANCY SERVICES PRIVATE LIMITED`)
- Tax rate discrepancies (e.g., 12% vs. 18%)
- Amount rounding and data entry errors
- Unfiled supplier invoices (`MISSING_IN_2B`)

If an organization claims credit on unfiled or mismatched invoices, **Section 16(2)(aa) of the CGST Act** mandates repayment of the tax plus an **18% per annum interest penalty**, with potential audit penalties up to 100%.

---

## 2. User & Customer Need

### Target Users
1. **Corporate Finance Controllers & CFOs:** Need high-level visibility into total financial exposure, supplier compliance risk, and potential working capital blockage.
2. **Tax Managers & Chartered Accountants (CAs):** Need automated monthly reconciliation that replaces 40–80 hours of manual Excel VLOOKUPs with instant, verifiable audit trails.
3. **Accounts Payable (AP) Teams:** Need a prioritized list of non-compliant suppliers to withhold payment or issue debit notes before tax filing deadlines.

### Core User Needs
- **Multi-Format Ingestion:** Accept raw exports from ERPs (SAP, Tally, Zoho) and the GST portal without requiring pre-formatting into a rigid template.
- **Deterministic Mathematical Precision:** Financial totals and tax penalties must be calculated with 100% precision. Probabilistic LLM arithmetic is unacceptable in accounting.
- **Explainable Discrepancy Classification:** Rather than a binary "match/no match", users need clear categorization (e.g., rate mismatch vs. timing difference) with a plain-language audit reason.
- **Human Authority:** Tax teams must retain final sign-off authority on ambiguous invoices before credits are permanently disallowed or claimed.

---

## 3. Goals

| Goal | Success Metric |
|:---|:---|
| **High Reconciliation Accuracy** | Achieve > 90% accuracy on status matching and discrepancy categorization across real-world edge cases. |
| **Zero Financial Hallucination** | 0.00% arithmetic variance on calculated tax liabilities. All math executed via Python `Decimal`. |
| **High-Throughput Scalability** | Process up to 1,000 invoices in under 5.0 seconds on standard compute. |
| **Cost & Token Efficiency** | Minimizing LLM token usage by resolving > 75% of clean records through deterministic rules first. |
| **Zero-Crash Resilience** | The system must never crash if an external API key is missing or internet connectivity drops. |

---

## 4. Requirements

### Functional Requirements
- **FR-1 Multi-Format File Ingestion:** Ingest Purchase Register and GSTR-2B datasets in either `.csv` or multi-page `.pdf` formats.
- **FR-2 Data Normalization:** Standardize column headers, strip corporate legal suffixes (`Pvt Ltd`, `LLP`), and extract the core serial segment from invoice strings.
- **FR-3 1-to-1 Cardinality Matching:** Enforce strict one-to-one invoice pairing to detect and flag `DUPLICATE_IN_BOOKS`.
- **FR-4 Discrepancy Taxonomy:** Categorize every invoice into one of 8 distinct categories (`NONE`, `MISSING_IN_2B`, `AMOUNT_DIFF`, `RATE_MISMATCH`, `DUPLICATE_IN_BOOKS`, `WRONG_PERIOD`, `EXTRA_IN_2B`, `NAME_DIFF`).
- **FR-5 Financial Risk Quantification:** Calculate exact Total ITC at Risk in Indian Rupees (₹).
- **FR-6 Human-in-the-Loop Review:** Automatically route decisions with confidence < 80% to a Review Queue with 1-click Approve/Reject actions.
- **FR-7 Audit Report Export:** Enable single-click download of the complete reconciliation ledger in CSV format.

### Technical Requirements
- **TR-1 Asynchronous REST Backend:** Built using Python 3.10+ and FastAPI.
- **TR-2 Modern Responsive Frontend:** Built using React 18, Vite, and Tailwind CSS.
- **TR-3 Scalable Fuzzy Blocking:** Implement Rapidfuzz with GSTIN and state-code partitioning to prevent $O(N \times M)$ slowdowns.
- **TR-4 LLM Integration:** Google Gemini 2.5 Flash via the official `google-genai` SDK with strict JSON schema response validation.
- **TR-5 Cache Layer:** SQLite database storing SHA-256 row-pair hashes to eliminate redundant API calls.
- **TR-6 Deterministic Arithmetic:** All monetary fields must use Python `decimal.Decimal` with standard `ROUND_HALF_UP` banking rules.

---

## 5. Proposed Solution: The Hybrid Architectural Model

Rather than choosing between a brittle 100% rules-based script and an expensive, unpredictable 100% LLM approach, I designed a **5-Stage Hybrid Pipeline**:

1. **Stage 1 (Vectorized Cleaning):** Deterministic Pandas rules strip corporate legal noise and isolate numeric invoice serials.
2. **Stage 2 (Deterministic Exact Match):** High-speed Pandas inner-join on `(GSTIN + Normalized Invoice No + Amount)` resolves 75%–85% of clean transactions in milliseconds with **zero LLM cost**.
3. **Stage 3 (Blocked Fuzzy Retrieval):** Rapidfuzz shortlists top-3 candidates strictly within the same GSTIN or state prefix, dropping search space by > 95%.
4. **Stage 4 (Gemini 2.5 Flash AI Auditor):** Gemini evaluates only the remaining edge cases. It assigns a confidence score, tags the discrepancy type, and outputs a one-sentence rationale.
5. **Stage 5 (Python Mathematical Audit & Review Queue):** Python computes exact risk sums and sends low-confidence items to human accountants for final sign-off.

---

## 6. Architecture Diagram

```text
[Input: CSV / PDF Files] ─────────► [pdfplumber & Pandas Ingestion Engine]
                                                │
                                                ▼
[Stage 1: Data Normalization] ────► Strip corporate suffixes & isolate serial invoice digits
                                                │
                                                ▼
[Stage 2: Vectorized Exact Match] ► Fast join on (GSTIN + Inv + Amt) [Resolves 80% @ 0 AI cost]
                                                │
                                                ▼
[Stage 3: Blocked Fuzzy Search] ──► Rapidfuzz shortlist by GSTIN/State [Drops search space >95%]
                                                │
                                                ▼
[Stage 4: Gemini 2.5 Flash AI] ───► Evaluates edge cases + SQLite Cache (Strict JSON array)
                                                │
                                                ▼
[Stage 5: Python Decimal Audit] ──► Exact Rupee ITC at risk calculation + 1-to-1 state tracking
                                                │
                                                ▼
[React 18 + Tailwind UI Layer] ───► KPI Summary Cards, Recharts, Review Queue & CSV Export
```

---

## 7. Technology Choices & Evaluation Matrix

### Decision 1: Arithmetic Execution Engine
- **Technology Selected:** Python `decimal.Decimal` (Local execution)
- **Why:** Financial audits require 100% deterministic reproducibility. Accounting law allows zero margin for calculation error.
- **Alternative Considered:** Prompting the LLM to calculate the rupee tax variance directly.
- **Trade-off:** Requires writing strict Python formula handlers for each mismatch type, but eliminates hallucination and floating-point rounding bugs entirely.

### Decision 2: LLM Model Selection
- **Technology Selected:** Google Gemini 2.5 Flash (via `google-genai` SDK)
- **Why:** Ultra-low inference latency (~300–600ms), cheap token pricing, native structured JSON schema mode, and sufficient reasoning capability for transaction auditing.
- **Alternative Considered:** Gemini 1.5 Pro or GPT-4o.
- **Trade-off:** Pro models have slightly higher reasoning depth for complex unstructured text, but cost 10x more and add 2–4 seconds of latency per call, which is unacceptable for large ledger batches.

### Decision 3: Candidate Retrieval Algorithm
- **Technology Selected:** Rapidfuzz with GSTIN/State Blocking
- **Why:** C++ optimized Levenshtein and token sort ratios provide sub-millisecond comparisons while blocking confines matching to relevant vendors.
- **Alternative Considered:** Vector embeddings with a vector database (e.g., ChromaDB, Pinecone).
- **Trade-off:** Vector embeddings excel at semantic similarity (e.g., synonyms), but perform poorly on alphanumeric codes and invoice numbers where a single character difference (`0043` vs. `0048`) matters immensely.

### Decision 4: Caching Layer
- **Technology Selected:** Embedded SQLite (`gst_reconcile.db`)
- **Why:** Serverless, zero-configuration, persists between runs, and requires zero external infrastructure.
- **Alternative Considered:** Redis in-memory cache.
- **Trade-off:** Redis is better suited for multi-server distributed clusters, but introduces unnecessary DevOps overhead for single-instance enterprise accounting deployments.

### Decision 5: Frontend Framework
- **Technology Selected:** React 18 + Vite + Tailwind CSS
- **Why:** Delivers an instant, crisp, enterprise-grade user interface with fast client-side sorting, filtering, and tab transitions.
- **Alternative Considered:** Streamlit or Gradio.
- **Trade-off:** Streamlit allows faster initial prototyping in Python, but forces full-page re-renders on every interaction, making interactive table filtering and review queues feel sluggish.

---

## 8. AI Design Decisions

1. **Why Use AI at All?**
   - Traditional regex or fuzzy matching fails on real-world edge cases where invoice formats shift dynamically (e.g., `FY24/INV/9` vs. `09`), vendor names contain brand aliases, or tax periods cross calendar months. Gemini provides human-like contextual judgment for these edge cases.
2. **Prompt Engineering & Schema Enforcement:**
   - The prompt (`match_prompt.txt`) instructs the model to act as a **Senior GST Compliance Auditor**.
   - Output is strictly constrained to a JSON schema:
     ```json
     [
       {
         "pr_row_id": "PR_1",
         "best_match_id": "2B_1",
         "confidence": 95,
         "mismatch_type": "AMOUNT_DIFF",
         "explanation": "Supplier filed invoice with ₹500 higher taxable value."
       }
     ]
     ```
3. **Batching Strategy:**
   - Unmatched rows are batched in groups of ~10 per API call. This reduces HTTP request round-trips by 90% and keeps API consumption well within free-tier rate limits.
4. **Offline Heuristic Fail-Safe:**
   - If the API key is not configured or an outage occurs, an internal heuristic classifier automatically assumes audit duties based on Rapidfuzz token sort scores, guaranteeing uninterrupted operation.

---

## 9. Scoping Trade-offs

| Trade-off Dimension | Choice Made | Rationale |
|:---|:---|:---|
| **Speed vs. Exhaustive Search** | Blocked Fuzzy Search over Global Cross-Product | Comparing 5,000 PR rows against 5,000 2B rows is 25,000,000 comparisons. Blocking by GSTIN drops this to < 10,000 comparisons, speeding execution by 2,500x. |
| **Cost vs. Model Capability** | Gemini 2.5 Flash over Gemini Pro | Flash handles structured table auditing with 93%+ accuracy at a fraction of the cost and 4x faster speed. |
| **Automation vs. Audit Control** | Human-in-the-Loop for Confidence < 80% | Fully autonomous tax filing is dangerous. Flagging uncertain rows for manual review maintains legal audit safety. |
| **Local Determinism vs. Cloud AI** | Hybrid Local/Cloud Split | Sensitive financial totals remain on local compute (Python `Decimal`); only anonymized candidate pairs are transmitted to the LLM. |

---

## 10. Project Outcome

- **Benchmarked Quality:** Verified across 15 reproducible datasets (4,715 invoices):
  - Overall status accuracy: **93.64%**
  - Mismatch categorization accuracy: **91.94%**
  - Processing runtime for 1,000 invoices: **< 3.2 seconds**
- **Ground Truth Challenge:** Achieved **100% accuracy** on the official benchmark sample (`3_answer_key.csv`), identifying the exact **₹38,047.00** total ITC at risk.
- **Enterprise Usability:** Replaced 40+ hours of monthly manual accountant labor with a 3-second automated run followed by a 10-minute review queue sign-off.

---

## 11. What I Would Improve (Future Roadmap)

1. **Direct GST Portal API Integration:** Integrate with official GST Suvidha Providers (GSPs) to pull GSTR-2B data directly via government APIs, removing the need for manual file downloads.
2. **Multimodal OCR for Paper Invoices:** Extend Gemini's vision capabilities to extract structured invoice data directly from camera photos and scanned paper bills.
3. **Automated Supplier Dispute Notice Generator:** Add an automated workflow that generates formal, email-ready PDF dispute letters to vendors whose missing invoices are blocking company tax credits.
