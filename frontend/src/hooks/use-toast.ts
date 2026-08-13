"use client";

import { useState, useCallback, useRef } from "react";
import type { ToastItem, ToastVariant } from "@/components/toast";

let _globalAddToast: ((variant: ToastVariant, message: string, duration?: number) => void) | null = null;

/**
 * Register the global toast dispatcher.
 * Called once by the layout that mounts <ToastContainer />.
 */
export function _registerToastDispatcher(
  fn: (variant: ToastVariant, message: string, duration?: number) => void
) {
  _globalAddToast = fn;
}

/**
 * Imperative toast API — call from anywhere without hooks.
 * Falls back to console if toast container not mounted yet.
 *
 * Usage:
 *   import { toast } from "@/hooks/use-toast";
 *   toast.success("Analysis started!");
 *   toast.error("Upload failed — file too large.");
 */
export const toast = {
  success: (message: string, duration?: number) =>
    _globalAddToast?.("success", message, duration) ?? console.log("[toast:success]", message),
  error: (message: string, duration?: number) =>
    _globalAddToast?.("error", message, duration) ?? console.error("[toast:error]", message),
  warning: (message: string, duration?: number) =>
    _globalAddToast?.("warning", message, duration) ?? console.warn("[toast:warning]", message),
  info: (message: string, duration?: number) =>
    _globalAddToast?.("info", message, duration) ?? console.info("[toast:info]", message),
};

/**
 * Hook for the layout component that owns the toast list state.
 * Returns the list of toasts and the functions to manage them.
 */
export function useToastManager() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const addToast = useCallback(
    (variant: ToastVariant, message: string, duration?: number) => {
      const id = `toast-${Date.now()}-${counter.current++}`;
      setToasts((prev) => [...prev, { id, variant, message, duration }]);
    },
    []
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, addToast, dismissToast };
}
