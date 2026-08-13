"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { useState, useMemo } from "react";
import { Download, FileText, Printer, ChevronRight } from "lucide-react";
import { motion } from "framer-motion";

interface ChartRef {
  path: string;
  url: string;
}

interface ReportViewerProps {
  markdown: string;
  filename?: string;
  showActions?: boolean;
  /** Chart URL map — used to replace ![...](charts/...) references inline */
  charts?: ChartRef[];
  /** Called when "Download PDF" is clicked — parent handles the request */
  onDownloadPdf?: () => void;
  /** Whether PDF download is loading */
  pdfLoading?: boolean;
}

export function ReportViewer({
  markdown,
  filename = "report",
  showActions = true,
  charts = [],
  onDownloadPdf,
  pdfLoading = false,
}: ReportViewerProps) {
  const [printing, setPrinting] = useState(false);

  // Build a map from chart path/filename → presigned URL
  const chartMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const c of charts) {
      map[c.path] = c.url;
      // Also index by bare filename
      const fname = c.path.split("/").pop() ?? "";
      if (fname) map[fname] = c.url;
    }
    return map;
  }, [charts]);

  /** Replace chart path references in markdown with real presigned URLs */
  const resolvedMarkdown = useMemo(() => {
    if (charts.length === 0) return markdown;
    return markdown.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
      // Try exact match, then filename match
      const resolved = chartMap[src] ?? chartMap[src.split("/").pop() ?? ""];
      return resolved ? `![${alt}](${resolved})` : match;
    });
  }, [markdown, chartMap, charts]);

  const handleDownloadMd = () => {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    setPrinting(true);
    setTimeout(() => {
      window.print();
      setPrinting(false);
    }, 100);
  };

  if (!markdown) {
    return (
      <div className="flex flex-col items-center justify-center h-64 opacity-50">
        <FileText className="w-10 h-10 mb-4 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Report is empty.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Actions bar */}
      {showActions && (
        <div className="flex items-center justify-between flex-wrap gap-4 pb-4 border-b border-border/50">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <div className="p-1.5 rounded bg-primary/10 text-primary">
              <FileText className="w-4 h-4" />
            </div>
            Executive Report
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              disabled={printing}
              className="btn-secondary px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-2"
            >
              <Printer className="w-3.5 h-3.5" />
              Print
            </button>
            <button
              onClick={handleDownloadMd}
              className="btn-secondary px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-2"
            >
              <Download className="w-3.5 h-3.5" />
              Markdown
            </button>
          </div>
        </div>
      )}

      {/* Rendered markdown */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="report-content max-w-4xl mx-auto bg-black/40 p-6 md:p-10 rounded-2xl border border-border/50 shadow-2xl"
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            h1: ({ children }) => (
              <h1 className="text-3xl font-bold tracking-tight text-white mb-6 pb-4 border-b border-white/10">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-xl font-semibold tracking-tight text-white mt-8 mb-4 flex items-center gap-2">
                <ChevronRight className="w-5 h-5 text-primary" />
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-lg font-medium text-white/90 mt-6 mb-3">
                {children}
              </h3>
            ),
            p: ({ children }) => (
              <p className="text-sm leading-relaxed text-muted-foreground mb-4">
                {children}
              </p>
            ),
            ul: ({ children }) => (
              <ul className="space-y-2 mb-4 ml-2 list-none text-sm text-muted-foreground">
                {children}
              </ul>
            ),
            li: ({ children }) => (
              <li className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 rounded-full bg-primary/60 mt-2 shrink-0" />
                <span className="leading-relaxed">{children}</span>
              </li>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-white">{children}</strong>
            ),
            em: ({ children }) => (
              <em className="text-white/80 italic">{children}</em>
            ),
            img: ({ src, alt }) => {
              if (!src) return null;
              return (
                <span className="block my-8 relative group">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={src}
                    alt={alt ?? "chart"}
                    className="w-full rounded-xl border border-border/50 bg-[#050505] shadow-lg max-h-[500px] object-contain transition-transform group-hover:scale-[1.01]"
                  />
                  {alt && (
                    <span className="block text-center text-xs mt-3 text-muted-foreground/60 uppercase tracking-widest font-mono">
                      {alt}
                    </span>
                  )}
                </span>
              );
            },
            code: ({ children, className }) => {
              const isBlock = className?.includes("language-");
              if (isBlock) {
                return (
                  <pre className="rounded-xl p-4 my-6 bg-[#0A0A0A] border border-border/50 overflow-x-auto shadow-inner">
                    <code className="text-xs font-mono text-[#A5B4FC] leading-relaxed">
                      {children}
                    </code>
                  </pre>
                );
              }
              return (
                <code className="px-1.5 py-0.5 rounded text-xs font-mono bg-white/5 border border-white/10 text-white/90">
                  {children}
                </code>
              );
            },
            table: ({ children }) => (
              <div className="my-6 overflow-x-auto rounded-xl border border-border/50 bg-black/20 shadow-inner">
                <table className="w-full text-sm text-left">{children}</table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-white/5 border-b border-white/5">{children}</thead>
            ),
            th: ({ children }) => (
              <th className="px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-4 py-3 text-sm text-muted-foreground border-b border-white/5">
                {children}
              </td>
            ),
            blockquote: ({ children }) => (
              <blockquote className="my-6 pl-4 border-l-2 border-primary/50 text-sm text-muted-foreground italic bg-primary/5 py-2 pr-4 rounded-r-lg">
                {children}
              </blockquote>
            ),
            hr: () => <hr className="my-10 border-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />,
          }}
        >
          {resolvedMarkdown}
        </ReactMarkdown>
      </motion.div>
    </div>
  );
}
