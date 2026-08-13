"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Brain, Clock, CheckCircle2, XCircle, Loader2,
  Database, Zap, BarChart3, FileText, Code2, ImageIcon, 
  ExternalLink, Download, Play, Terminal
} from "lucide-react";
import { api } from "@/lib/api";
import { useAnalysisStream } from "@/hooks/use-analysis-stream";
import { toast } from "@/hooks/use-toast";
import { CodeViewer } from "@/components/code-viewer";
import { ChartGrid } from "@/components/chart-renderer";
import { ReportViewer } from "@/components/report-viewer";
import { FindingCard } from "@/components/finding-card";
import { SkeletonAnalysisPage } from "@/components/skeleton";
import { motion, AnimatePresence } from "framer-motion";

// ── Types ─────────────────────────────────────────────────────────────────────
interface SessionStatus {
  session_id: string;
  status: string;
  dataset_filename: string;
  steps_completed: number;
  findings_count: number;
  has_report: boolean;
  created_at: string;
  completed_at: string | null;
}

interface AgentStep {
  id: string;
  agent_name: string;
  step_index: number;
  status: string;
  code_executed: string | null;
  code_output: string | null;
  error_message: string | null;
  duration_seconds: number | null;
  output_data: Record<string, unknown> | null;
}

interface Finding {
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

interface StreamEvent {
  type: string;
  agent?: string;
  status?: string;
  message?: string;
  data?: Record<string, unknown>;
  timestamp?: string;
}

// ── Agent config ──────────────────────────────────────────────────────────────
const AGENTS = [
  { key: "orchestrator", label: "Orchestrator", icon: Brain, color: "#A78BFA" },
  { key: "profiler",     label: "Profiler",     icon: Database, color: "#3B82F6" },
  { key: "eda",          label: "EDA",          icon: BarChart3, color: "#10B981" },
  { key: "statistician", label: "Stats",        icon: Zap, color: "#FBBF24" },
  { key: "visualizer",   label: "Visualizer",   icon: ImageIcon, color: "#F87171" },
  { key: "reporter",     label: "Reporter",     icon: FileText, color: "#C084FC" },
];

function formatBytes(n: number) {
  return n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string; icon: typeof Loader2; spin?: boolean }> = {
    running:   { color: "#8B5CF6", bg: "rgba(139,92,246,0.15)", icon: Loader2, spin: true },
    completed: { color: "#10B981", bg: "rgba(16,185,129,0.15)", icon: CheckCircle2 },
    failed:    { color: "#EF4444", bg: "rgba(239,68,68,0.15)", icon: XCircle },
    skipped:   { color: "#A1A1AA", bg: "rgba(255,255,255,0.08)", icon: Clock },
    pending:   { color: "#FBBF24", bg: "rgba(251,191,36,0.15)", icon: Clock },
  };
  const cfg = map[status] ?? map.pending;
  const Icon = cfg.icon;
  return (
    <span className="flex items-center gap-2 px-4 py-1.5 rounded-xl text-xs font-bold uppercase tracking-widest border"
      style={{ background: cfg.bg, color: cfg.color, borderColor: `${cfg.color}30` }}>
      <Icon className={`w-4 h-4 ${cfg.spin ? "animate-spin" : ""}`} />
      {status}
    </span>
  );
}

// ── Step card ─────────────────────────────────────────────────────────────────
function StepCard({ step }: { step: AgentStep }) {
  const agent = AGENTS.find(a => a.key === step.agent_name) ?? AGENTS[0];
  const AgIcon = agent.icon;
  const msg = (step.output_data as Record<string, string> | null)?.message ?? "";
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white/[0.02] rounded-xl overflow-hidden transition-all duration-300 border border-white/[0.06] hover:border-white/[0.1] shadow-lg shadow-black/10">
      <div 
        className="p-5 flex items-start gap-4 cursor-pointer hover:bg-white/[0.03] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-inner"
          style={{ background: `${agent.color}15`, border: `1px solid ${agent.color}30` }}>
          <AgIcon className="w-5 h-5" style={{ color: agent.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-sm font-bold text-white">{agent.label}</span>
            <span className="text-xs text-white/30">•</span>
            <span className="text-[11px] font-bold text-white/40 uppercase tracking-widest">Step {step.step_index}</span>
            {step.duration_seconds != null && (
              <>
                 <span className="text-xs text-white/30">•</span>
                 <span className="text-[11px] font-bold text-white/40">{step.duration_seconds.toFixed(1)}s</span>
              </>
            )}
          </div>
          {msg && <p className="text-sm text-white/70 leading-relaxed font-medium">{msg}</p>}
        </div>
        <div className="shrink-0 ml-4 pt-1.5">
           {step.status === "failed"
            ? <XCircle className="w-6 h-6 text-red-500" />
            : <CheckCircle2 className="w-6 h-6" style={{ color: agent.color }} />}
        </div>
      </div>

      <AnimatePresence>
        {expanded && (step.code_executed || step.error_message) && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-white/[0.06] bg-black/40"
          >
            {step.error_message && (
              <div className="p-4 m-4 rounded-xl bg-red-500/10 border border-red-500/20 text-[13px] text-red-400 font-mono shadow-inner">
                {step.error_message}
              </div>
            )}
            {step.code_executed && (
              <div className="p-5">
                <CodeViewer code={step.code_executed} title="Executed Code" defaultExpanded />
                {step.code_output && (
                  <div className="mt-5">
                    <p className="text-[11px] font-bold text-white/40 mb-2 uppercase tracking-widest">Console Output</p>
                    <pre className="text-[13px] rounded-xl p-5 overflow-x-auto max-h-60 bg-[#0A0A0A] border border-white/10 text-[#86efac] font-mono leading-relaxed shadow-inner">
                      {step.code_output}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Live stream terminal ────────────────────────────────────────────────────────
function StreamTerminal({ events, isRunning }: { events: StreamEvent[], isRunning: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="flex flex-col h-full bg-[#050505] rounded-2xl border border-white/[0.06] overflow-hidden shadow-2xl shadow-black/50">
      <div className="px-5 py-3.5 bg-black/60 border-b border-white/[0.06] flex items-center justify-between">
         <div className="flex items-center gap-3">
           <Terminal className="w-4 h-4 text-white/50" />
           <span className="text-[11px] font-bold text-white/50 uppercase tracking-widest">Agent Stream</span>
         </div>
         <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isRunning ? "bg-[#10B981] animate-pulse shadow-[0_0_8px_#10B981]" : "bg-white/20"}`} />
            <span className="text-[10px] font-bold uppercase tracking-widest text-white/50">{isRunning ? "Live" : "Stopped"}</span>
         </div>
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto p-5 space-y-2 font-mono text-[13px]">
        {events.length === 0 ? (
           <p className="text-white/30 italic">Waiting for orchestrator to initialize...</p>
        ) : (
          events.map((e, i) => {
            const agent = AGENTS.find(a => a.key === e.agent);
            return (
              <div key={i} className="flex items-start gap-3 hover:bg-white/[0.02] py-1 rounded-lg px-2 transition-colors">
                <span className="shrink-0 text-white/30 w-16">
                  {new Date(e.timestamp ?? Date.now()).toLocaleTimeString("en-US", { hour12: false, hour: '2-digit', minute: '2-digit', second:'2-digit' })}
                </span>
                {agent ? (
                  <span className="shrink-0 font-bold min-w-[110px]" style={{ color: agent.color }}>
                    [{agent.label}]
                  </span>
                ) : (
                  <span className="shrink-0 font-bold min-w-[110px] text-white/40">
                    [System]
                  </span>
                )}
                <span className="text-white/80 break-words flex-1 leading-relaxed">{e.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [session, setSession] = useState<SessionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [report, setReport] = useState<string | null>(null);
  const [charts, setCharts] = useState<Array<{ url: string; path: string }>>([]);
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([]);
  
  // View mode for right pane
  const [viewMode, setViewMode] = useState<"findings" | "report" | "charts">("report");
  const [pdfLoading, setPdfLoading] = useState(false);

  const isRunning = session?.status === "running";
  const hasStarted = session?.status !== "pending";

  const loadStatus = useCallback(async () => {
    if (!id) return;
    const r = await api.get(`/analysis/${id}/status`);
    setSession(r.data);
  }, [id]);

  const loadResults = useCallback(async () => {
    if (!id) return;
    try { const r = await api.get(`/analysis/${id}/steps`); setSteps(r.data); } catch {}
    try { const r = await api.get(`/analysis/${id}/findings`); setFindings(r.data); } catch {}
    try { const r = await api.get(`/analysis/${id}/report`); setReport(r.data.report_markdown); } catch {}
    try { const r = await api.get(`/analysis/${id}/charts`); setCharts(r.data); } catch {}
  }, [id]);

  useEffect(() => {
    if (!id) return;
    loadStatus().finally(() => setLoading(false));
  }, [id, loadStatus]);

  useEffect(() => {
    if (!isRunning) return;
    const t = setInterval(loadStatus, 5000);
    return () => clearInterval(t);
  }, [isRunning, loadStatus]);

  useEffect(() => {
    if (session?.status === "completed" || session?.status === "failed") loadResults();
  }, [session?.status, loadResults]);

  useAnalysisStream({
    sessionId: id ?? "",
    enabled: !!id,
    onEvent: (e) => {
      setStreamEvents(prev => [...prev, e as StreamEvent]);
      if (e.type === "agent_update") loadStatus();
    },
  });

  const startAnalysis = async () => {
    if (!id) return;
    setStarting(true);
    try {
      await api.post(`/analysis/${id}/start`);
      toast.info("Pipeline initializing...");
      await loadStatus();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const msg = e.response?.data?.detail ?? "Failed to start analysis";
      toast.error(msg);
    } finally {
      setStarting(false);
    }
  };

  const handleDownloadPdf = useCallback(async () => {
    if (pdfLoading || !id) return;
    setPdfLoading(true);
    try {
      const token = localStorage.getItem("access_token") ?? "";
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/analysis/${id}/report/pdf`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error(`PDF failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stem = (session?.dataset_filename ?? "report").replace(/\.[^.]+$/, "");
      a.download = `${stem}_analysis_report.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF download failed:", err);
      toast.error("PDF generation failed. Please try again.");
    } finally {
      setPdfLoading(false);
    }
  }, [id, pdfLoading, session?.dataset_filename]);

  if (loading) return <SkeletonAnalysisPage />;
  if (!session) return <div className="text-center py-16 text-muted-foreground">Session not found.</div>;

  return (
    <div className="flex flex-col h-full space-y-6 animate-in fade-in duration-500">
      {/* ── Top Bar ── */}
      <div className="flex items-center justify-between shrink-0 bg-white/[0.02] backdrop-blur-xl border border-white/[0.06] p-5 rounded-2xl shadow-xl shadow-black/20">
         <div className="flex items-center gap-5">
           <button onClick={() => router.push("/dashboard")} className="p-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-white/50 hover:text-white transition-all">
              <ArrowLeft className="w-5 h-5" />
           </button>
           <div>
             <h1 className="text-xl font-bold text-white tracking-tight mb-0.5">{session.dataset_filename}</h1>
             <p className="text-[13px] font-medium text-white/50">
                {new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(session.created_at))}
             </p>
           </div>
         </div>
         <div className="flex items-center gap-4">
            <StatusBadge status={session.status} />
            {!hasStarted && (
               <button onClick={startAnalysis} disabled={starting} className="btn-primary px-6 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 transition-all">
                 {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                 Start Pipeline
               </button>
            )}
         </div>
      </div>

      {/* ── Split Layout ── */}
      {hasStarted ? (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0 pb-6">
          
          {/* Left Pane: Agent Activity & Pipeline */}
          <div className="flex flex-col gap-6 min-h-0">
             
             {/* Pipeline Progress */}
             <div className="bg-white/[0.02] backdrop-blur-xl border border-white/[0.06] p-6 rounded-2xl flex items-center justify-between shrink-0 shadow-xl shadow-black/20">
               {AGENTS.map((agent, i) => {
                  const step = steps.find(s => s.agent_name === agent.key);
                  const isActive = streamEvents.some(e => e.agent === agent.key && e.status === "running") && isRunning;
                  const isDone = step?.status === "completed";
                  const isFailed = step?.status === "failed";
                  
                  let stateColor = "rgba(255,255,255,0.1)";
                  if (isActive) stateColor = agent.color;
                  if (isDone) stateColor = agent.color;
                  if (isFailed) stateColor = "#EF4444";

                  return (
                    <div key={agent.key} className="flex-1 flex items-center relative group">
                       <div className="flex flex-col items-center gap-3 relative z-10 mx-auto">
                          <div className={`w-10 h-10 rounded-full border-[3px] flex items-center justify-center bg-[#050505] transition-all duration-500`}
                               style={{ borderColor: stateColor, boxShadow: isActive ? `0 0 25px ${stateColor}60` : 'none' }}>
                             {isActive ? <Loader2 className="w-4 h-4 animate-spin" style={{ color: agent.color }}/> 
                              : isDone ? <CheckCircle2 className="w-4 h-4" style={{ color: agent.color }}/>
                              : isFailed ? <XCircle className="w-4 h-4 text-red-500"/>
                              : <agent.icon className="w-4 h-4 text-white/30" />}
                          </div>
                          <span className="text-[10px] uppercase tracking-widest font-bold opacity-0 lg:opacity-100 absolute top-14 whitespace-nowrap"
                                style={{ color: isDone || isActive ? agent.color : "rgba(255,255,255,0.3)" }}>
                            {agent.label}
                          </span>
                       </div>
                       {i < AGENTS.length - 1 && (
                         <div className="absolute top-5 left-[50%] right-[-50%] h-[2px] -z-0 transition-all duration-1000"
                              style={{ background: isDone ? `linear-gradient(90deg, ${agent.color}, ${AGENTS[i+1].color}60)` : "rgba(255,255,255,0.05)" }} />
                       )}
                    </div>
                  );
               })}
             </div>

             {/* Terminal Stream (if running) or Steps History (if done) */}
             <div className="flex-1 min-h-0 relative">
               {isRunning ? (
                  <StreamTerminal events={streamEvents} isRunning={isRunning} />
               ) : (
                  <div className="absolute inset-0 overflow-y-auto space-y-4 pr-3 scrollbar-hide">
                    <h3 className="text-xs font-bold uppercase tracking-widest text-white/40 mb-5 sticky top-0 bg-black/90 backdrop-blur py-2 z-10">
                      Execution History
                    </h3>
                    {steps.map(s => <StepCard key={s.id} step={s} />)}
                  </div>
               )}
             </div>

          </div>

          {/* Right Pane: Insights / Report / Charts */}
          <div className="flex flex-col min-h-0 bg-white/[0.02] backdrop-blur-xl rounded-2xl border border-white/[0.06] overflow-hidden shadow-xl shadow-black/20">
             
             {/* Right Pane Tabs */}
             <div className="flex border-b border-white/[0.06] bg-black/20 shrink-0">
               {[
                 { id: "report", label: "Final Report", icon: FileText, show: session.has_report || session.status === "completed" },
                 { id: "findings", label: `Findings (${session.findings_count})`, icon: BarChart3, show: session.findings_count > 0 },
                 { id: "charts", label: `Charts (${charts.length})`, icon: ImageIcon, show: charts.length > 0 },
               ].filter(t => t.show).map(t => (
                 <button
                   key={t.id}
                   onClick={() => setViewMode(t.id as any)}
                   className={`flex-1 py-4 text-sm font-bold flex items-center justify-center gap-2 border-b-2 transition-all duration-200 ${
                     viewMode === t.id 
                      ? "border-white text-white bg-white/[0.04]" 
                      : "border-transparent text-white/40 hover:bg-white/[0.04] hover:text-white"
                   }`}
                 >
                   <t.icon className="w-4 h-4" />
                   {t.label}
                 </button>
               ))}
               {!session.has_report && session.findings_count === 0 && (
                 <div className="w-full py-4 text-sm font-medium text-center text-white/30 bg-black/20">
                    Results will appear here as the pipeline progresses.
                 </div>
               )}
             </div>

             {/* Right Pane Content */}
             <div className="flex-1 overflow-y-auto p-8 bg-black/10">
               {viewMode === "report" && (
                 session.has_report && report ? (
                   <div className="space-y-6">
                     <div className="flex justify-end">
                       <button onClick={handleDownloadPdf} disabled={pdfLoading} className="bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg text-[13px] font-bold flex items-center gap-2 transition-colors">
                         {pdfLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                         Export PDF
                       </button>
                     </div>
                     <ReportViewer
                       markdown={report}
                       filename={session.dataset_filename.replace(/\.[^.]+$/, "")}
                       charts={charts}
                       onDownloadPdf={handleDownloadPdf}
                       pdfLoading={pdfLoading}
                     />
                   </div>
                 ) : (
                   <div className="h-full flex flex-col items-center justify-center text-white/20">
                      <FileText className="w-16 h-16 mb-6 opacity-50" />
                      <p className="text-sm font-medium">Report is currently being generated...</p>
                   </div>
                 )
               )}

               {viewMode === "findings" && (
                 <div className="space-y-5">
                   {findings.map(f => <FindingCard key={f.id} {...f} />)}
                 </div>
               )}

               {viewMode === "charts" && (
                 <ChartGrid
                   charts={charts.map(c => ({
                     url: c.url,
                     chartId: c.path.split("/").pop()?.replace(".png", ""),
                   }))}
                 />
               )}
             </div>
          </div>
        </div>
      ) : (
         /* ── Pending State Hero ── */
         <div className="flex-1 flex flex-col items-center justify-center text-center">
            <div className="w-28 h-28 rounded-3xl bg-white/[0.03] border border-white/[0.08] flex items-center justify-center mb-8 shadow-2xl shadow-black/50">
               <Brain className="w-14 h-14 text-white/40" />
            </div>
            <h2 className="text-3xl font-bold text-white mb-3 tracking-tight">Dataset Ready for Analysis</h2>
            <p className="text-white/50 text-sm max-w-md mx-auto mb-10 leading-relaxed font-medium">
               The pipeline is ready. Click "Start Pipeline" to unleash the 6-agent system on your dataset. You will see real-time updates as they explore, test, and visualize the data.
            </p>
         </div>
      )}
    </div>
  );
}
