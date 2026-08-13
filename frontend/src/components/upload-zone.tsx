"use client";

import { useCallback, useState } from "react";
import { Upload, FileSpreadsheet, FileJson, File, X, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
  isUploading?: boolean;
  uploadProgress?: number;
}

const ACCEPTED = ".csv,.xlsx,.xls,.json,.parquet";

const EXT_ICONS: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  csv: { icon: FileSpreadsheet, color: "#10B981", label: "CSV" },
  xlsx: { icon: FileSpreadsheet, color: "#10B981", label: "XLSX" },
  xls: { icon: FileSpreadsheet, color: "#10B981", label: "XLS" },
  json: { icon: FileJson, color: "#3B82F6", label: "JSON" },
  parquet: { icon: File, color: "#8B5CF6", label: "PARQUET" },
};

function getExt(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export function UploadZone({ onFileSelect, isUploading, uploadProgress }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validateAndSet = useCallback(
    (file: File) => {
      setError(null);
      const ext = getExt(file.name);
      if (!Object.keys(EXT_ICONS).includes(ext)) {
        setError(`Unsupported format ".${ext}". Please use CSV, XLSX, JSON, or Parquet.`);
        return;
      }
      const maxMB = 500;
      if (file.size > maxMB * 1024 * 1024) {
        setError(`File too large (${formatBytes(file.size)}). Max: ${maxMB} MB.`);
        return;
      }
      setSelectedFile(file);
      onFileSelect(file);
    },
    [onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) validateAndSet(file);
    },
    [validateAndSet]
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSet(file);
  };

  const clearFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setSelectedFile(null);
    setError(null);
    // Reset file input value
    const fileInput = document.getElementById("file-upload-input") as HTMLInputElement;
    if (fileInput) fileInput.value = "";
  };

  const ext = selectedFile ? getExt(selectedFile.name) : null;
  const FileIcon = ext && EXT_ICONS[ext] ? EXT_ICONS[ext].icon : FileSpreadsheet;
  const iconColor = ext && EXT_ICONS[ext] ? EXT_ICONS[ext].color : "#EDEDED";
  const extLabel = ext && EXT_ICONS[ext] ? EXT_ICONS[ext].label : "";

  return (
    <div className="w-full">
      <label
        htmlFor="file-upload-input"
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`block relative overflow-hidden rounded-xl transition-all duration-300 ${!isUploading && !selectedFile ? "cursor-pointer" : "cursor-default"
          }`}
      >
        <motion.div
          animate={{
            borderColor: isDragging
              ? "rgba(255,255,255,0.3)"
              : selectedFile ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.06)",
            backgroundColor: isDragging
              ? "rgba(255,255,255,0.04)"
              : selectedFile ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.01)"
          }}
          className="border-2 border-dashed p-8 md:p-12 text-center rounded-xl flex flex-col items-center justify-center min-h-[200px]"
        >
          <AnimatePresence mode="wait">
            {isUploading ? (
              /* ── Uploading State ── */
              <motion.div
                key="uploading"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="w-full max-w-md mx-auto space-y-5"
              >
                <div className="relative w-16 h-16 mx-auto">
                  <div className="absolute inset-0 border-4 border-white/10 rounded-full"></div>
                  <div
                    className="absolute inset-0 border-4 border-white rounded-full border-t-transparent animate-spin"
                  ></div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-white/50" />
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-white">Ingesting Dataset...</p>
                  <p className="text-xs text-muted-foreground">The AI is profiling column semantics.</p>
                </div>
                <div className="w-full bg-white/10 rounded-full h-1.5 overflow-hidden">
                  <motion.div
                    className="h-full bg-white"
                    initial={{ width: 0 }}
                    animate={{ width: `${uploadProgress ?? 0}%` }}
                    transition={{ type: "spring", bounce: 0, duration: 0.5 }}
                  />
                </div>
              </motion.div>
            ) : selectedFile ? (
              /* ── File Selected State ── */
              <motion.div
                key="selected"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-6 w-full flex flex-col items-center"
              >
                <div className="flex items-center justify-center w-12 h-12 rounded-full bg-[#10B981]/10 text-[#10B981] mb-2">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div className="glass-card inline-flex items-center gap-4 px-5 py-3 rounded-xl border border-white/10 w-full max-w-sm relative group overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-r from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                  <FileIcon className="w-8 h-8 shrink-0" style={{ color: iconColor }} />
                  <div className="text-left flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{selectedFile.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {extLabel} · {formatBytes(selectedFile.size)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={clearFile}
                    className="p-1.5 rounded-md hover:bg-white/10 text-muted-foreground hover:text-white transition-colors shrink-0 z-10"
                    title="Remove file"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            ) : (
              /* ── Empty State ── */
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-5 flex flex-col items-center pointer-events-none"
              >
                <motion.div
                  animate={{ scale: isDragging ? 1.1 : 1 }}
                  className="w-16 h-16 rounded-2xl flex items-center justify-center bg-white/5 border border-white/10 shadow-inner"
                >
                  <Upload className="w-7 h-7 text-white/70" />
                </motion.div>

                <div className="space-y-1">
                  <p className="text-base font-medium text-white">
                    {isDragging ? "Drop to analyze" : "Click or drag dataset here"}
                  </p>
                  <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                    Supported formats: CSV, Excel, JSON, Parquet up to 500MB
                  </p>
                </div>

                <div className="flex items-center justify-center gap-2 pt-2">
                  {Object.entries(EXT_ICONS).map(([ext, { label, color }]) => (
                    <span
                      key={ext}
                      className="px-2 py-1 rounded-[4px] text-[10px] font-mono font-medium border border-white/5 bg-white/5"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </label>

      {/* Hidden native input */}
      <input
        id="file-upload-input"
        type="file"
        accept={ACCEPTED}
        className="sr-only"
        onChange={handleInputChange}
        disabled={isUploading || !!selectedFile}
      />

      {/* Error message */}
      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: "auto", marginTop: 12 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            className="text-sm text-destructive flex items-center gap-1.5"
          >
            <X className="w-3.5 h-3.5" />
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
