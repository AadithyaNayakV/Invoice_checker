import React, { useState, useEffect, useMemo } from 'react';
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
  Cpu,
  Layers,
  TrendingUp,
  BarChart3,
  HelpCircle,
  Check,
  X,
  ExternalLink,
  ChevronDown
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

// Format currency to Indian Rupees
const formatINR = (val) => {
  const num = Number(val) || 0;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(num);
};

export default function App() {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'dashboard' | 'review' | 'table'
  const [selectedSample, setSelectedSample] = useState('sample_01');
  const [filePR, setFilePR] = useState(null);
  const [file2B, setFile2B] = useState(null);

  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Reconciled data state
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [sessionMeta, setSessionMeta] = useState(null);

  // Table filtering state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Backend health state
  const [health, setHealth] = useState(null);

  // Fetch health check on mount
  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.warn('API health check pending:', err);
    }
  };

  // Run reconciliation from uploaded CSVs
  const handleUploadReconcile = async (e) => {
    e?.preventDefault();
    if (!filePR || !file2B) {
      setErrorMsg('Please upload both Purchase Register and GSTR-2B CSV files.');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    setLoadingStep('Uploading files and standardizing columns...');

    try {
      const formData = new FormData();
      formData.append('pr_file', filePR);
      formData.append('gstr2b_file', file2B);

      setTimeout(() => setLoadingStep('Running vectorized exact matching & rapidfuzz shortlisting...'), 400);
      setTimeout(() => setLoadingStep('Batch evaluating discrepancy candidates & computing ITC at risk...'), 900);

      const res = await fetch('/api/reconcile', {
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
        source: 'Uploaded CSV Files',
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

  // Load built-in sample dataset
  const handleLoadSample = async (sampleName) => {
    const sampleIdx = parseInt(sampleName.replace('sample_', ''), 10) || 1;
    setLoading(true);
    setErrorMsg('');
    setLoadingStep(`Loading built-in ${sampleName} from repository...`);

    try {
      setTimeout(() => setLoadingStep('Preprocessing records and resolving candidate blocks...'), 300);
      const res = await fetch(`/api/sample/${sampleIdx}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to load sample dataset.');
      }

      const data = await res.json();
      setSummary(data.summary);
      setResults(data.results);
      setSessionMeta({
        source: `Sample Dataset: ${sampleName}`,
        elapsed: data.elapsed_seconds,
        records: data.results?.length || 0,
      });
      setActiveTab('dashboard');
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load sample data.');
    } finally {
      setLoading(false);
      setLoadingStep('');
    }
  };

  // Human Review Queue Action (Approve / Reject)
  const handleReviewAction = async (rowId, action) => {
    try {
      const res = await fetch('/api/review', {
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
      const res = await fetch('/api/export', {
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

  // Color bar chart palette
  const BAR_COLORS = ['#ef4444', '#f97316', '#f59e0b', '#3b82f6', '#8b5cf6'];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-emerald-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <FileSpreadsheet className="w-5 h-5 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">GST Reconcile</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">
                  AI-Powered
                </span>
              </div>
              <p className="text-xs text-slate-400">Purchase Register vs GSTR-2B Audit Engine</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-1 sm:space-x-2 bg-slate-950/60 p-1.5 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('upload')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition ${
                activeTab === 'upload'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              Upload & Run
            </button>
            <button
              disabled={!summary}
              onClick={() => setActiveTab('dashboard')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition flex items-center space-x-1.5 ${
                !summary ? 'opacity-40 cursor-not-allowed text-slate-500' : ''
              } ${
                activeTab === 'dashboard'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Dashboard</span>
            </button>
            <button
              disabled={!summary}
              onClick={() => setActiveTab('table')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition flex items-center space-x-1.5 ${
                !summary ? 'opacity-40 cursor-not-allowed text-slate-500' : ''
              } ${
                activeTab === 'table'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Invoices ({results.length})</span>
            </button>
            <button
              disabled={!summary}
              onClick={() => setActiveTab('review')}
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition flex items-center space-x-1.5 ${
                !summary ? 'opacity-40 cursor-not-allowed text-slate-500' : ''
              } ${
                activeTab === 'review'
                  ? 'bg-amber-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
              <span>Review</span>
              {pendingReviewRows.length > 0 && (
                <span className="ml-1 bg-amber-400 text-slate-950 font-bold text-[11px] px-1.5 py-0.2 rounded-full">
                  {pendingReviewRows.length}
                </span>
              )}
            </button>
          </nav>

          {/* Action buttons & Model status */}
          <div className="flex items-center space-x-3">
            <div className="hidden lg:flex items-center space-x-1.5 text-xs text-slate-400 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
              <Cpu className="w-3.5 h-3.5 text-emerald-400" />
              <span>Model:</span>
              <span className="text-slate-200 font-mono font-medium">
                {health?.gemini_model || 'gemini-2.5-flash'}
              </span>
              <span
                className={`w-2 h-2 rounded-full ml-1 ${
                  health?.gemini_connected ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
                title={health?.gemini_connected ? 'Gemini API active' : 'Offline heuristic fallback'}
              />
            </div>

            {results.length > 0 && (
              <button
                onClick={handleExportCSV}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
              >
                <Download className="w-4 h-4 text-emerald-400" />
                <span>Export CSV</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Error notification banner */}
        {errorMsg && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex items-start space-x-3">
            <XCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1 text-sm">{errorMsg}</div>
            <button onClick={() => setErrorMsg('')} className="text-red-400 hover:text-red-200">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Loading Overlay */}
        {loading && (
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="glass-panel p-8 rounded-2xl max-w-md w-full text-center space-y-4 shadow-2xl border border-slate-700">
              <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center animate-spin">
                <RefreshCw className="w-7 h-7 text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Reconciliation in Progress</h3>
              <p className="text-sm text-slate-400 animate-pulse">{loadingStep}</p>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div className="bg-gradient-to-r from-emerald-500 to-teal-400 h-full w-2/3 animate-pulse" />
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 1: UPLOAD & SAMPLE SELECTOR */}
        {/* ========================================================================= */}
        {activeTab === 'upload' && (
          <div className="space-y-8 max-w-4xl mx-auto">
            {/* Hero Card */}
            <div className="glass-panel p-6 sm:p-8 rounded-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
              <div className="relative z-10 space-y-3">
                <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold border border-emerald-500/20">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>GST ITC Protection Suite</span>
                </span>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  Automated GST Purchase Register vs GSTR-2B Audit
                </h1>
                <p className="text-sm text-slate-300 leading-relaxed max-w-2xl">
                  Reconciles internal purchase registers against government GSTR-2B supplier filings.
                  Detects name variations, ERP numbering mismatches, tax rate discrepancies, and unfiled invoices.
                  Protects your business from ineligible Input Tax Credit (ITC) penalties.
                </p>
              </div>
            </div>

            {/* Quick Demo with Pre-generated Sample Pair */}
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className="w-8 h-8 rounded-lg bg-teal-500/10 flex items-center justify-center border border-teal-500/20">
                    <Layers className="w-4 h-4 text-teal-400" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-white">One-Click Demonstration</h2>
                    <p className="text-xs text-slate-400">
                      Explore pre-generated realistic Indian GST datasets (30 to 1,000 invoices).
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="sm:col-span-2">
                  <select
                    value={selectedSample}
                    onChange={(e) => setSelectedSample(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition"
                  >
                    <option value="sample_01">sample_01 (30 rows - Quick Demo)</option>
                    <option value="sample_02">sample_02 (35 rows - Discrepancy mix)</option>
                    <option value="sample_03">sample_03 (40 rows)</option>
                    <option value="sample_04">sample_04 (50 rows)</option>
                    <option value="sample_05">sample_05 (60 rows)</option>
                    <option value="sample_06">sample_06 (100 rows)</option>
                    <option value="sample_07">sample_07 (150 rows)</option>
                    <option value="sample_08">sample_08 (200 rows - Mid-size ledger)</option>
                    <option value="sample_09">sample_09 (200 rows)</option>
                    <option value="sample_10">sample_10 (250 rows)</option>
                    <option value="sample_11">sample_11 (300 rows)</option>
                    <option value="sample_12">sample_12 (500 rows - High volume)</option>
                    <option value="sample_13">sample_13 (800 rows)</option>
                    <option value="sample_14">sample_14 (1000 rows - Enterprise test)</option>
                    <option value="sample_15">sample_15 (1000 rows - Full stress test)</option>
                  </select>
                </div>
                <button
                  onClick={() => handleLoadSample(selectedSample)}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-5 py-3 rounded-xl transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20"
                >
                  <ArrowRight className="w-4 h-4" />
                  <span>Run Sample</span>
                </button>
              </div>
            </div>

            {/* Custom CSV Upload Zones */}
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                  <UploadCloud className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-white">Upload Custom CSV Files</h2>
                  <p className="text-xs text-slate-400">
                    Compare your organization's Purchase Register against GSTR-2B.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Zone 1: Purchase Register */}
                <div className="relative border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-2xl p-6 text-center transition bg-slate-900/40">
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setFilePR(e.target.files[0])}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  <div className="space-y-2 pointer-events-none">
                    <div className="w-12 h-12 mx-auto rounded-full bg-slate-800 flex items-center justify-center">
                      <FileSpreadsheet className="w-6 h-6 text-emerald-400" />
                    </div>
                    <div className="font-medium text-sm text-slate-200">
                      {filePR ? filePR.name : 'List 1: Purchase Register (PR)'}
                    </div>
                    <p className="text-xs text-slate-500">
                      {filePR
                        ? `${(filePR.size / 1024).toFixed(1)} KB selected`
                        : 'Company ERP books (CSV format)'}
                    </p>
                  </div>
                </div>

                {/* Zone 2: GSTR-2B */}
                <div className="relative border-2 border-dashed border-slate-700 hover:border-teal-500/50 rounded-2xl p-6 text-center transition bg-slate-900/40">
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setFile2B(e.target.files[0])}
                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  />
                  <div className="space-y-2 pointer-events-none">
                    <div className="w-12 h-12 mx-auto rounded-full bg-slate-800 flex items-center justify-center">
                      <FileSpreadsheet className="w-6 h-6 text-teal-400" />
                    </div>
                    <div className="font-medium text-sm text-slate-200">
                      {file2B ? file2B.name : 'List 2: GSTR-2B Government Portal'}
                    </div>
                    <p className="text-xs text-slate-500">
                      {file2B
                        ? `${(file2B.size / 1024).toFixed(1)} KB selected`
                        : 'Supplier reported filings (CSV format)'}
                    </p>
                  </div>
                </div>
              </div>

              <button
                disabled={!filePR || !file2B}
                onClick={handleUploadReconcile}
                className={`w-full py-3.5 px-6 rounded-xl font-semibold flex items-center justify-center space-x-2 transition shadow-lg ${
                  filePR && file2B
                    ? 'bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white shadow-emerald-500/20'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                }`}
              >
                <RefreshCw className="w-4 h-4" />
                <span>Reconcile Uploaded Invoices</span>
              </button>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: EXECUTIVE DASHBOARD */}
        {/* ========================================================================= */}
        {activeTab === 'dashboard' && summary && (
          <div className="space-y-6">
            {/* Top status bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/50 p-4 rounded-xl border border-slate-800">
              <div>
                <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                  Audit Run Completed
                </span>
                <div className="text-sm font-medium text-white flex items-center space-x-2">
                  <span>{sessionMeta?.source}</span>
                  <span className="text-slate-500">•</span>
                  <span className="text-slate-400">{sessionMeta?.records} Invoices</span>
                  <span className="text-slate-500">•</span>
                  <span className="text-slate-400">{sessionMeta?.elapsed}s Execution Time</span>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setActiveTab('review')}
                  className="px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-medium rounded-lg transition flex items-center space-x-1.5"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Review Queue ({summary.status_counts?.NEEDS_REVIEW || 0})</span>
                </button>
                <button
                  onClick={() => setActiveTab('table')}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-medium rounded-lg transition flex items-center space-x-1.5"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>View All Invoices</span>
                </button>
              </div>
            </div>

            {/* Metric Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Total ITC at Risk (Hero Card) */}
              <div className="sm:col-span-2 lg:col-span-1 glass-panel p-5 rounded-2xl border-l-4 border-l-red-500 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Total ITC at Risk</span>
                  <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
                    <TrendingUp className="w-4 h-4 text-red-400" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-black text-red-400 tracking-tight">
                  {formatINR(summary.total_itc_at_risk)}
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Potential tax loss due to supplier filing errors
                </p>
              </div>

              {/* Card 2: Matched Invoices */}
              <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-emerald-500">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Matched Invoices</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-bold text-emerald-400">
                  {summary.status_counts?.MATCHED || 0}
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {(
                    ((summary.status_counts?.MATCHED || 0) / (summary.total_records || 1)) *
                    100
                  ).toFixed(1)}
                  % of total purchase ledger
                </p>
              </div>

              {/* Card 3: Needs Review */}
              <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-amber-500">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Needs Review</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-bold text-amber-400">
                  {summary.status_counts?.NEEDS_REVIEW || 0}
                </div>
                <p className="mt-1 text-xs text-slate-400">Low confidence AI flags requiring human sign-off</p>
              </div>

              {/* Card 4: Confirmed Mismatches */}
              <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-rose-500">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-400">Confirmed Mismatches</span>
                  <div className="w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center">
                    <XCircle className="w-4 h-4 text-rose-400" />
                  </div>
                </div>
                <div className="mt-3 text-2xl font-bold text-rose-400">
                  {summary.status_counts?.MISMATCHED || 0}
                </div>
                <p className="mt-1 text-xs text-slate-400">Missing in 2B, rate errors or amount drift</p>
              </div>
            </div>

            {/* Discrepancy Categories Pill Row */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-3">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Discrepancy Category Breakdown
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {[
                  { key: 'NONE', label: 'Exact / Normalized', color: 'emerald' },
                  { key: 'MISSING_IN_2B', label: 'Missing in GSTR-2B', color: 'red' },
                  { key: 'AMOUNT_DIFF', label: 'Amount Discrepancy', color: 'amber' },
                  { key: 'RATE_MISMATCH', label: 'GST Rate Mismatch', color: 'rose' },
                  { key: 'NAME_DIFF', label: 'Supplier Name Variation', color: 'blue' },
                  { key: 'DATE_PERIOD', label: 'Period / Month Shift', color: 'purple' },
                ].map((item) => {
                  const count = summary.mismatch_counts?.[item.key] || 0;
                  return (
                    <div
                      key={item.key}
                      onClick={() => {
                        setTypeFilter(item.key);
                        setActiveTab('table');
                      }}
                      className="cursor-pointer bg-slate-900/60 hover:bg-slate-800/80 p-3 rounded-xl border border-slate-800 transition"
                    >
                      <div className="text-xs text-slate-400 truncate">{item.label}</div>
                      <div className="text-lg font-bold text-white mt-1">{count}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recharts Bar Chart: Top Suppliers by ITC at Risk */}
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    Top Suppliers by ITC at Risk (₹)
                  </h3>
                  <p className="text-xs text-slate-400">
                    Suppliers with missing filings, rate discrepancies, or unverified invoices
                  </p>
                </div>
                <span className="text-xs text-slate-500">Recharts Visualization</span>
              </div>

              {summary.itc_by_supplier && summary.itc_by_supplier.length > 0 ? (
                <div className="h-72 w-full pt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={summary.itc_by_supplier}
                      margin={{ top: 10, right: 30, left: 20, bottom: 40 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="supplier_name"
                        stroke="#64748b"
                        fontSize={11}
                        angle={-20}
                        textAnchor="end"
                        tickFormatter={(val) =>
                          val.length > 18 ? val.substring(0, 16) + '...' : val
                        }
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={11}
                        tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#334155',
                          borderRadius: '8px',
                          color: '#fff',
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
                <div className="p-8 text-center text-slate-500 text-sm">
                  No suppliers currently have ITC at risk in this dataset.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: HUMAN REVIEW QUEUE */}
        {/* ========================================================================= */}
        {activeTab === 'review' && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center space-x-2">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  <span>Human Review Queue</span>
                  <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/30">
                    {pendingReviewRows.length} Pending
                  </span>
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Rows where AI confidence is below 80% or discrepancies require auditor verification.
                  Approving or rejecting instantly recalculates ITC at risk.
                </p>
              </div>

              {pendingReviewRows.length > 0 && (
                <div className="text-xs text-slate-400">
                  Tip: Approving marks invoice as matched and frees blocked credit.
                </div>
              )}
            </div>

            {pendingReviewRows.length === 0 ? (
              <div className="glass-panel p-12 rounded-2xl text-center space-y-3">
                <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/30">
                  <Check className="w-6 h-6 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-white">Review Queue Clear!</h3>
                <p className="text-sm text-slate-400 max-w-md mx-auto">
                  All low-confidence records have been verified. You can explore the full ledger
                  under the Invoices tab or export the CSV report.
                </p>
                <button
                  onClick={() => setActiveTab('table')}
                  className="mt-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition"
                >
                  View Invoices Table
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {pendingReviewRows.map((row) => (
                  <div
                    key={row.id}
                    className="glass-panel p-5 rounded-2xl border border-amber-500/30 space-y-4"
                  >
                    {/* Header line */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-mono font-bold text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">
                          {row.pr_row_id}
                        </span>
                        <span className="text-sm font-semibold text-white">
                          {row.supplier_name}
                        </span>
                        <span className="text-xs text-slate-400 font-mono">({row.gstin})</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                          Confidence: <strong className="text-amber-400">{row.confidence}%</strong>
                        </span>
                        <span className="text-xs font-semibold text-rose-400 bg-rose-400/10 px-2.5 py-0.5 rounded-full border border-rose-400/20">
                          ITC at Risk: {formatINR(row.itc_at_risk)}
                        </span>
                      </div>
                    </div>

                    {/* Side-by-Side Comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Left: Purchase Register (PR) */}
                      <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
                        <div className="text-xs font-semibold text-emerald-400 flex items-center space-x-1">
                          <FileSpreadsheet className="w-3.5 h-3.5" />
                          <span>Company Purchase Register</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                          <div>
                            <span className="text-slate-500">Invoice No:</span>
                            <div className="font-mono font-medium text-slate-200">
                              {row.invoice_number}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500">Date:</span>
                            <div className="font-mono text-slate-200">{row.invoice_date}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">Taxable Value:</span>
                            <div className="font-medium text-slate-200">
                              {formatINR(row.taxable_value)}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500">Total Tax:</span>
                            <div className="font-medium text-emerald-400">
                              {formatINR(row.total_tax)}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Right: GSTR-2B Candidate */}
                      <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
                        <div className="text-xs font-semibold text-teal-400 flex items-center space-x-1">
                          <FileSpreadsheet className="w-3.5 h-3.5" />
                          <span>GSTR-2B Supplier Filing</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                          <div>
                            <span className="text-slate-500">2B Invoice No:</span>
                            <div className="font-mono font-medium text-slate-200">
                              {row.b2_invoice_number || '-'}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500">2B Date:</span>
                            <div className="font-mono text-slate-200">{row.b2_date || '-'}</div>
                          </div>
                          <div>
                            <span className="text-slate-500">2B Amount:</span>
                            <div className="font-medium text-slate-200">
                              {formatINR(row.b2_amount)}
                            </div>
                          </div>
                          <div>
                            <span className="text-slate-500">2B Tax:</span>
                            <div className="font-medium text-teal-400">
                              {formatINR(row.b2_tax)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* AI Auditor Explanation */}
                    <div className="bg-slate-900/40 p-3 rounded-xl border border-slate-800/80 flex items-start space-x-2 text-xs">
                      <HelpCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <div className="text-slate-300">
                        <strong className="text-slate-200">Audit Finding: </strong>
                        {row.reason}
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center justify-end space-x-3 pt-2">
                      <button
                        onClick={() => handleReviewAction(row.id, 'REJECT')}
                        className="px-4 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30 text-xs font-semibold transition flex items-center space-x-1.5"
                      >
                        <X className="w-4 h-4 text-red-400" />
                        <span>Reject & Block ITC</span>
                      </button>
                      <button
                        onClick={() => handleReviewAction(row.id, 'APPROVE')}
                        className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition flex items-center space-x-1.5 shadow-md shadow-emerald-600/20"
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
        {/* TAB 4: ALL INVOICES TABLE */}
        {/* ========================================================================= */}
        {activeTab === 'table' && (
          <div className="space-y-4">
            {/* Filter toolbar */}
            <div className="glass-panel p-4 rounded-2xl border border-slate-800 flex flex-wrap items-center justify-between gap-3">
              {/* Search bar */}
              <div className="relative flex-1 min-w-[240px]">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by supplier name, GSTIN, invoice #..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-4 py-2 text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {/* Status filter */}
              <div className="flex items-center space-x-2">
                <span className="text-xs text-slate-400">Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="MATCHED">Matched</option>
                  <option value="NEEDS_REVIEW">Needs Review</option>
                  <option value="MISMATCHED">Mismatched</option>
                </select>
              </div>

              {/* Type filter */}
              <div className="flex items-center space-x-2">
                <span className="text-xs text-slate-400">Discrepancy:</span>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="ALL">All Types</option>
                  <option value="NONE">NONE (Exact/Normalized)</option>
                  <option value="NAME_DIFF">NAME_DIFF (Name variation)</option>
                  <option value="AMOUNT_DIFF">AMOUNT_DIFF (Value drift)</option>
                  <option value="RATE_MISMATCH">RATE_MISMATCH (Tax rate)</option>
                  <option value="DATE_PERIOD">DATE_PERIOD (Month shift)</option>
                  <option value="MISSING_IN_2B">MISSING_IN_2B (Unfiled)</option>
                </select>
              </div>

              {/* Export button */}
              <button
                onClick={handleExportCSV}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center space-x-1.5 transition"
              >
                <Download className="w-3.5 h-3.5 text-emerald-400" />
                <span>Export ({filteredRows.length})</span>
              </button>
            </div>

            {/* Results Table */}
            <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Invoice # & Date</th>
                      <th className="py-3 px-4">Supplier & GSTIN</th>
                      <th className="py-3 px-4">PR Value / Tax</th>
                      <th className="py-3 px-4">2B Filing</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Discrepancy</th>
                      <th className="py-3 px-4">Confidence</th>
                      <th className="py-3 px-4 text-right">ITC at Risk</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="py-8 text-center text-slate-500">
                          No invoices found matching current search and filter criteria.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((row) => {
                        const statusBadge =
                          row.status === 'MATCHED'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : row.status === 'NEEDS_REVIEW'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-rose-500/10 text-rose-400 border-rose-500/20';

                        return (
                          <tr key={row.id} className="hover:bg-slate-900/50 transition">
                            <td className="py-3 px-4 font-mono">
                              <div className="font-semibold text-slate-200">{row.invoice_number}</div>
                              <div className="text-[11px] text-slate-500">{row.invoice_date}</div>
                            </td>
                            <td className="py-3 px-4 max-w-[200px]">
                              <div className="font-medium text-slate-200 truncate" title={row.supplier_name}>
                                {row.supplier_name}
                              </div>
                              <div className="font-mono text-[11px] text-slate-400">{row.gstin}</div>
                            </td>
                            <td className="py-3 px-4">
                              <div className="text-slate-200">{formatINR(row.total_amount)}</div>
                              <div className="text-[11px] text-emerald-400">
                                Tax: {formatINR(row.total_tax)}
                              </div>
                            </td>
                            <td className="py-3 px-4 font-mono text-[11px]">
                              {row.b2_invoice_number !== '-' ? (
                                <>
                                  <div className="text-slate-300">{row.b2_invoice_number}</div>
                                  <div className="text-slate-500">{row.b2_date}</div>
                                </>
                              ) : (
                                <span className="text-slate-500 italic">Not in 2B</span>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${statusBadge}`}
                              >
                                {row.status}
                              </span>
                            </td>
                            <td className="py-3 px-4">
                              <span className="text-[11px] text-slate-300 font-mono">
                                {row.mismatch_type}
                              </span>
                              <div className="text-[10px] text-slate-500 max-w-[220px] truncate" title={row.reason}>
                                {row.reason}
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex items-center space-x-1.5">
                                <div className="w-12 bg-slate-800 rounded-full h-1.5">
                                  <div
                                    className={`h-full rounded-full ${
                                      row.confidence >= 80 ? 'bg-emerald-400' : 'bg-amber-400'
                                    }`}
                                    style={{ width: `${row.confidence}%` }}
                                  />
                                </div>
                                <span className="font-mono text-[11px] text-slate-400">
                                  {row.confidence}%
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-4 text-right font-mono font-semibold">
                              {row.itc_at_risk > 0 ? (
                                <span className="text-rose-400">{formatINR(row.itc_at_risk)}</span>
                              ) : (
                                <span className="text-slate-500">₹0.00</span>
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

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/40 py-4 text-xs text-slate-500 text-center">
        <div className="max-w-7xl mx-auto px-4 flex flex-wrap items-center justify-between gap-2">
          <div>GST Reconciliation Tool • Built for Indian Financial Compliance</div>
          <div className="flex items-center space-x-3">
            <span>Deterministic Math (Python Decimal)</span>
            <span>•</span>
            <span>AI Fuzzy Discrepancy Auditing</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
