"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, Variants, useScroll, useTransform } from "framer-motion";
import {
  Brain, Database, BarChart3, FileText, ChevronRight, Activity,
  UploadCloud, Zap, CheckCircle2, ArrowRight, Menu, X,
} from "lucide-react";
import Image from "next/image";

/* ═══════════════════════════════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════════════════════════════ */

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hasScrolled, setHasScrolled] = useState(false);
  const heroImageRef = useRef<HTMLDivElement>(null);

  // ── Scroll-based hero image rotation ───────────────────────────────────────
  const { scrollY } = useScroll();
  const heroRotateX = useTransform(scrollY, [0, 500], [8, 0]);
  const heroScale = useTransform(scrollY, [0, 500], [0.98, 1]);

  // Track scroll for navbar styling
  useEffect(() => {
    const onScroll = () => setHasScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Framer variants
  const containerV: Variants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
  };
  const itemV: Variants = {
    hidden: { opacity: 0, y: 24 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 200, damping: 22 } },
  };
  const fadeUpV: Variants = {
    hidden: { opacity: 0, y: 30 },
    show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
  };

  const features = [
    { icon: Brain, title: "Orchestrator", desc: "Autonomously plans the analytical strategy tailored to your dataset." },
    { icon: Database, title: "Profiler", desc: "Detects semantics, PII, quality issues, and structural nuances." },
    { icon: Activity, title: "EDA Specialist", desc: "Uncovers correlations, distributions, and forms testable hypotheses." },
    { icon: FileText, title: "Reporter", desc: "Synthesizes raw findings into an executive-level analytical briefing." },
  ];

  const stats = [
    { value: "50+", label: "Data Formats" },
    { value: "1000+", label: "Analyses Run" },
    { value: "95%", label: "Accuracy Rate" },
    { value: "24/7", label: "Availability" },
  ];

  const steps = [
    { num: "01", icon: UploadCloud, title: "Upload Dataset", desc: "Share your CSV, JSON, or Parquet file for analysis." },
    { num: "02", icon: Brain, title: "AI Orchestration", desc: "Agents autonomously plan and execute the strategy." },
    { num: "03", icon: Zap, title: "Execute & Validate", desc: "Rigorous statistical validation and automated EDA." },
    { num: "04", icon: CheckCircle2, title: "Receive Insights", desc: "Get a comprehensive, interactive executive report." },
  ];

  return (
    <div className="min-h-screen w-screen bg-black text-white selection:bg-[#8B5CF6]/30 font-sans overflow-x-hidden">

      {/* ══════════════════════════════════════════════════════════════════════
          NAVBAR
          ══════════════════════════════════════════════════════════════════════ */}
      <nav
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${hasScrolled
            ? "bg-black/80 backdrop-blur-xl border-b border-white/[0.06]"
            : "bg-transparent"
          }`}
      >
        <div className="max-w-6xl mx-auto px-5 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-white/[0.08] border border-white/[0.08] flex items-center justify-center group-hover:bg-white/[0.12] transition-colors">
              <Brain className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-white tracking-tight">Analyst AI</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden sm:flex items-center gap-2">
            <Link href="/login" className="btn-ghost text-sm text-white/60 hover:text-white px-4 py-2">
              Log in
            </Link>
            <Link href="/register" className="btn-primary text-sm px-5 py-2.5">
              Get Started
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            className="sm:hidden p-2 text-white/60 hover:text-white transition-colors"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="sm:hidden bg-black/95 backdrop-blur-xl border-t border-white/[0.06] px-5 py-4 space-y-3 animate-in">
            <Link href="/login" onClick={() => setMobileMenuOpen(false)} className="block text-sm text-white/70 py-2 hover:text-white transition-colors">
              Log in
            </Link>
            <Link href="/register" onClick={() => setMobileMenuOpen(false)} className="btn-primary w-full text-sm py-2.5 text-center">
              Get Started
            </Link>
          </div>
        )}
      </nav>

      {/* Navbar spacer */}
      <div className="h-16" />

      {/* ══════════════════════════════════════════════════════════════════════
          HERO
          ══════════════════════════════════════════════════════════════════════ */}
      <section className="relative pt-20 sm:pt-28 pb-8 px-5 sm:px-6 overflow-hidden">
        {/* Ambient glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[600px] bg-[#8B5CF6]/[0.04] rounded-full blur-[140px] pointer-events-none" />

        <motion.div
          initial="hidden"
          animate="show"
          variants={containerV}
          className="relative max-w-4xl mx-auto flex flex-col items-center text-center z-10"
        >
          {/* Badge */}
          <motion.div variants={itemV} className="mb-6">
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-white/50 bg-white/[0.04] border border-white/[0.06] rounded-full px-3.5 py-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              AI-Powered Analytics Platform
            </span>
          </motion.div>

          {/* Heading */}
          <motion.h1
            variants={itemV}
            className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-[-0.04em] leading-[1.05] mb-6"
          >
            <span className="text-white block">The Autonomous</span>
            <span className="text-gradient block">Data Science Team</span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            variants={itemV}
            className="text-base sm:text-lg text-white/50 max-w-xl mb-10 leading-relaxed font-normal"
          >
            Upload your dataset and let AI agents autonomously explore, validate, visualize, and deliver a complete analytical report.
          </motion.p>

          {/* CTAs */}
          <motion.div variants={itemV} className="flex flex-col sm:flex-row items-center gap-3 mb-20 sm:mb-28">
            <Link href="/register" className="btn-primary px-7 py-3 text-sm">
              Start Analyzing
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="#features" className="btn-secondary px-7 py-3 text-sm">
              Learn More
            </Link>
          </motion.div>

          {/* Hero Image — scroll-based rotation */}
          <motion.div
            variants={itemV}
            ref={heroImageRef}
            className="w-full max-w-5xl mx-auto"
            style={{ perspective: 1200 }}
          >
            <motion.div
              className="relative w-full aspect-[16/9] rounded-xl overflow-hidden border border-white/[0.08]"
              style={{
                rotateX: heroRotateX,
                scale: heroScale,
                transformOrigin: "center bottom",
                boxShadow: "0 20px 80px -20px rgba(0,0,0,0.8), 0 0 60px rgba(139,92,246,0.06)",
              }}
            >
              <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent z-10" />
              <Image src="/hero_image.png" alt="AI Data Analyst Dashboard" fill className="object-cover" priority />
            </motion.div>
          </motion.div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          FEATURES
          ══════════════════════════════════════════════════════════════════════ */}
      <div className="section-divider max-w-6xl mx-auto" />

      <section id="features" className="py-24 sm:py-32 px-5 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUpV}
            className="text-center mb-14"
          >
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight mb-3">
              Powerful Features for Your Data
            </h2>
            <p className="text-sm sm:text-base text-white/40 max-w-md mx-auto">
              Four specialized AI agents working together to deliver comprehensive analysis.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {features.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={i}
                  initial="hidden"
                  whileInView="show"
                  viewport={{ once: true, margin: "-40px" }}
                  variants={fadeUpV}
                  transition={{ delay: i * 0.08 }}
                  className="group p-6 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/[0.1] transition-all duration-300 hover-lift"
                >
                  <div className="w-10 h-10 rounded-lg bg-white/[0.06] flex items-center justify-center mb-4 group-hover:bg-white/[0.1] transition-colors">
                    <Icon className="w-5 h-5 text-white/70" />
                  </div>
                  <h3 className="text-[15px] font-semibold text-white mb-2">{feature.title}</h3>
                  <p className="text-sm text-white/40 leading-relaxed">{feature.desc}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          STATS
          ══════════════════════════════════════════════════════════════════════ */}
      <section className="py-16 sm:py-20 px-5 sm:px-6 lg:px-8 bg-white/[0.015] border-y border-white/[0.04]">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8">
            {stats.map((stat, i) => (
              <motion.div
                key={i}
                initial="hidden"
                whileInView="show"
                viewport={{ once: true }}
                variants={fadeUpV}
                transition={{ delay: i * 0.06 }}
                className="flex flex-col items-center text-center"
              >
                <span className="text-3xl sm:text-4xl font-bold text-white tracking-tight mb-1.5">{stat.value}</span>
                <span className="text-xs sm:text-sm text-white/40 font-medium">{stat.label}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          HOW IT WORKS
          ══════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 sm:py-32 px-5 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUpV}
            className="text-center mb-16"
          >
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight mb-3">How It Works</h2>
            <p className="text-sm sm:text-base text-white/40 max-w-md mx-auto">
              Four simple steps to comprehensive data analysis.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <motion.div
                  key={i}
                  initial="hidden"
                  whileInView="show"
                  viewport={{ once: true, margin: "-40px" }}
                  variants={fadeUpV}
                  transition={{ delay: i * 0.1 }}
                  className="relative flex flex-col items-center text-center group"
                >
                  {/* Step number */}
                  <span className="text-xs font-mono font-bold text-white/20 mb-3 tracking-widest">{step.num}</span>

                  {/* Icon circle */}
                  <div className="w-14 h-14 rounded-full border border-white/[0.08] bg-white/[0.03] flex items-center justify-center mb-5 group-hover:border-white/[0.15] group-hover:bg-white/[0.06] transition-all duration-300">
                    <Icon className="w-6 h-6 text-white/60" />
                  </div>

                  <h3 className="text-sm font-semibold text-white mb-2">{step.title}</h3>
                  <p className="text-sm text-white/40 leading-relaxed max-w-[220px]">{step.desc}</p>

                  {/* Connector line on desktop */}
                  {i < steps.length - 1 && (
                    <div className="hidden lg:block absolute top-[4.5rem] left-[calc(50%+2.5rem)] w-[calc(100%-3rem)] h-px bg-gradient-to-r from-white/[0.06] to-transparent" />
                  )}
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          CTA SECTION
          ══════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 sm:py-28 px-5 sm:px-6 lg:px-8">
        <div className="max-w-2xl mx-auto text-center">
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUpV}
          >
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight mb-4">
              Ready to Transform Your Data?
            </h2>
            <p className="text-base text-white/40 mb-8 max-w-lg mx-auto leading-relaxed">
              Join thousands of analysts using autonomous AI to uncover insights faster.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/register" className="btn-primary px-8 py-3 text-sm">
                Start Free
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="#features" className="btn-secondary px-8 py-3 text-sm">
                View Features
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          FOOTER
          ══════════════════════════════════════════════════════════════════════ */}
      <div className="section-divider" />

      <footer className="py-10 sm:py-12 px-5 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          {/* Left: branding */}
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-white/30" />
            <span className="text-sm text-white/30 font-medium">
              © {new Date().getFullYear()} Analyst AI
            </span>
          </div>

          {/* Right: links */}
          <div className="flex items-center gap-6 text-sm">
            {["Documentation", "API", "GitHub", "Privacy", "Terms"].map((label) => (
              <Link key={label} href="#" className="text-white/30 hover:text-white/60 transition-colors">
                {label}
              </Link>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
