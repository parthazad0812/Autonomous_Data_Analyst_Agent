"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Download, FileText, Loader2, AlertCircle,
  ExternalLink, BarChart3, Printer,
} from "lucide-react";
import { api } from "@/lib/api";
import { ReportViewer } from "@/components/report-viewer";

interface ChartURL {
  path: string;
  url: string;
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [markdown, setMarkdown] = useState<string>("");
  const [charts, setCharts] = useState<ChartURL[]>([]);
  const [filename, setFilename] = useState<string>("report");
  const [title, setTitle] = useState<string>("Analysis Report");
  const [findingsCount, setFindingsCount] = useState<number>(0);
  const [completedAt, setCompletedAt] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Load report data
  useEffect(() => {
    if (!id) return;
    const load = async () => {
      setLoading(true);
      try {
        const [statusRes, reportRes, chartsRes] = await Promise.all([
          api.get(`/analysis/${id}/status`),
          api.get(`/analysis/${id}/report`),
          api.get(`/analysis/${id}/charts`),
        ]);
        setMarkdown(reportRes.data.report_markdown ?? "");
        setCharts(chartsRes.data ?? []);
        setFilename(statusRes.data.dataset_filename ?? "report");
        setTitle(
          statusRes.data.dataset_filename
            ? `${statusRes.data.dataset_filename} — Analysis Report`
            : "Analysis Report"
        );
        setFindingsCount(statusRes.data.findings_count ?? 0);
        setCompletedAt(statusRes.data.completed_at ?? null);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load report";
        setError(msg);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  // PDF download
  const handleDownloadPdf = useCallback(async () => {
    if (pdfLoading) return;
    setPdfLoading(true);
    try {
      const token = localStorage.getItem("access_token") ?? "";
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/analysis/${id}/report/pdf`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error(`PDF request failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stem = filename.replace(/\.[^.]+$/, "");
      a.download = `${stem}_analysis_report.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      console.error("PDF download failed:", err);
      alert("PDF generation failed. Please try again.");
    } finally {
      setPdfLoading(false);
    }
  }, [id, filename, pdfLoading]);

  // Markdown download via API endpoint
  const handleDownloadMd = useCallback(async () => {
    const token = localStorage.getItem("access_token") ?? "";
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/analysis/${id}/report/download`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const stem = filename.replace(/\.[^.]+$/, "");
    a.download = `${stem}_analysis_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [id, filename]);

  const handlePrint = () => window.print();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center"
        style={{ background: "hsl(var(--background))" }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin" style={{ color: "hsl(var(--primary))" }} />
          <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>Loading report…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center"
        style={{ background: "hsl(var(--background))" }}>
        <div className="text-center space-y-3">
          <AlertCircle className="w-12 h-12 mx-auto" style={{ color: "hsl(var(--destructive))" }} />
          <p className="font-medium text-white">{error}</p>
          <button
            onClick={() => router.back()}
            className="text-sm underline"
            style={{ color: "hsl(var(--muted-foreground))" }}
          >
            Go back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "hsl(var(--background))" }}>
      {/* ── Top toolbar ──────────────────────────────────────────────────────── */}
      <div
        className="sticky top-0 z-30 border-b print:hidden"
        style={{ background: "hsl(var(--card)/.95)", borderColor: "hsl(var(--border))", backdropFilter: "blur(8px)" }}
      >
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          {/* Left: back + title */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              id="report-page-back-btn"
              onClick={() => router.back()}
              className="p-2 rounded-lg transition-colors hover:bg-white/5 shrink-0"
              style={{ color: "hsl(var(--muted-foreground))" }}
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 shrink-0" style={{ color: "hsl(var(--primary))" }} />
                <span className="font-semibold text-sm text-white truncate">{title}</span>
              </div>
              <div className="text-xs mt-0.5 flex items-center gap-3"
                style={{ color: "hsl(var(--muted-foreground))" }}>
                <span className="flex items-center gap-1">
                  <BarChart3 className="w-3 h-3" />
                  {findingsCount} findings
                </span>
                {completedAt && (
                  <span>
                    {new Date(completedAt).toLocaleDateString("en-US", {
                      month: "short", day: "numeric", year: "numeric",
                    })}
                  </span>
                )}
                {charts.length > 0 && (
                  <span>{charts.length} charts embedded</span>
                )}
              </div>
            </div>
          </div>

          {/* Right: action buttons */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              id="report-page-print-btn"
              onClick={handlePrint}
              className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border transition-colors"
              style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--muted-foreground))" }}
            >
              <Printer className="w-3.5 h-3.5" />
              Print
            </button>
            <button
              id="report-page-download-md-btn"
              onClick={handleDownloadMd}
              className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border transition-colors"
              style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--muted-foreground))" }}
            >
              <Download className="w-3.5 h-3.5" />
              .md
            </button>
            <button
              id="report-page-download-pdf-btn"
              onClick={handleDownloadPdf}
              disabled={pdfLoading}
              className="flex items-center gap-1.5 text-xs px-4 py-2 rounded-lg font-semibold text-white transition-all"
              style={{
                background: pdfLoading ? "hsl(var(--primary)/.4)" : "linear-gradient(135deg, hsl(var(--primary)), hsl(262 83% 58%))",
                cursor: pdfLoading ? "not-allowed" : "pointer",
                boxShadow: pdfLoading ? "none" : "0 0 20px hsl(var(--primary)/.3)",
              }}
            >
              {pdfLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  Download PDF
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Report body ───────────────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto px-6 py-10 print:px-0 print:py-0">
        {/* Meta banner */}
        <div
          className="rounded-2xl p-5 mb-8 flex items-start gap-4 print:hidden"
          style={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}
        >
          <div
            className="p-3 rounded-xl shrink-0"
            style={{ background: "hsl(var(--primary)/.15)" }}
          >
            <FileText className="w-6 h-6" style={{ color: "hsl(var(--primary))" }} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-white text-sm">{filename}</p>
            <p className="text-xs mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
              {findingsCount} findings · {charts.length} charts embedded
              {completedAt && ` · Completed ${new Date(completedAt).toLocaleString()}`}
            </p>
          </div>
          <a
            href={`/analysis/${id}`}
            className="flex items-center gap-1 text-xs shrink-0 hover:opacity-80 transition-opacity"
            style={{ color: "hsl(var(--primary))" }}
          >
            <ExternalLink className="w-3 h-3" />
            View Analysis
          </a>
        </div>

        {/* The actual report */}
        <ReportViewer
          markdown={markdown}
          filename={filename.replace(/\.[^.]+$/, "")}
          showActions={false}
          charts={charts}
          onDownloadPdf={handleDownloadPdf}
          pdfLoading={pdfLoading}
        />
      </div>
    </div>
  );
}
