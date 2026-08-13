"use client";

import { CheckCircle2, AlertTriangle, TrendingUp, BarChart3, Database, Zap } from "lucide-react";

interface FindingCardProps {
  id: string;
  finding_type: string | null;
  title: string;
  description: string | null;
  evidence: Record<string, unknown> | null;
  confidence: string | null;
  hypothesis: string | null;
  visualization_path: string | null;
  created_at: string;
}

const TYPE_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  profile:        { icon: Database, color: "hsl(196 100% 50%)", label: "Profile" },
  correlation:    { icon: TrendingUp, color: "hsl(142 76% 50%)", label: "Correlation" },
  distribution:   { icon: BarChart3, color: "hsl(262 83% 64%)", label: "Distribution" },
  outlier:        { icon: AlertTriangle, color: "hsl(38 92% 60%)", label: "Outlier" },
  pattern:        { icon: Zap, color: "hsl(10 100% 60%)", label: "Pattern" },
  hypothesis:     { icon: CheckCircle2, color: "hsl(142 76% 50%)", label: "Hypothesis" },
  visualization:  { icon: BarChart3, color: "hsl(280 70% 65%)", label: "Chart" },
  cluster:        { icon: Database, color: "hsl(196 80% 55%)", label: "Cluster" },
};

const CONFIDENCE_COLORS = {
  high:   { bg: "rgba(34,197,94,.1)",  border: "rgba(34,197,94,.25)",  text: "hsl(142 76% 50%)" },
  medium: { bg: "rgba(234,179,8,.1)",  border: "rgba(234,179,8,.25)",  text: "hsl(48 96% 53%)" },
  low:    { bg: "rgba(239,68,68,.1)",  border: "rgba(239,68,68,.25)",  text: "hsl(0 84% 60%)" },
};

export function FindingCard(props: FindingCardProps) {
  const typeCfg = TYPE_CONFIG[props.finding_type ?? "profile"] ?? TYPE_CONFIG.profile;
  const confCfg = CONFIDENCE_COLORS[(props.confidence ?? "medium") as keyof typeof CONFIDENCE_COLORS] ?? CONFIDENCE_COLORS.medium;
  const TypeIcon = typeCfg.icon;

  // Extract key evidence values
  const evidenceEntries = props.evidence
    ? Object.entries(props.evidence)
        .filter(([k]) => !["agent_name", "chart_id"].includes(k))
        .slice(0, 4)
    : [];

  return (
    <div className="glass-card rounded-xl p-5 border flex flex-col gap-3 transition-all duration-200 hover-glow"
      style={{ borderColor: `${typeCfg.color}15` }}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
            style={{ background: `${typeCfg.color}18` }}>
            <TypeIcon className="w-4 h-4" style={{ color: typeCfg.color }} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white leading-tight">{props.title}</p>
            <span className="text-xs mt-0.5" style={{ color: typeCfg.color }}>{typeCfg.label}</span>
          </div>
        </div>
        {props.confidence && (
          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full font-medium capitalize"
            style={{ background: confCfg.bg, border: `1px solid ${confCfg.border}`, color: confCfg.text }}>
            {props.confidence}
          </span>
        )}
      </div>

      {/* Description */}
      {props.description && (
        <p className="text-xs leading-relaxed" style={{ color: "rgba(255,255,255,.65)" }}>
          {props.description}
        </p>
      )}

      {/* Evidence pills */}
      {evidenceEntries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {evidenceEntries.map(([key, val]) => (
            <span key={key} className="text-xs px-2 py-0.5 rounded-md font-mono"
              style={{ background: "rgba(255,255,255,.04)", color: "rgba(255,255,255,.45)", border: "1px solid rgba(255,255,255,.08)" }}>
              {key}: {typeof val === "number" ? (val as number).toFixed ? (val as number).toFixed(3) : val : String(val).slice(0, 30)}
            </span>
          ))}
        </div>
      )}

      {/* Hypothesis */}
      {props.hypothesis && (
        <p className="text-xs italic" style={{ color: "hsl(262 83% 74%)" }}>
          ↳ {props.hypothesis}
        </p>
      )}
    </div>
  );
}
