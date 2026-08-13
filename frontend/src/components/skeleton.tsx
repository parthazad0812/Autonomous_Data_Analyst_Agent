"use client";

/**
 * Skeleton loading components — reuse the `.skeleton` CSS shimmer class.
 *
 * Usage:
 *   <SkeletonCard />             — session/report card placeholder
 *   <SkeletonText lines={3} />   — paragraph placeholder
 *   <SkeletonRow />              — single table/list row placeholder
 *   <SkeletonAnalysisPage />     — full analysis page placeholder
 */

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

// ── Primitive ─────────────────────────────────────────────────────────────────

export function Skeleton({ className = "", style }: SkeletonProps) {
  return <div className={`skeleton ${className}`} style={style} />;
}

// ── Text lines ────────────────────────────────────────────────────────────────

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  const widths = ["100%", "85%", "70%", "90%", "60%"];
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4 rounded-md"
          style={{ width: widths[i % widths.length] }}
        />
      ))}
    </div>
  );
}

// ── Session / result card ─────────────────────────────────────────────────────

export function SkeletonCard() {
  return (
    <div
      className="rounded-xl border p-5 space-y-3"
      style={{ borderColor: "hsl(var(--border))", background: "rgba(255,255,255,.03)" }}
    >
      {/* Header row */}
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-lg shrink-0" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-4 rounded w-2/3" />
          <Skeleton className="h-3 rounded w-1/3" />
        </div>
        <Skeleton className="h-6 w-20 rounded-full shrink-0" />
      </div>
      {/* Meta row */}
      <div className="flex gap-4">
        <Skeleton className="h-3 rounded w-24" />
        <Skeleton className="h-3 rounded w-20" />
        <Skeleton className="h-3 rounded w-16" />
      </div>
      {/* Footer */}
      <Skeleton className="h-8 rounded-lg w-28" />
    </div>
  );
}

// ── List row ──────────────────────────────────────────────────────────────────

export function SkeletonRow() {
  return (
    <div
      className="rounded-xl border p-4 flex items-center gap-3"
      style={{ borderColor: "hsl(var(--border))", background: "rgba(255,255,255,.02)" }}
    >
      <Skeleton className="w-8 h-8 rounded-lg shrink-0" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-3.5 rounded w-1/2" />
        <Skeleton className="h-3 rounded w-1/3" />
      </div>
      <Skeleton className="h-6 w-16 rounded-full shrink-0" />
    </div>
  );
}

// ── Full analysis page skeleton ───────────────────────────────────────────────

export function SkeletonAnalysisPage() {
  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header card */}
      <div
        className="rounded-xl border p-6 space-y-3"
        style={{ borderColor: "rgba(139,92,246,.2)", background: "rgba(255,255,255,.03)" }}
      >
        <Skeleton className="h-7 rounded w-72" />
        <Skeleton className="h-4 rounded w-48" />
      </div>

      {/* Pipeline bar */}
      <div
        className="rounded-xl border p-5"
        style={{ borderColor: "rgba(139,92,246,.15)", background: "rgba(255,255,255,.02)" }}
      >
        <Skeleton className="h-3 rounded w-28 mb-4" />
        <div className="flex items-center gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-1">
              <Skeleton className="w-10 h-10 rounded-full" />
              {i < 5 && <Skeleton className="w-5 h-0.5" />}
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{ borderColor: "rgba(139,92,246,.15)", background: "rgba(255,255,255,.02)" }}
      >
        {/* Tab bar */}
        <div className="flex border-b gap-1 p-1" style={{ borderColor: "hsl(var(--border))" }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 rounded-lg" style={{ width: `${80 + i * 10}px` }} />
          ))}
        </div>
        {/* Content */}
        <div className="p-6 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Dashboard sessions skeleton ───────────────────────────────────────────────

export function SkeletonDashboard() {
  return (
    <div className="space-y-6">
      {/* Upload zone placeholder */}
      <div
        className="rounded-xl border-2 border-dashed p-10 flex flex-col items-center gap-3"
        style={{ borderColor: "hsl(var(--border))" }}
      >
        <Skeleton className="w-12 h-12 rounded-full" />
        <Skeleton className="h-5 rounded w-48" />
        <Skeleton className="h-4 rounded w-64" />
      </div>
      {/* Session cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}
