"use client";

import { useState, useEffect } from "react";
import { Settings, User, Brain, Bell, Trash2, LogOut, ChevronRight, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const AVAILABLE_MODELS = [
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash", desc: "Fast · Recommended for most datasets" },
  { id: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite", desc: "Fastest · Best for quick analysis" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", desc: "Most capable · Best for complex analysis" },
];

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [selectedModel, setSelectedModel] = useState("gemini-2.0-flash");
  const [saved, setSaved] = useState(false);
  const [profileName, setProfileName] = useState("");

  useEffect(() => {
    if (user?.full_name) {
      setProfileName(user.full_name);
    }
  }, [user]);

  useEffect(() => {
    const stored = localStorage.getItem("preferred_model");
    if (stored) setSelectedModel(stored);
  }, []);

  const handleSave = () => {
    localStorage.setItem("preferred_model", selectedModel);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const sections = [
    {
      id: "profile",
      icon: User,
      title: "Profile",
      content: (
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-2 pl-1">
              Full Name
            </label>
            <input
              value={profileName}
              onChange={e => setProfileName(e.target.value)}
              className="w-full px-5 py-3.5 rounded-xl text-sm text-white bg-black/40 border border-white/[0.06] outline-none transition-all focus:ring-2 focus:ring-white/20 focus:border-white/20 shadow-inner"
              placeholder="Your name"
            />
          </div>
          <div>
            <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-2 pl-1">
              Email Address
            </label>
            <input
              value={user?.email ?? ""}
              disabled
              className="w-full px-5 py-3.5 rounded-xl text-sm text-white/40 bg-white/[0.03] border border-white/[0.06] cursor-not-allowed shadow-inner"
            />
          </div>
        </div>
      ),
    },
    {
      id: "model",
      icon: Brain,
      title: "AI Model",
      content: (
        <div className="space-y-4">
          <p className="text-sm text-white/60 mb-2">
            Choose which Gemini model powers your analysis agents.
          </p>
          <div className="grid grid-cols-1 gap-3">
            {AVAILABLE_MODELS.map(m => {
              const isSelected = selectedModel === m.id;
              return (
                <button
                  key={m.id}
                  id={`model-select-${m.id}`}
                  onClick={() => setSelectedModel(m.id)}
                  className={`w-full flex items-center gap-4 p-5 rounded-xl border text-left transition-all duration-200 ${
                    isSelected
                      ? "border-white/30 bg-white/[0.06]"
                      : "border-white/[0.06] bg-black/20 hover:bg-white/[0.04] hover:border-white/[0.1]"
                  }`}
                >
                  <div className="flex-1">
                    <p className={`text-sm font-bold ${isSelected ? "text-white" : "text-white/80"}`}>
                      {m.label}
                    </p>
                    <p className="text-xs mt-1 text-white/40 font-medium">{m.desc}</p>
                  </div>
                  {isSelected && (
                    <CheckCircle2 className="w-5 h-5 shrink-0 text-white" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-in fade-in duration-500 pb-16">
      <div className="flex items-center gap-4 mb-2">
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center bg-white/[0.04] shadow-inner border border-white/[0.06]">
          <Settings className="w-6 h-6 text-white/50" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Settings</h1>
          <p className="text-sm font-medium text-white/50">
            Manage your preferences and AI configuration
          </p>
        </div>
      </div>

      {/* Settings sections */}
      <div className="space-y-6">
        {sections.map(s => {
          const SIcon = s.icon;
          return (
            <div key={s.id} className="bg-white/[0.02] backdrop-blur-xl rounded-2xl overflow-hidden border border-white/[0.06] shadow-2xl shadow-black/20">
              <div className="px-8 py-5 border-b border-white/[0.06] flex items-center gap-3 bg-white/[0.02]">
                <SIcon className="w-5 h-5 text-white/50" />
                <h2 className="text-base font-bold text-white tracking-tight">{s.title}</h2>
              </div>
              <div className="p-8">{s.content}</div>
            </div>
          );
        })}
      </div>

      {/* Save button */}
      <button
        id="settings-save-btn"
        onClick={handleSave}
        className={`btn-primary w-full py-4 rounded-xl text-sm font-bold transition-all duration-300 ${
          saved 
            ? "!bg-green-500 hover:!bg-green-600 !text-white !shadow-green-500/20" 
            : ""
        }`}
      >
        {saved ? "✓ Settings Saved Successfully" : "Save Changes"}
      </button>

      {/* Danger zone */}
      <div className="bg-white/[0.02] backdrop-blur-xl rounded-2xl overflow-hidden border border-red-500/20 shadow-2xl shadow-red-900/10 mt-12">
        <div className="px-8 py-5 border-b border-red-500/10 bg-red-500/5 flex items-center gap-3">
          <h2 className="text-base font-bold text-red-400 tracking-tight">Danger Zone</h2>
        </div>
        <div className="p-8">
          <button
            id="settings-signout-btn"
            onClick={handleLogout}
            className="w-full flex items-center justify-between px-6 py-5 rounded-xl border border-red-500/20 bg-red-500/5 text-left transition-all duration-200 hover:bg-red-500/10 hover:border-red-500/30 group"
          >
            <div className="flex items-center gap-4">
              <div className="p-2.5 rounded-lg bg-red-500/20 group-hover:bg-red-500/30 transition-colors">
                <LogOut className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-base font-bold text-red-400">Sign Out</p>
                <p className="text-xs font-medium text-red-400/60 mt-0.5">
                  Securely sign out of your account on this device
                </p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-red-400/50 group-hover:text-red-400/80 transition-colors" />
          </button>
        </div>
      </div>
    </div>
  );
}
