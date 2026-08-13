"use client";

import { useState } from "react";
import { ZoomIn, X, Download, BarChart3, Maximize2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ChartRendererProps {
  url: string;
  title?: string;
  description?: string;
  chartId?: string;
}

export function ChartRenderer({ url, title, description, chartId }: ChartRendererProps) {
  const [lightbox, setLightbox] = useState(false);
  const [error, setError] = useState(false);

  if (!url) return null;

  return (
    <>
      {/* Chart card */}
      <motion.div 
        layout
        className="glass-card rounded-xl overflow-hidden group transition-all duration-300 relative flex flex-col hover-glow"
      >
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/10 pointer-events-none" />

        {(title || description) && (
          <div className="px-5 pt-4 pb-3 z-10 relative bg-black/10 border-b border-white/[0.04]">
            {title && <p className="text-sm font-semibold text-white tracking-tight">{title}</p>}
            {description && (
              <p className="text-xs mt-1 text-muted-foreground leading-relaxed line-clamp-2">
                {description}
              </p>
            )}
          </div>
        )}

        <div 
          className="relative bg-[#050505] cursor-pointer p-4 flex-1 flex items-center justify-center min-h-[250px]" 
          onClick={() => !error && setLightbox(true)}
        >
          {!error ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt={title ?? "Analysis chart"}
                className="w-full object-contain transition-transform duration-500 group-hover:scale-[1.02]"
                style={{ maxHeight: "380px" }}
                onError={() => setError(true)}
              />
              {/* Hover overlay */}
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all duration-300 flex items-center justify-center backdrop-blur-[1px]">
                <div className="opacity-0 group-hover:opacity-100 transition-opacity transform translate-y-4 group-hover:translate-y-0 duration-300">
                  <div className="bg-white/10 p-3 rounded-full backdrop-blur-md border border-white/20">
                     <Maximize2 className="w-6 h-6 text-white drop-shadow-md" />
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground opacity-50">
              <BarChart3 className="w-10 h-10" />
              <p className="text-xs uppercase tracking-widest font-mono">Chart unavailable</p>
            </div>
          )}
        </div>

        {!error && (
          <div className="px-4 py-3 flex justify-between items-center z-10 relative bg-black/10 border-t border-white/[0.04]">
            <span className="text-[10px] uppercase font-mono text-muted-foreground tracking-wider">
               {chartId ? `ID: ${chartId.split("_").pop()}` : 'Interactive Plot'}
            </span>
            <a
              href={url}
              download={`${chartId ?? "chart"}.png`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-medium text-white/60 hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-md border border-white/5"
              onClick={e => e.stopPropagation()}
            >
              <Download className="w-3.5 h-3.5" />
              Save
            </a>
          </div>
        )}
      </motion.div>

      {/* Lightbox */}
      <AnimatePresence>
        {lightbox && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/95 backdrop-blur-xl flex items-center justify-center p-4 md:p-10"
            onClick={() => setLightbox(false)}
          >
            <button
              className="absolute top-6 right-6 p-2 rounded-full bg-white/10 text-white/70 hover:text-white hover:bg-white/20 transition-colors z-50 border border-white/10"
              onClick={() => setLightbox(false)}
            >
              <X className="w-5 h-5" />
            </button>
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="relative max-w-[90vw] max-h-[90vh]"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt={title ?? "Chart"}
                className="w-full h-full object-contain rounded-xl shadow-2xl border border-white/10 bg-[#050505]"
                onClick={e => e.stopPropagation()}
              />
              {title && (
                 <div className="absolute bottom-4 left-4 right-4 bg-black/70 backdrop-blur p-4 rounded-lg border border-white/10 text-center">
                    <p className="text-sm font-medium text-white">{title}</p>
                 </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/** Grid of charts */
export function ChartGrid({ charts }: { charts: Array<{ url: string; title?: string; description?: string; chartId?: string }> }) {
  if (!charts.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-white/30 border border-dashed border-white/[0.08] rounded-xl bg-white/[0.01]">
        <BarChart3 className="w-12 h-12 mb-4" />
        <p className="text-sm">No visualizations generated yet.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      {charts.map((c, i) => (
        <ChartRenderer key={c.chartId ?? i} {...c} />
      ))}
    </div>
  );
}
