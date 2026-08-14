"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/auth";
import { Brain, LayoutDashboard, Settings, LogOut, PlusCircle, Menu, X } from "lucide-react";
import { ToastContainer } from "@/components/toast";
import { useToastManager, _registerToastDispatcher } from "@/hooks/use-toast";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // ── Toast ──────────────────────────────────────────────────────────────────
  const { toasts, addToast, dismissToast } = useToastManager();
  _registerToastDispatcher(addToast);

  // ── Auth guard ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!auth.isAuthenticated()) {
      router.replace("/login");
    }
  }, [router]);

  // Close mobile menu on nav
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  const user = auth.getUser();

  function handleLogout() {
    auth.clearSession();
    router.replace("/login");
  }

  const navItems = [
    { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  const NavLink = ({ item }: { item: typeof navItems[number] }) => {
    const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
    const Icon = item.icon;
    return (
      <Link
        href={item.href}
        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${active
            ? "bg-white/[0.06] text-white"
            : "text-white/45 hover:bg-white/[0.03] hover:text-white/70"
          }`}
      >
        <Icon className={`w-4 h-4 ${active ? "text-white/80" : "text-white/35"}`} />
        {item.label}
      </Link>
    );
  };

  return (
    <div className="min-h-screen w-full flex bg-black text-white overflow-hidden font-sans">

      {/* ── Sidebar (desktop) ─────────────────────────────────────────── */}
      <aside className="w-64 border-r border-white/[0.04] bg-[#080808] hidden sm:flex flex-col shrink-0">
        {/* Logo */}
        <div className="p-5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-white/[0.06] border border-white/[0.06] flex items-center justify-center shrink-0">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white tracking-tight text-[15px]">DataAnalyst AI</span>
        </div>

        {/* New Analysis CTA */}
        <div className="px-4 mb-6">
          <button
            onClick={() => router.push("/dashboard")}
            className="btn-primary w-full py-2.5 text-sm"
          >
            <PlusCircle className="w-4 h-4" />
            New Analysis
          </button>
        </div>

        {/* Nav */}
        <nav className="px-3 space-y-1">
          <p className="px-3 mb-2 text-[11px] font-semibold text-white/20 uppercase tracking-widest">Menu</p>
          {navItems.map((item) => <NavLink key={item.href} item={item} />)}
        </nav>

        {/* User footer */}
        <div className="mt-auto p-4 border-t border-white/[0.04]">
          <div className="flex items-center justify-between">
            {user && (
              <div className="flex items-center gap-2.5 overflow-hidden min-w-0">
                <div className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center text-xs font-semibold text-white/60 shrink-0 border border-white/[0.06]">
                  {(user.full_name || user.email)?.[0]?.toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white/80 truncate">{user.full_name || "User"}</p>
                  <p className="text-[11px] text-white/30 truncate">{user.email}</p>
                </div>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="p-2 rounded-lg text-white/25 hover:bg-white/[0.04] hover:text-red-400 transition-colors shrink-0"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Mobile sidebar overlay ────────────────────────────────────────── */}
      {mobileOpen && (
        <div className="sm:hidden fixed inset-0 z-50">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />

          {/* Drawer */}
          <div className="absolute left-0 top-0 bottom-0 w-64 bg-[#080808] border-r border-white/[0.06] flex flex-col animate-in">
            <div className="p-5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-white/[0.06] border border-white/[0.06] flex items-center justify-center">
                  <Brain className="w-4 h-4 text-white" />
                </div>
                <span className="font-bold text-white tracking-tight text-[15px]">DataAnalyst AI</span>
              </div>
              <button onClick={() => setMobileOpen(false)} className="p-1.5 text-white/40 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <nav className="px-3 space-y-1 mt-2">
              {navItems.map((item) => <NavLink key={item.href} item={item} />)}
            </nav>

            {user && (
              <div className="mt-auto p-4 border-t border-white/[0.04]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center text-xs font-semibold text-white/60 shrink-0">
                      {(user.full_name || user.email)?.[0]?.toUpperCase()}
                    </div>
                    <p className="text-sm text-white/60 truncate">{user.full_name || user.email}</p>
                  </div>
                  <button onClick={handleLogout} className="p-2 text-white/25 hover:text-red-400 transition-colors">
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Main Content ────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto h-screen bg-black">
        {/* Mobile header */}
        <header className="sm:hidden sticky top-0 z-40 border-b border-white/[0.04] bg-[#080808]/90 backdrop-blur-xl px-4 h-14 flex items-center justify-between">
          <button onClick={() => setMobileOpen(true)} className="p-2 text-white/50 hover:text-white transition-colors">
            <Menu className="w-5 h-5" />
          </button>
          <Link href="/dashboard" className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-white/60" />
            <span className="font-semibold text-sm text-white/80">DataAnalyst AI</span>
          </Link>
          <button onClick={handleLogout} className="p-2 text-white/40 hover:text-white transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </header>

        {/* Content */}
        <div className="flex-1 p-5 sm:p-8 lg:p-10 max-w-7xl mx-auto w-full">
          {children}
        </div>
      </main>

      {/* ── Toast ──────────────────────────────────────────────────────────── */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
