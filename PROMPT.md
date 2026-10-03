You are a senior full-stack engineer. Build a complete project from scratch in an empty folder. I have nothing yet, so create every file, including the fake data. Explain simply in comments because I am a student and must be able to explain every part in an interview.

PROJECT NAME: GST Reconciliation Tool

WHAT IT DOES (simple):
A company has two lists of the same purchases:
- List 1 = Purchase Register (the company's own books)
- List 2 = GSTR-2B (what suppliers reported to the government)
They should match but often don't (different name spelling, different invoice number format, wrong amount, supplier didn't report). The tool compares both lists, finds mismatches, explains each one, and shows the total tax refund (ITC) at risk in rupees.

TECH STACK (everything must be free, no paid services):
- Backend: Python 3.11+, FastAPI, pandas, rapidfuzz, google-genai (Gemini API), SQLite, python-dotenv
- Frontend: React + Vite + Tailwind CSS (no Next.js, no TypeScript)
- AI: Gemini API. Read the model name from .env (GEMINI_MODEL, default gemini-2.5-flash) so I can swap models by changing one line. Read the key from GEMINI_API_KEY in .env. Never hardcode keys. Provide .env.example.

CORE RULE (very important):
Python does all exact matching and ALL money calculations. The AI only handles the messy leftovers and NEVER does arithmetic. Humans review low-confidence results.

BACKEND PIPELINE (put this logic in backend/reconcile.py, separate from the API file, so it is reusable):
1. Load both CSV files with pandas and clean them: uppercase names, remove "PVT LTD / PRIVATE LIMITED / LTD", strip spaces and punctuation, normalize invoice numbers (remove prefixes like INV/, slashes, leading zeros).
2. EXACT MATCH: match on (supplier GSTIN + normalized invoice number + amount). Mark these "MATCHED". No AI used.
3. For each unmatched row, use rapidfuzz to shortlist the top 3 candidates from the other list (same GSTIN or similar name, similar amount, close date).
4. If a row has no candidate at all, mark it "MISSING_IN_2B" without calling AI.
5. For rows with candidates, call Gemini IN BATCHES (about 10 rows per call, not one call per row). Ask it to return STRICT JSON only: [{"row_id":..., "best_candidate_id": ... or null, "same_invoice": true/false, "confidence": 0-100, "mismatch_type": "AMOUNT_DIFF|RATE_MISMATCH|DATE_PERIOD|NAME_DIFF|MISSING_IN_2B|NONE", "reason": "one short sentence"}]
6. Add retry (max 3), a timeout, JSON-validation, and rate-limit handling with a small delay so the free tier does not break. If Gemini fails, fall back to the rapidfuzz result and mark it "NEEDS_REVIEW". The app must never crash because of the AI.
7. Cache AI answers in SQLite (key = hash of the two rows) so repeat runs cost nothing.
8. If confidence is below 80, status = "NEEDS_REVIEW". Otherwise AI result is accepted.
9. Python calculates: total ITC at risk (sum of tax of problem rows), ITC at risk grouped by supplier, and counts per status. Use pandas/Decimal, never the AI.

API ENDPOINTS (FastAPI, with CORS enabled for the React dev server):
- POST /api/reconcile  (upload two CSV files, returns summary + all rows)
- POST /api/review     (human confirms or rejects a NEEDS_REVIEW row, recalculates totals)
- GET  /api/sample/{n} (loads built-in sample pair number n so I can demo without uploading)
- GET  /api/export     (download results as CSV)
- GET  /api/health

FRONTEND (React, clean and simple, responsive):
- Upload page: two file drop zones + "Use sample data" dropdown + Run button with loading state and progress text.
- Dashboard: big card "Total ITC at risk (₹)", cards for Matched / Needs Review / Mismatched counts, a bar chart of ITC at risk by supplier (use recharts).
- Results table: filter by status, search by supplier, shows the AI reason and confidence badge.
- Review queue: for NEEDS_REVIEW rows, side-by-side view of the two rows with Approve / Reject buttons. Totals update live.
- Download CSV button. Show friendly error messages.

FAKE DATA (create backend/data/generate_data.py and run it so files exist):
- Generate 15 sample pairs (sample_01 ... sample_15). Each pair has purchase_register.csv, gstr2b.csv and answer_key.csv.
- Sizes vary: some 30 rows, some 200, a few 1000 rows.
- Use realistic Indian supplier names, valid-format fake GSTINs (15 characters), invoice dates in a single financial year, GST rates 5/12/18/28 percent, invoice number, taxable value, CGST/SGST/IGST amounts.
- Plant these mismatches on purpose, with known answers saved in answer_key.csv: name spelling differences (Pvt Ltd vs PRIVATE LIMITED), invoice number format differences (INV/23-24/0045 vs 45), small amount differences, wrong GST rate, supplier did not report (missing in 2B), invoice in the wrong month, and some duplicate invoices.
- Make about 75-85 percent of rows match exactly, and the rest have planted problems.
- Use a fixed random seed so data is reproducible.

EVALUATION (backend/evaluate.py):
Run the pipeline on all 15 samples, compare with answer_key.csv, and print accuracy, precision, recall per mismatch type, and total ITC-at-risk error versus the true value. Save the results to evaluation_results.md. This is my proof of quality.

OPTIMIZATION (apply all of these):
- Do vectorized pandas matching for the exact step (no Python loops over rows).
- Use rapidfuzz process.extract with blocking (only compare rows with same GSTIN or same first letters) so 1000 rows stay fast.
- Batch AI calls, cache results, and send only the minimum columns to the AI to save tokens.
- Keep the AI prompt short and put the instructions in a separate file backend/prompts/match_prompt.txt.
- Add logging with timing for each stage.
- Add a small pytest test file for normalization, exact matching, and the money calculation.

DELIVERABLES:
- Folder structure: /backend (main.py, reconcile.py, ai_matcher.py, db.py, evaluate.py, prompts/, data/, tests/, requirements.txt, .env.example) and /frontend (Vite React app).
- README.md with: what the project is in simple words, architecture diagram in text, setup steps for Windows, how to get the Gemini key, how to run backend (uvicorn) and frontend (npm run dev), how to run the evaluation, and a "Limitations and next steps" section (PDF input, MCP tool, vendor email drafts).
- Install dependencies, run the data generator, start both servers, run the tests, run the evaluation, and fix any errors until everything works end to end. Tell me the final URLs and commands.
- Initialize git and make small, meaningful commits step by step so the history shows how it was built.

Keep the code simple, readable, and well commented. Do not over-engineer. No chatbot features.