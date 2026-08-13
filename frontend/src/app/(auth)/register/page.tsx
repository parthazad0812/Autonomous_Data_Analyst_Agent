"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { Brain, Mail, Lock, User, Eye, EyeOff, ArrowRight, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setIsLoading(true);
    try {
      await register(email, password, fullName || undefined);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(
        axiosErr.response?.data?.detail || "Registration failed. Please try again."
      );
    } finally {
      setIsLoading(false);
    }
  }

  // Password strength
  const getStrength = () => {
    let score = 0;
    if (password.length > 0) score += 20;
    if (password.length >= 8) score += 20;
    if (/[A-Z]/.test(password)) score += 20;
    if (/[0-9]/.test(password)) score += 20;
    if (/[^A-Za-z0-9]/.test(password)) score += 20;
    return score;
  };

  const strength = getStrength();
  const strengthColor =
    strength >= 80 ? "bg-emerald-400" :
    strength >= 60 ? "bg-yellow-400" :
    strength >= 40 ? "bg-orange-400" :
    strength > 0   ? "bg-red-400" :
                     "bg-white/[0.06]";
  const strengthLabel =
    strength >= 80 ? "Strong" :
    strength >= 60 ? "Good" :
    strength >= 40 ? "Fair" :
    strength > 0   ? "Weak" : "";

  return (
    <div className="min-h-screen w-full flex items-center justify-center px-4 py-8 bg-black font-sans">

      <div className="w-full max-w-[960px] flex flex-col md:flex-row bg-black border border-white/[0.06] rounded-xl overflow-hidden min-h-[580px]">

        {/* ── Left Pane (Marketing) ── */}
        <div className="hidden md:flex flex-col flex-1 bg-[#060606] p-10 lg:p-12 border-r border-white/[0.04] relative overflow-hidden">
          {/* Background glow */}
          <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-[#8B5CF6]/[0.04] rounded-full blur-[100px] pointer-events-none" />

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 mb-auto relative z-10">
            <div className="w-9 h-9 rounded-lg bg-white/[0.06] border border-white/[0.06] flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold text-white tracking-tight">Analyst AI</span>
          </Link>

          {/* Marketing copy */}
          <div className="relative z-10 mt-12 mb-8">
            <h2 className="text-3xl lg:text-4xl font-bold text-white tracking-tight leading-tight mb-4">
              Turn raw data into actionable insights in seconds.
            </h2>
            <p className="text-white/35 leading-relaxed text-sm max-w-sm">
              Upload datasets, run AI-powered statistical analysis, and receive comprehensive reports — all automatically.
            </p>
          </div>

          {/* Decorative image area */}
          <div className="relative z-10 rounded-lg border border-white/[0.06] overflow-hidden mt-auto">
            <div
              className="aspect-[4/3] bg-cover bg-center opacity-30"
              style={{ backgroundImage: "url('https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=2070&auto=format&fit=crop')" }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#060606] via-transparent to-transparent" />
          </div>
        </div>

        {/* ── Right Pane (Form) ── */}
        <div className="flex-1 p-8 sm:p-10 lg:p-12 flex flex-col justify-center bg-[#0A0A0A]">

          {/* Mobile logo */}
          <Link href="/" className="flex md:hidden items-center gap-2.5 mb-8">
            <div className="w-8 h-8 rounded-lg bg-white/[0.06] border border-white/[0.06] flex items-center justify-center">
              <Brain className="w-4 h-4 text-white" />
            </div>
            <span className="text-base font-bold text-white tracking-tight">Analyst AI</span>
          </Link>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <div className="mb-8">
              <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">Create your account</h1>
              <p className="text-sm text-white/40">Start analyzing data with AI today</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5 max-w-md">

              {/* Full Name */}
              <div>
                <label htmlFor="full-name" className="input-label">
                  Full Name <span className="text-white/20 font-normal">(optional)</span>
                </label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-[15px] h-[15px] text-white/25 pointer-events-none" />
                  <input
                    id="full-name"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="John Doe"
                    autoComplete="name"
                    className="input-field input-with-icon"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label htmlFor="email" className="input-label">Email</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-[15px] h-[15px] text-white/25 pointer-events-none" />
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    autoComplete="email"
                    className="input-field input-with-icon"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label htmlFor="password" className="input-label">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-[15px] h-[15px] text-white/25 pointer-events-none" />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    autoComplete="new-password"
                    className="input-field input-with-icon input-with-right-icon"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-white/25 hover:text-white/50 transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {/* Strength indicator */}
                <div className="mt-2.5 space-y-1.5">
                  <div className="h-1 w-full bg-white/[0.04] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${strengthColor}`}
                      style={{ width: `${Math.max(strength > 0 ? 10 : 0, strength)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-white/30">Min. 8 characters</p>
                    {strengthLabel && (
                      <p className={`text-xs font-medium ${strength >= 80 ? 'text-emerald-400/70' : strength >= 60 ? 'text-yellow-400/70' : 'text-white/30'}`}>
                        {strengthLabel}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="rounded-lg px-4 py-3 text-sm text-red-400 bg-red-500/[0.08] border border-red-500/[0.12]">
                  {error}
                </div>
              )}

              {/* Submit — Full width */}
              <button
                id="register-submit"
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-3 mt-2"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    Create account
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            {/* Bottom link */}
            <div className="mt-8 pt-6 border-t border-white/[0.04]">
              <p className="text-sm text-white/35">
                Already have an account?{" "}
                <Link href="/login" className="font-medium text-white/70 hover:text-white transition-colors">
                  Sign in
                </Link>
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
