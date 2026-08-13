"use client";

import { useEffect, useRef } from "react";
import { CheckCircle2, XCircle, AlertCircle, Info, X } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;
  variant: ToastVariant;
  message: string;
  duration?: number;
}

// ── Config ────────────────────────────────────────────────────────────────────

const VARIANT_CONFIG: Record<ToastVariant, {
  icon: typeof CheckCircle2;
  bg: string;
  border: string;
  iconColor: string;
}> = {
  success: {
    icon: CheckCircle2,
    bg: "rgba(16,185,129,.12)",
    border: "rgba(16,185,129,.3)",
    iconColor: "hsl(142 76% 50%)",
  },
  error: {
    icon: XCircle,
    bg: "rgba(239,68,68,.12)",
    border: "rgba(239,68,68,.3)",
    iconColor: "hsl(0 84% 60%)",
  },
  warning: {
    icon: AlertCircle,
    bg: "rgba(245,158,11,.12)",
    border: "rgba(245,158,11,.3)",
    iconColor: "hsl(38 92% 60%)",
  },
  info: {
    icon: Info,
    bg: "rgba(99,102,241,.12)",
    border: "rgba(99,102,241,.3)",
    iconColor: "hsl(262 83% 64%)",
  },
};

// ── Single Toast ──────────────────────────────────────────────────────────────

interface ToastProps {
  item: ToastItem;
  onDismiss: (id: string) => void;
}

export function Toast({ item, onDismiss }: ToastProps) {
  const cfg = VARIANT_CONFIG[item.variant];
  const Icon = cfg.icon;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const duration = item.duration ?? 4000;
    timer.current = setTimeout(() => onDismiss(item.id), duration);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [item.id, item.duration, onDismiss]);

  return (
    <div
      role="alert"
      aria-live="polite"
      className="flex items-start gap-3 px-4 py-3 rounded-xl border shadow-xl animate-fade-in-up"
      style={{
        background: cfg.bg,
        borderColor: cfg.border,
        backdropFilter: "blur(16px)",
        minWidth: "280px",
        maxWidth: "420px",
      }}
    >
      <Icon className="w-4 h-4 mt-0.5 shrink-0" style={{ color: cfg.iconColor }} />
      <p className="text-sm text-white/90 flex-1 leading-snug">{item.message}</p>
      <button
        onClick={() => onDismiss(item.id)}
        className="shrink-0 mt-0.5 opacity-40 hover:opacity-80 transition-opacity"
      >
        <X className="w-3.5 h-3.5 text-white" />
      </button>
    </div>
  );
}

// ── Toast Container ───────────────────────────────────────────────────────────

interface ToastContainerProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((item) => (
        <div key={item.id} className="pointer-events-auto">
          <Toast item={item} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
