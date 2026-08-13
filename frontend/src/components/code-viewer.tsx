"use client";

import { useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp, Code2 } from "lucide-react";

interface CodeViewerProps {
  code: string;
  language?: string;
  title?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  maxHeight?: string;
}

export function CodeViewer({
  code,
  language = "python",
  title,
  collapsible = true,
  defaultExpanded = false,
  maxHeight = "400px",
}: CodeViewerProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  if (!code) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl overflow-hidden border"
      style={{ borderColor: "rgba(139,92,246,.2)", background: "#0a0a0f" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b"
        style={{ borderColor: "rgba(139,92,246,.15)", background: "#0d0d14" }}>
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full" style={{ background: "#ff5f57" }} />
            <div className="w-3 h-3 rounded-full" style={{ background: "#febc2e" }} />
            <div className="w-3 h-3 rounded-full" style={{ background: "#28c840" }} />
          </div>
          {title && (
            <span className="text-xs font-medium ml-2" style={{ color: "rgba(255,255,255,.4)" }}>
              {title}
            </span>
          )}
          <span className="text-xs px-1.5 py-0.5 rounded font-mono"
            style={{ background: "rgba(139,92,246,.15)", color: "hsl(262 83% 74%)" }}>
            {language}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            id="code-copy-btn"
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors"
            style={{ color: copied ? "hsl(142 76% 50%)" : "rgba(255,255,255,.4)" }}>
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied!" : "Copy"}
          </button>
          {collapsible && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="text-xs px-2 py-1 rounded transition-colors flex items-center gap-1"
              style={{ color: "rgba(255,255,255,.4)" }}>
              {expanded
                ? <><ChevronUp className="w-3.5 h-3.5" /> Collapse</>
                : <><ChevronDown className="w-3.5 h-3.5" /> Expand</>}
            </button>
          )}
        </div>
      </div>

      {/* Code body */}
      {(!collapsible || expanded) && (
        <div className="overflow-auto" style={{ maxHeight }}>
          <pre className="p-4 text-xs leading-relaxed m-0"
            style={{ fontFamily: "'Fira Code', 'Cascadia Code', 'Consolas', monospace", color: "#a5b4fc" }}>
            <code>{highlightPython(code)}</code>
          </pre>
        </div>
      )}

      {/* Collapsed preview */}
      {collapsible && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="w-full flex items-center gap-2 px-4 py-3 text-xs text-left transition-colors hover:bg-white/[.02]"
          style={{ color: "rgba(255,255,255,.35)" }}>
          <Code2 className="w-3.5 h-3.5 shrink-0" />
          <span className="font-mono truncate">{code.split("\n")[0]}</span>
          <span className="shrink-0 ml-auto">{code.split("\n").length} lines</span>
        </button>
      )}
    </div>
  );
}

/** Minimal Python syntax colouring without a library dependency */
function highlightPython(code: string): string {
  // We render as plain text — the styled pre/code gives sufficient readability
  // A full highlighter (shiki/prism) can be added in Phase 7 polish
  return code;
}
