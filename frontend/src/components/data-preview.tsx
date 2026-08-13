"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, AlertCircle, HardDrive, Columns, Rows, Hash, Type, Calendar, ToggleLeft } from "lucide-react";
import { motion } from "framer-motion";

interface ColumnMeta {
  name: string;
  dtype: string;
  col_type: "numeric" | "text" | "datetime" | "boolean";
  null_count: number;
  null_pct: number;
  unique_count: number;
  mean?: number;
  min?: number;
  max?: number;
  top_values?: Record<string, number>;
}

interface DatasetProfile {
  rows: number;
  columns: number;
  column_names: string[];
  columns_meta: ColumnMeta[];
  sample_rows: Record<string, unknown>[];
  numeric_cols: string[];
  text_cols: string[];
  datetime_cols: string[];
  has_nulls: boolean;
  memory_mb: number;
}

interface DataPreviewProps {
  profile: DatasetProfile;
  filename: string;
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  numeric: Hash,
  text: Type,
  datetime: Calendar,
  boolean: ToggleLeft,
};

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  numeric: { bg: "rgba(59,130,246,0.1)", border: "rgba(59,130,246,0.2)", text: "#60A5FA" },
  text: { bg: "rgba(167,139,250,0.1)", border: "rgba(167,139,250,0.2)", text: "#C084FC" },
  datetime: { bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.2)", text: "#FBBF24" },
  boolean: { bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.2)", text: "#34D399" },
};

const PAGE_SIZE = 10;

export function DataPreview({ profile, filename }: DataPreviewProps) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(profile.sample_rows.length / PAGE_SIZE);
  const pageRows = profile.sample_rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function formatCellValue(val: unknown): string {
    if (val === null || val === undefined) return "—";
    if (typeof val === "number") {
      return Number.isInteger(val) ? val.toString() : val.toFixed(4);
    }
    const s = String(val);
    return s.length > 40 ? s.slice(0, 40) + "…" : s;
  }

  function isNull(val: unknown) {
    return val === null || val === undefined;
  }

  return (
    <div className="space-y-6">
      {/* ── Summary stats ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Total Rows", value: profile.rows.toLocaleString(), icon: Rows },
          { label: "Total Columns", value: profile.columns.toString(), icon: Columns },
          { label: "Memory Usage", value: `${profile.memory_mb} MB`, icon: HardDrive },
          {
            label: "Missing Values",
            value: profile.has_nulls ? "Detected" : "Clean",
            warn: profile.has_nulls,
            icon: AlertCircle
          },
        ].map(({ label, value, warn, icon: Icon }) => (
          <div key={label} className="bg-white/[0.02] border border-white/5 px-4 py-3 rounded-xl flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                {label}
              </p>
              <p
                className="text-xl font-semibold"
                style={{ color: warn ? "#F87171" : "white" }}
              >
                {value}
              </p>
            </div>
            <div className="p-2 bg-white/5 rounded-lg shrink-0">
               <Icon className="w-4 h-4 text-muted-foreground" style={{ color: warn ? "#F87171" : undefined }} />
            </div>
          </div>
        ))}
      </div>

      {/* ── Column metadata chips ── */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Detected Schema
        </p>
        <div className="flex flex-wrap gap-2">
          {profile.columns_meta.map((col) => {
            const colors = TYPE_COLORS[col.col_type] ?? TYPE_COLORS.text;
            const ColIcon = TYPE_ICONS[col.col_type] ?? TYPE_ICONS.text;
            return (
              <div
                key={col.name}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border cursor-help transition-colors hover:brightness-110"
                style={{ background: colors.bg, borderColor: colors.border }}
                title={`${col.dtype} · ${col.null_pct}% nulls · ${col.unique_count} unique`}
              >
                <ColIcon className="w-3.5 h-3.5" style={{ color: colors.text }} />
                <span className="font-medium" style={{ color: colors.text }}>
                  {col.name}
                </span>
                {col.null_count > 0 && (
                  <span className="flex items-center gap-1 ml-1 px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded text-[10px] font-bold">
                    {col.null_pct}% Null
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Sample table ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Data Sample
          </p>
          {totalPages > 1 && (
            <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-1 rounded-md disabled:opacity-30 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs px-2 font-medium text-muted-foreground">
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page === totalPages - 1}
                className="p-1 rounded-md disabled:opacity-30 hover:bg-white/10 text-muted-foreground hover:text-white transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
        
        <div className="overflow-x-auto rounded-xl border border-border/50 bg-black/20 shadow-inner">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-white/5 border-b border-white/5">
                {profile.column_names.map((col) => {
                  const meta = profile.columns_meta.find((c) => c.name === col);
                  const colors = TYPE_COLORS[meta?.col_type ?? "text"] ?? TYPE_COLORS.text;
                  const ColIcon = TYPE_ICONS[meta?.col_type ?? "text"] ?? TYPE_ICONS.text;
                  return (
                    <th
                      key={col}
                      className="px-4 py-3 text-left font-medium whitespace-nowrap"
                      style={{ color: colors.text }}
                    >
                      <div className="flex items-center gap-1.5">
                        <ColIcon className="w-3.5 h-3.5 opacity-70" />
                        {col}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {pageRows.map((row, i) => (
                <tr
                  key={i}
                  className="transition-colors hover:bg-white/5 group"
                >
                  {profile.column_names.map((col) => {
                    const val = row[col];
                    const nullVal = isNull(val);
                    return (
                      <td
                        key={col}
                        className={`px-4 py-2.5 whitespace-nowrap font-mono text-xs ${
                          nullVal ? "text-muted-foreground/50 italic" : "text-foreground/80 group-hover:text-foreground"
                        }`}
                      >
                        {formatCellValue(val)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
