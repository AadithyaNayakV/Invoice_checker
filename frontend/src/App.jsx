import React, { useState, useMemo } from 'react';
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  UploadCloud,
  Download,
  RefreshCw,
  Search,
  Filter,
  ArrowRight,
  ShieldCheck,
  Layers,
  TrendingUp,
  BarChart3,
  HelpCircle,
  Check,
  X,
  FileText
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  CartesianGrid
} from 'recharts';

// Format currency to Indian Rupees (INR)
const formatINR = (val) => {
  const num = Number(val) || 0;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(num);
};

// Base URL for API requests (supports local Vite proxy or deployed cloud backend)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function App() {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'dashboard' | 'review' | 'table'
  const [filePR, setFilePR] = useState(null);
  const [file2B, setFile2B] = useState(null);

  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Reconciled session data state
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [sessionMeta, setSessionMeta] = useState(null);

  // Table filtering and search state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Run reconciliation from uploaded CSVs or PDFs
  const handleUploadReconcile = async (e) => {
    e?.preventDefault();
    if (!filePR || !file2B) {
      setErrorMsg('Please upload both Purchase Register and GSTR-2B files (CSV or PDF).');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    setLoadingStep('Uploading files and standardizing columns...');

    try {
      const formData = new FormData();
      formData.append('pr_file', filePR);
      formData.append('gstr2b_file', file2B);

      setTimeout(() => setLoadingStep('Extracting tables & running vectorized exact matching...'), 350);
      setTimeout(() => setLoadingStep('Evaluating discrepancy candidates & computing ITC at risk...'), 800);

      const res = await fetch(`${API_BASE_URL}/api/reconcile`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Reconciliation failed.');
      }

      const data = await res.json();
      setSummary(data.summary);
      setResults(data.results);
      setSessionMeta({
        source: `${filePR.name} vs ${file2B.name}`,
        elapsed: data.elapsed_seconds,
        records: data.results?.length || 0,
      });
      setActiveTab('dashboard');
    } catch (err) {
      setErrorMsg(err.message || 'An error occurred during reconciliation.');
    } finally {
      setLoading(false);
      setLoadingStep('');
    }
  };

  // Human Review Queue Action (Approve / Reject)
  const handleReviewAction = async (rowId, action) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_id: rowId,
          action: action,
          results: results,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Review update failed.');
      }

      const data = await res.json();
      setSummary(data.summary);
      setResults(data.results);
    } catch (err) {
      alert(`Review error: ${err.message}`);
    }
  };

  // Export current results as CSV
  const handleExportCSV = async () => {
    if (!results || results.length === 0) {
      alert('No reconciliation results available to export.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(results),
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `GST_Reconciliation_Report_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert('Failed to export CSV: ' + err.message);
    }
  };

  // Filtered rows for Results Table
  const filteredRows = useMemo(() => {
    return results.filter((r) => {
      const matchStatus = statusFilter === 'ALL' || r.status === statusFilter;
      const matchType = typeFilter === 'ALL' || r.mismatch_type === typeFilter;
      const query = searchQuery.trim().toLowerCase();
      const matchQuery =
        !query ||
        r.supplier_name?.toLowerCase().includes(query) ||
        r.gstin?.toLowerCase().includes(query) ||
        r.invoice_number?.toLowerCase().includes(query) ||
        r.b2_invoice_number?.toLowerCase().includes(query);
      return matchStatus && matchType && matchQuery;
    });
  }, [results, statusFilter, typeFilter, searchQuery]);

  // Rows pending human review
  const pendingReviewRows = useMemo(() => {
    return results.filter((r) => r.status === 'NEEDS_REVIEW');
  }, [results]);

  // Vibrant, professional colors for bar chart
  const BAR_COLORS = ['#dc2626', '#ea580c', '#d97706', '#2563eb', '#7c3aed', '#059669'];

  return (
    <div className="min-h-screen bg-white text-slate-900 flex flex-col font-sans">
      {/* Top Navigation Bar (Full Width Light Theme) */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-40 shadow-sm">
        <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-12 h-16 flex items-center justify-between">
          {/* Logo & Project Title */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center shadow-md shadow-emerald-600/20 text-white">
              <FileSpreadsheet className="w-5 h-5 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-slate-900">GST Reconcile</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                  Compliance Auditor
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">Purchase Register vs GSTR-2B Reconciliation Engine</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center space-x-1 sm:space-x-2 bg-slate-100 p-1.5 rounded-xl border border-slate-200">
            <button
              onClick={() => setActiveTab('upload')}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition ${
                activeTab === 'upload'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              Upload Files
            </button>
            <button
              disabled={!summary}
              onClick={() => setActiveTab('dashboard')}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition flex items-center space-x-1.5 ${
                !summary ? 'opacity-40 cursor-not-allowed text-slate-400' : ''
              } ${
                activeTab === 'dashboard'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Dashboard</span>
            </button>
            <button
              disabled={!summary}
              onClick={() => setActiveTab('table')}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition flex items-center space-x-1.5 ${
                !summary ? 'opacity-40 cursor-not-allowed text-slate-400' : ''
              } ${
                activeTab === 'table'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Invoices ({results.length})</span>
            </button>
            <button
              disabled={!summary}
              onClick={() => setActiveTab('review')}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition flex items-center space-x-1.5 ${
                !summary ? 'opacity-40 cursor-not-allowed text-slate-400' : ''
              } ${
                activeTab === 'review'
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
              <span>Review Queue</span>
              {pendingReviewRows.length > 0 && (
                <span className="ml-1 bg-amber-500 text-white font-bold text-[11px] px-1.5 py-0.2 rounded-full">
                  {pendingReviewRows.length}
                </span>
              )}
            </button>
          </nav>

          {/* Action Button: Export CSV */}
          <div className="flex items-center space-x-3">
            {results.length > 0 && (
              <button
                onClick={handleExportCSV}
                className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 transition shadow-sm"
              >
                <Download className="w-4 h-4 text-emerald-600" />
                <span>Export Report (CSV)</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Full-Width Content Container */}
      <main className="flex-1 w-full bg-white px-4 sm:px-6 lg:px-8 xl:px-12 py-6">
        {/* Error notification banner */}
        {errorMsg && (
          <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 flex items-start space-x-3 shadow-sm">
            <XCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="flex-1 text-sm font-medium">{errorMsg}</div>
            <button onClick={() => setErrorMsg('')} className="text-red-500 hover:text-red-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Loading Overlay */}
        {loading && (
          <div className="fixed inset-0 bg-slate-900/30 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white p-8 rounded-2xl max-w-md w-full text-center space-y-4 shadow-xl border border-slate-200">
              <div className="w-14 h-14 mx-auto rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center animate-spin">
                <RefreshCw className="w-7 h-7 text-emerald-600" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Reconciling Ledger</h3>
              <p className="text-sm text-slate-600 font-medium">{loadingStep}</p>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div className="bg-emerald-600 h-full w-2/3 animate-pulse rounded-full" />
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 1: UPLOAD FILES (Expansive Light Theme) */}
        {/* ========================================================================= */}
        {activeTab === 'upload' && (
          <div className="w-full max-w-6xl mx-auto space-y-6">
            {/* Header Banner */}
            <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden">
              <div className="max-w-3xl space-y-2">
                <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>GST ITC Protection Suite</span>
                </span>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                  Reconcile Purchase Register vs GSTR-2B
                </h1>
                <p className="text-sm text-slate-600 leading-relaxed">
                  Upload your internal Purchase Register and the government GSTR-2B supplier filings in either <strong>CSV</strong> or <strong>PDF</strong> format.
                  The engine standardizes invoice numbers, resolves vendor legal name variants, checks tax rates, and pinpoints exact <strong>Input Tax Credit (₹)</strong> at risk.
                </p>
              </div>
            </div>

            {/* Upload Dropzones */}
            <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center border border-emerald-200">
                  <UploadCloud className="w-4 h-4 text-emerald-600" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-900">Upload Purchase & Tax Records</h2>
                  <p className="text-xs text-slate-500">Supports CSV spreadsheets or PDF statements/invoices.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Zone 1: Purchase Register */}
                <div className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition ${
                  filePR ? 'border-emerald-500 bg-emerald-50/30' : 'border-slate-300 hover:border-emerald-500 bg-slate-50/50'
                }`}>
                  <input
                    type="file"
                    accept=".csv,.pdf"
                    onChange={(e) => setFilePR(e.target.files[0])}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  <div className="space-y-3 pointer-events-none">
                    <div className="w-14 h-14 mx-auto rounded-full bg-white shadow-sm border border-slate-200 flex items-center justify-center">
                      <FileSpreadsheet className="w-7 h-7 text-emerald-600" />
                    </div>
                    <div>
                      <div className="font-bold text-sm text-slate-900">
                        {filePR ? filePR.name : 'List 1: Purchase Register (PR)'}
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        {filePR
                          ? `${(filePR.size / 1024).toFixed(1)} KB • Click or drop to replace`
                          : 'Company ERP books (CSV or PDF format)'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Zone 2: GSTR-2B */}
                <div className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition ${
                  file2B ? 'border-teal-500 bg-teal-50/30' : 'border-slate-300 hover:border-teal-500 bg-slate-50/50'
                }`}>
                  <input
                    type="file"
                    accept=".csv,.pdf"
                    onChange={(e) => setFile2B(e.target.files[0])}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  <div className="space-y-3 pointer-events-none">
                    <div className="w-14 h-14 mx-auto rounded-full bg-white shadow-sm border border-slate-200 flex items-center justify-center">
                      <FileText className="w-7 h-7 text-teal-600" />
                    </div>
                    <div>
                      <div className="font-bold text-sm text-slate-900">
                        {file2B ? file2B.name : 'List 2: GSTR-2B Tax Portal Records'}
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        {file2B
                          ? `${(file2B.size / 1024).toFixed(1)} KB • Click or drop to replace`
                          : 'Supplier reported filings (CSV or PDF format)'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Submit Reconcile Button */}
              <button
                disabled={!filePR || !file2B}
                onClick={handleUploadReconcile}
                className={`w-full py-4 px-6 rounded-xl font-bold flex items-center justify-center space-x-2 transition text-sm shadow-md ${
                  filePR && file2B
                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-600/20 cursor-pointer'
                    : 'bg-slate-200 text-slate-400 cursor-not-allowed border border-slate-200'
                }`}
              >
                <RefreshCw className="w-4 h-4" />
                <span>Reconcile Uploaded Invoices</span>
              </button>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: EXECUTIVE DASHBOARD (Full Width Expansive) */}
        {/* ========================================================================= */}
        {activeTab === 'dashboard' && summary && (
          <div className="w-full space-y-6">
            {/* Session Info Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <div>
                <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
                  Reconciliation Completed
                </span>
                <div className="text-sm font-semibold text-slate-900 flex items-center space-x-2 mt-0.5">
                  <span>{sessionMeta?.source}</span>
                  <span className="text-slate-400">•</span>
                  <span className="text-slate-600">{sessionMeta?.records} Total Invoices</span>
                  <span className="text-slate-400">•</span>
                  <span className="text-slate-600">{sessionMeta?.elapsed}s Execution Time</span>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setActiveTab('review')}
                  className="px-4 py-2 bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-900 text-xs font-bold rounded-lg transition flex items-center space-x-1.5 shadow-sm"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  <span>Review Queue ({summary.status_counts?.NEEDS_REVIEW || 0})</span>
                </button>
                <button
                  onClick={() => setActiveTab('table')}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-800 text-xs font-bold rounded-lg transition flex items-center space-x-1.5"
                >
                  <Layers className="w-3.5 h-3.5 text-slate-600" />
                  <span>View All Invoices</span>
                </button>
              </div>
            </div>

            {/* Metrics Cards Grid (Full Screen 4 Columns) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Total ITC at Risk */}
              <div className="bg-white p-5 rounded-2xl border-l-4 border-l-rose-500 border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Total ITC at Risk</span>
                  <div className="w-8 h-8 rounded-lg bg-rose-50 flex items-center justify-center">
                    <TrendingUp className="w-4 h-4 text-rose-600" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-black text-rose-600 tracking-tight">
                  {formatINR(summary.total_itc_at_risk)}
                </div>
                <p className="mt-1 text-xs text-slate-500 font-medium">
                  Tax credit blocked due to missing or mismatched filings
                </p>
              </div>

              {/* Card 2: Matched Invoices */}
              <div className="bg-white p-5 rounded-2xl border-l-4 border-l-emerald-500 border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Matched Invoices</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-bold text-emerald-600">
                  {summary.status_counts?.MATCHED || 0}
                </div>
                <p className="mt-1 text-xs text-slate-500 font-medium">
                  {(
                    ((summary.status_counts?.MATCHED || 0) / (summary.total_records || 1)) *
                    100
                  ).toFixed(1)}
                  % of total purchase ledger
                </p>
              </div>

              {/* Card 3: Needs Review */}
              <div className="bg-white p-5 rounded-2xl border-l-4 border-l-amber-500 border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Needs Review</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-bold text-amber-600">
                  {summary.status_counts?.NEEDS_REVIEW || 0}
                </div>
                <p className="mt-1 text-xs text-slate-500 font-medium">Pending manual auditor verification</p>
              </div>

              {/* Card 4: Confirmed Mismatches */}
              <div className="bg-white p-5 rounded-2xl border-l-4 border-l-red-500 border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Mismatched Records</span>
                  <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center">
                    <XCircle className="w-4 h-4 text-red-600" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-bold text-red-600">
                  {summary.status_counts?.MISMATCHED || 0}
                </div>
                <p className="mt-1 text-xs text-slate-500 font-medium">Missing in 2B or rate discrepancies</p>
              </div>
            </div>

            {/* Discrepancy Breakdown Row */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Discrepancy Category Breakdown
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
                {[
                  { key: 'NONE', label: 'Exact / Normalized', color: 'text-emerald-700' },
                  { key: 'MISSING_IN_2B', label: 'Missing in GSTR-2B', color: 'text-rose-700' },
                  { key: 'AMOUNT_DIFF', label: 'Amount Discrepancy', color: 'text-amber-700' },
                  { key: 'RATE_MISMATCH', label: 'Rate Mismatch', color: 'text-red-700' },
                  { key: 'DUPLICATE_IN_BOOKS', label: 'Duplicate in Books', color: 'text-orange-700' },
                  { key: 'WRONG_PERIOD', label: 'Wrong Period Shift', color: 'text-purple-700' },
                  { key: 'EXTRA_IN_2B', label: 'Extra in GSTR-2B', color: 'text-teal-700' },
                  { key: 'NAME_DIFF', label: 'Name Variation', color: 'text-blue-700' },
                ].map((item) => {
                  const count = summary.mismatch_counts?.[item.key] || 0;
                  return (
                    <div
                      key={item.key}
                      onClick={() => {
                        setTypeFilter(item.key);
                        setActiveTab('table');
                      }}
                      className="cursor-pointer bg-white hover:bg-slate-50 p-3 rounded-xl border border-slate-200 hover:border-slate-300 transition shadow-sm"
                    >
                      <div className="text-xs text-slate-500 font-medium truncate">{item.label}</div>
                      <div className={`text-lg font-extrabold mt-1 ${item.color}`}>{count}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recharts Bar Chart: Top Suppliers with ITC at Risk (Full Width) */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Top Suppliers by ITC at Risk (₹)
                  </h3>
                  <p className="text-xs text-slate-500">
                    Suppliers with missing portal filings, rate discrepancies, or unverified invoices
                  </p>
                </div>
                <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600 border border-slate-200">
                  Rupee Distribution Chart
                </span>
              </div>

              {summary.itc_by_supplier && summary.itc_by_supplier.length > 0 ? (
                <div className="h-80 w-full pt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={summary.itc_by_supplier}
                      margin={{ top: 10, right: 30, left: 30, bottom: 50 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                      <XAxis
                        dataKey="supplier_name"
                        stroke="#64748b"
                        fontSize={12}
                        angle={-15}
                        textAnchor="end"
                        tickFormatter={(val) =>
                          val.length > 20 ? val.substring(0, 18) + '...' : val
                        }
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={12}
                        tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          borderColor: '#cbd5e1',
                          borderRadius: '8px',
                          color: '#0f172a',
                          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                        }}
                        formatter={(val) => [formatINR(val), 'ITC at Risk']}
                      />
                      <Bar dataKey="itc_at_risk" radius={[6, 6, 0, 0]}>
                        {summary.itc_by_supplier.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={BAR_COLORS[index % BAR_COLORS.length]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400 text-sm">
                  No suppliers currently have ITC at risk in this ledger.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: HUMAN REVIEW QUEUE (Expansive Full Width) */}
        {/* ========================================================================= */}
        {activeTab === 'review' && (
          <div className="w-full space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-slate-900 flex items-center space-x-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  <span>Human Review Queue</span>
                  <span className="text-xs bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full border border-amber-300">
                    {pendingReviewRows.length} Pending
                  </span>
                </h2>
                <p className="text-xs text-slate-500 mt-1">
                  Invoices where confidence is below 80% or discrepancies require auditor verification.
                  Approving or rejecting updates the live ITC at risk calculations instantly.
                </p>
              </div>
            </div>

            {pendingReviewRows.length === 0 ? (
              <div className="bg-white p-12 rounded-2xl border border-slate-200 text-center space-y-3 shadow-sm">
                <div className="w-12 h-12 mx-auto rounded-full bg-emerald-50 flex items-center justify-center border border-emerald-200">
                  <Check className="w-6 h-6 text-emerald-600" />
                </div>
                <h3 className="text-lg font-bold text-slate-900">Review Queue Clear!</h3>
                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  All low-confidence records have been verified. Explore the full ledger under Invoices or download the CSV report.
                </p>
                <button
                  onClick={() => setActiveTab('table')}
                  className="mt-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition shadow-sm"
                >
                  View Invoices Table
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {pendingReviewRows.map((row) => (
                  <div
                    key={row.id}
                    className="bg-white p-6 rounded-2xl border border-amber-300 shadow-sm space-y-4"
                  >
                    {/* Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-mono font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded border border-amber-300">
                          {row.pr_row_id}
                        </span>
                        <span className="text-sm font-bold text-slate-900">
                          {row.supplier_name}
                        </span>
                        <span className="text-xs text-slate-500 font-mono">({row.gstin})</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 font-medium">
                          Confidence: <strong className="text-amber-700">{row.confidence}%</strong>
                        </span>
                        <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200">
                          ITC at Risk: {formatINR(row.itc_at_risk)}
                        </span>
                      </div>
                    </div>

                    {/* Side-by-Side Comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Left: Purchase Register */}
                      <div className="bg-emerald-50/40 p-4 rounded-xl border border-emerald-200 space-y-2">
                        <div className="text-xs font-bold text-emerald-800 flex items-center space-x-1">
                          <FileSpreadsheet className="w-3.5 h-3.5" />
                          <span>Company Purchase Register</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                          <div>
                            <span className="text-slate-500">Invoice No:</span>
                            <div className="font-mono font-bold text-slate-900">{row.invoice_number}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">Date:</span>
                            <div className="font-mono text-slate-800">{row.invoice_date}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">Taxable Value:</span>
                            <div className="font-semibold text-slate-800">{formatINR(row.taxable_value)}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">Total Tax:</span>
                            <div className="font-bold text-emerald-700">{formatINR(row.total_tax)}</div>
                          </div>
                        </div>
                      </div>

                      {/* Right: GSTR-2B Candidate */}
                      <div className="bg-teal-50/40 p-4 rounded-xl border border-teal-200 space-y-2">
                        <div className="text-xs font-bold text-teal-800 flex items-center space-x-1">
                          <FileSpreadsheet className="w-3.5 h-3.5" />
                          <span>GSTR-2B Supplier Filing</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                          <div>
                            <span className="text-slate-500">2B Invoice No:</span>
                            <div className="font-mono font-bold text-slate-900">{row.b2_invoice_number || '-'}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">2B Date:</span>
                            <div className="font-mono text-slate-800">{row.b2_date || '-'}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">2B Amount:</span>
                            <div className="font-semibold text-slate-800">{formatINR(row.b2_amount)}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">2B Tax:</span>
                            <div className="font-bold text-teal-700">{formatINR(row.b2_tax)}</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Audit Explanation */}
                    <div className="bg-amber-50/70 p-3 rounded-xl border border-amber-200 flex items-start space-x-2 text-xs">
                      <HelpCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div className="text-slate-700">
                        <strong className="text-slate-900">Audit Finding: </strong>
                        {row.reason}
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center justify-end space-x-3 pt-2">
                      <button
                        onClick={() => handleReviewAction(row.id, 'REJECT')}
                        className="px-4 py-2 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300 text-xs font-bold transition flex items-center space-x-1.5"
                      >
                        <X className="w-4 h-4 text-rose-600" />
                        <span>Reject & Block ITC</span>
                      </button>
                      <button
                        onClick={() => handleReviewAction(row.id, 'APPROVE')}
                        className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition flex items-center space-x-1.5 shadow-sm"
                      >
                        <Check className="w-4 h-4" />
                        <span>Approve Match</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: ALL INVOICES TABLE (Expansive Full Width) */}
        {/* ========================================================================= */}
        {activeTab === 'table' && (
          <div className="w-full space-y-4">
            {/* Filter Toolbar */}
            <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
              {/* Search bar */}
              <div className="relative flex-1 min-w-[260px]">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by supplier name, GSTIN, invoice #..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl pl-9 pr-4 py-2 text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {/* Status filter */}
              <div className="flex items-center space-x-2">
                <span className="text-xs font-medium text-slate-600">Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="MATCHED">Matched</option>
                  <option value="NEEDS_REVIEW">Needs Review</option>
                  <option value="MISMATCHED">Mismatched</option>
                </select>
              </div>

              {/* Type filter */}
              <div className="flex items-center space-x-2">
                <span className="text-xs font-medium text-slate-600">Discrepancy:</span>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="bg-white border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
                >
                  <option value="ALL">All Types</option>
                  <option value="NONE">NONE (Exact / Normalized)</option>
                  <option value="DUPLICATE_IN_BOOKS">DUPLICATE_IN_BOOKS (Duplicate in Books)</option>
                  <option value="AMOUNT_DIFF">AMOUNT_DIFF (Value Mismatch)</option>
                  <option value="RATE_MISMATCH">RATE_MISMATCH (Tax Rate Mismatch)</option>
                  <option value="WRONG_PERIOD">WRONG_PERIOD (Different Month)</option>
                  <option value="EXTRA_IN_2B">EXTRA_IN_2B (Filed but Not in Books)</option>
                  <option value="MISSING_IN_2B">MISSING_IN_2B (Unfiled by Vendor)</option>
                  <option value="NAME_DIFF">NAME_DIFF (Name Variation)</option>
                </select>
              </div>

              {/* Export button */}
              <button
                onClick={handleExportCSV}
                className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 border border-slate-300 text-xs font-semibold text-slate-800 flex items-center space-x-1.5 transition"
              >
                <Download className="w-3.5 h-3.5 text-emerald-600" />
                <span>Export ({filteredRows.length})</span>
              </button>
            </div>

            {/* Results Table (Edge-to-Edge) */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100/90 text-slate-700 uppercase tracking-wider font-bold border-b border-slate-200">
                    <tr>
                      <th className="py-3.5 px-4">Invoice # & Date</th>
                      <th className="py-3.5 px-4">Supplier & GSTIN</th>
                      <th className="py-3.5 px-4">PR Value / Tax</th>
                      <th className="py-3.5 px-4">2B Filing</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4">Discrepancy</th>
                      <th className="py-3.5 px-4">Confidence</th>
                      <th className="py-3.5 px-4 text-right">ITC at Risk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="py-10 text-center text-slate-500 font-medium">
                          No invoices found matching current search and filter criteria.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((row) => {
                        const statusBadge =
                          row.status === 'MATCHED'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : row.status === 'NEEDS_REVIEW'
                            ? 'bg-amber-50 text-amber-800 border-amber-200'
                            : 'bg-rose-50 text-rose-700 border-rose-200';

                        return (
                          <tr key={row.id} className="hover:bg-slate-50/80 transition">
                            <td className="py-3.5 px-4 font-mono">
                              <div className="font-bold text-slate-900">{row.invoice_number}</div>
                              <div className="text-[11px] text-slate-500">{row.invoice_date}</div>
                            </td>
                            <td className="py-3.5 px-4 max-w-[240px]">
                              <div className="font-semibold text-slate-900 truncate" title={row.supplier_name}>
                                {row.supplier_name}
                              </div>
                              <div className="font-mono text-[11px] text-slate-500">{row.gstin}</div>
                            </td>
                            <td className="py-3.5 px-4">
                              <div className="font-medium text-slate-900">{formatINR(row.total_amount)}</div>
                              <div className="text-[11px] font-semibold text-emerald-700">
                                Tax: {formatINR(row.total_tax)}
                              </div>
                            </td>
                            <td className="py-3.5 px-4 font-mono text-[11px]">
                              {row.b2_invoice_number !== '-' ? (
                                <>
                                  <div className="text-slate-800 font-medium">{row.b2_invoice_number}</div>
                                  <div className="text-slate-500">{row.b2_date}</div>
                                </>
                              ) : (
                                <span className="text-slate-400 italic">Not in 2B</span>
                              )}
                            </td>
                            <td className="py-3.5 px-4">
                              <span
                                className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${statusBadge}`}
                              >
                                {row.status}
                              </span>
                            </td>
                            <td className="py-3.5 px-4">
                              <span className="text-[11px] font-mono font-bold text-slate-800">
                                {row.mismatch_type}
                              </span>
                              <div className="text-[11px] text-slate-500 max-w-[260px] truncate" title={row.reason}>
                                {row.reason}
                              </div>
                            </td>
                            <td className="py-3.5 px-4">
                              <div className="flex items-center space-x-1.5">
                                <div className="w-12 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      row.confidence >= 80 ? 'bg-emerald-600' : 'bg-amber-500'
                                    }`}
                                    style={{ width: `${row.confidence}%` }}
                                  />
                                </div>
                                <span className="font-mono text-[11px] font-semibold text-slate-700">
                                  {row.confidence}%
                                </span>
                              </div>
                            </td>
                            <td className="py-3.5 px-4 text-right font-mono font-bold">
                              {row.itc_at_risk > 0 ? (
                                <span className="text-rose-600">{formatINR(row.itc_at_risk)}</span>
                              ) : (
                                <span className="text-slate-400">₹0.00</span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer (Full Width Light) */}
      <footer className="border-t border-slate-200 bg-white py-4 text-xs text-slate-500 text-center shadow-inner mt-auto">
        <div className="w-full px-4 sm:px-6 lg:px-8 xl:px-12 flex flex-wrap items-center justify-between gap-2">
          <div>GST Reconciliation Tool • Built for Indian Financial Compliance</div>
          <div className="flex items-center space-x-3">
            <span>Deterministic Math (Python Decimal)</span>
            <span>•</span>
            <span>Automated Discrepancy Auditing</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
