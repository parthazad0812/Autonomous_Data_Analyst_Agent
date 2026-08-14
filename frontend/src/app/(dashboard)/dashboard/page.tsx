"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Brain, Sparkles, Clock, CheckCircle2, XCircle, Loader2, Trash2, ArrowRight } from "lucide-react";
import { UploadZone } from "@/components/upload-zone";
import { DataPreview } from "@/components/data-preview";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { AnalysisSession } from "@/types/session";
import { toast } from "@/hooks/use-toast";
import { SkeletonCard } from "@/components/skeleton";
import { motion, AnimatePresence } from "framer-motion";

interface Profile {
  rows: number;
  columns: number;
  column_names: string[];
  columns_meta: unknown[];
  sample_rows: Record<string, unknown>[];
  numeric_cols: string[];
  text_cols: string[];
  datetime_cols: string[];
  has_nulls: boolean;
  memory_mb: number;
}

interface UploadResult {
  session_id: string;
  dataset_filename: string;
  profile: Profile;
}

const STATUS_CONFIG = {
  pending: { icon: Clock, color: "#A1A1AA", bg: "rgba(255,255,255,0.05)", label: "Pending" },
  running: { icon: Loader2, color: "#8B5CF6", bg: "rgba(139,92,246,0.15)", label: "Running" },
  completed: { icon: CheckCircle2, color: "#10B981", bg: "rgba(16,185,129,0.15)", label: "Completed" },
  failed: { icon: XCircle, color: "#EF4444", bg: "rgba(239,68,68,0.15)", label: "Failed" },
};

function formatDate(iso: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

export default function DashboardPage() {
  const router = useRouter();
  const user = auth.getUser();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadSessions();
  }, []);

  async function loadSessions() {
    setSessionsLoading(true);
    try {
      const res = await api.get("/upload/sessions");
      setSessions(res.data.sessions);
    } catch {
      // silently fail — user may have no sessions yet
    } finally {
      setSessionsLoading(false);
    }
  }

  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    setUploadResult(null);
    setUploadError(null);
  }, []);

  async function handleUpload() {
    if (!selectedFile) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      if (query.trim()) formData.append("query", query.trim());

      const progressInterval = setInterval(() => {
        setUploadProgress((p) => Math.min(p + 8, 85));
      }, 400);

      const res = await api.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      clearInterval(progressInterval);
      setUploadProgress(100);
      setUploadResult(res.data);
      await loadSessions();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      const msg = axiosErr.response?.data?.detail ?? "Upload failed. Please try again.";
      setUploadError(msg);
      toast.error(msg);
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadProgress(0), 600);
    }
  }

  async function handleDelete(sessionId: string) {
    setDeletingId(sessionId);
    try {
      await api.delete(`/upload/sessions/${sessionId}`);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      toast.success("Session deleted.");
    } catch {
      toast.error("Could not delete session. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-8 pb-16 w-full max-w-6xl mx-auto">
      {/* ── Header ── */}
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-2">
          Overview
        </h1>
        <p className="text-white/40 text-sm">
          Welcome back, {user?.full_name?.split(" ")[0] || "User"}. Upload a dataset to begin a new analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-8 items-start">
        {/* ── Upload Panel ── */}
        <motion.div
          layout
          className="glass-card-elevated p-7 flex flex-col gap-6 w-full"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-white/50" />
              New Analysis
            </h2>
          </div>

          <UploadZone
            onFileSelect={handleFileSelect}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
          />

          <AnimatePresence mode="popLayout">
            {selectedFile && !isUploading && !uploadResult && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-6 overflow-hidden pt-2"
              >
                <div className="space-y-2">
                  <label className="input-label">Context / Goal (Optional)</label>
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. Find what correlates with higher customer churn."
                    rows={3}
                    className="input-field resize-none"
                  />
                </div>

                {uploadError && (
                  <div className="rounded-xl px-5 py-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 font-medium flex items-start gap-3">
                    <XCircle className="w-5 h-5 shrink-0" />
                    {uploadError}
                  </div>
                )}

                <button
                  id="start-analysis-btn"
                  onClick={handleUpload}
                  className="btn-brand w-full py-3 mt-1"
                >
                  <Brain className="w-4 h-4" />
                  Analyze Dataset
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* ── Recent sessions ── */}
        <div className="flex flex-col gap-5">
          <h2 className="text-[11px] font-bold text-white/40 uppercase tracking-widest px-2">
            Recent Activity
          </h2>

          <div className="space-y-4">
            {sessionsLoading ? (
              Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            ) : sessions.length === 0 ? (
              <div className="glass-card border-dashed p-10 text-center flex flex-col items-center justify-center">
                <div className="w-11 h-11 rounded-lg bg-white/[0.04] flex items-center justify-center mb-4">
                  <Clock className="w-5 h-5 text-white/40" />
                </div>
                <p className="text-sm font-medium text-white/50">No analyses yet.</p>
              </div>
            ) : (
              sessions.slice(0, 5).map((session) => {
                const cfg = STATUS_CONFIG[session.status as keyof typeof STATUS_CONFIG] ?? STATUS_CONFIG.pending;
                const StatusIcon = cfg.icon;
                return (
                  <div
                    key={session.id}
                    onClick={() => router.push(`/analysis/${session.id}`)}
                    className="group flex items-center gap-4 p-4 rounded-xl border border-white/[0.06] bg-white/[0.02] cursor-pointer hover:bg-white/[0.04] hover:border-white/[0.1] transition-all relative overflow-hidden"
                  >
                    <div className="w-10 h-10 rounded-lg shrink-0 flex items-center justify-center" style={{ background: cfg.bg }}>
                      <StatusIcon className={`w-4 h-4 ${session.status === "running" ? "animate-spin" : ""}`} style={{ color: cfg.color }} />
                    </div>

                    <div className="flex-1 min-w-0 pr-10">
                      <p className="text-sm font-bold text-white/90 truncate mb-1 group-hover:text-white transition-colors">
                        {session.title ?? session.dataset_filename}
                      </p>
                      <p className="text-xs font-medium text-white/50 truncate flex items-center gap-1.5">
                        <span>{session.dataset_rows != null ? `${session.dataset_rows.toLocaleString()} rows` : "Unknown rows"}</span>
                        <span>·</span>
                        <span>{formatDate(session.created_at)}</span>
                      </p>
                    </div>

                    <div className="absolute right-5 top-1/2 -translate-y-1/2 flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(session.id); }}
                        disabled={deletingId === session.id}
                        className="p-2.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400 text-white/30 transition-all"
                        title="Delete session"
                      >
                        {deletingId === session.id
                          ? <Loader2 className="w-4 h-4 animate-spin" />
                          : <Trash2 className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* ── Data preview (after upload) ── */}
      {uploadResult && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card-elevated p-7 flex flex-col gap-6 mt-8"
        >
          <div className="flex items-center justify-between border-b border-white/[0.04] pb-5">
            <div>
              <h2 className="text-lg font-bold text-white mb-1">Data Profile</h2>
              <p className="text-sm text-white/40">{uploadResult.dataset_filename}</p>
            </div>
            <button
              onClick={() => router.push(`/analysis/${uploadResult.session_id}`)}
              className="btn-primary text-sm px-5 py-2.5"
            >
              Start Pipeline
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
          <DataPreview
            profile={uploadResult.profile as Parameters<typeof DataPreview>[0]["profile"]}
            filename={uploadResult.dataset_filename}
          />
        </motion.div>
      )}
    </div>
  );
}
