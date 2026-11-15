"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3, BrainCircuit, Building2, CloudSun, ChevronDown, FileText, FlaskConical, Layers, LayoutDashboard, LogOut, Map, Menu, Microscope,
  Plus, Repeat, Settings, Sprout, X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { FarmProvider, useFarm } from "@/lib/farm";
import { Logo } from "./Logo";
import { Loading } from "./ui";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ className?: string }> };

const GROUPS: { title: string; items: NavItem[] }[] = [
  { title: "Overview", items: [{ href: "/app", label: "Dashboard", icon: LayoutDashboard }] },
  {
    title: "Your farm", items: [
      { href: "/app/farms", label: "Farms", icon: Map },
      { href: "/app/earth", label: "Field conditions", icon: CloudSun },
      { href: "/app/soil", label: "Soil analysis", icon: Layers },
    ],
  },
  {
    title: "Plan", items: [
      { href: "/app/predict", label: "Crop prediction", icon: BrainCircuit },
      { href: "/app/crops", label: "Crop library", icon: Sprout },
      { href: "/app/suitability", label: "Crop suitability", icon: BarChart3 },
      { href: "/app/planner", label: "Rotation planner", icon: Repeat },
      { href: "/app/simulator", label: "Five-year simulator", icon: FlaskConical },
    ],
  },
  { title: "Share", items: [{ href: "/app/reports", label: "Reports", icon: FileText }] },
];

function FarmPicker() {
  const { farms, farm, selectFarm } = useFarm();
  if (!farms.length) {
    return <Link href="/app/farms/new" className="btn-lime py-2"><Plus className="h-4 w-4" /> Add farm</Link>;
  }
  return (
    <label className="relative flex items-center gap-2 rounded-full border border-line bg-white py-1 pl-4 pr-2 text-sm shadow-soft">
      <span className="hidden text-ink-faint sm:inline">Farm</span>
      <select className="appearance-none bg-transparent py-1 pr-6 font-semibold text-ink focus:outline-none" value={farm?.id ?? ""}
              onChange={(e) => selectFarm(Number(e.target.value))} aria-label="Selected farm">
        {farms.map((f) => (
          <option key={f.id} value={f.id}>{f.farm_name}{f.can_edit ? "" : ` (${f.owner_name})`}</option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 h-4 w-4 text-ink-faint" />
    </label>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const { user, logout } = useAuth();
  const router = useRouter();
  const extra: NavItem[] = [
    ...(user && ["researcher", "admin"].includes(user.role) ? [{ href: "/app/research", label: "Researcher portal", icon: Microscope }] : []),
    ...(user && ["organisation", "admin"].includes(user.role) ? [{ href: "/app/organisation", label: "Organisation portal", icon: Building2 }] : []),
    { href: "/app/settings", label: "Profile & settings", icon: Settings },
  ];
  const item = (n: NavItem) => {
    const active = n.href === "/app" ? path === "/app" : path.startsWith(n.href);
    return (
      <li key={n.href}>
        <Link href={n.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-full px-3.5 py-2 text-sm transition-colors ${active ? "bg-lime font-bold text-forest" : "text-white/75 hover:bg-white/10 hover:text-white"}`}>
          <n.icon className="h-4 w-4" /> {n.label}
        </Link>
      </li>
    );
  };
  return (
    <div className="flex h-full flex-col rounded-[24px] bg-forest px-3 py-5">
      <div className="px-3 pb-6"><Logo light href="/app" /></div>
      <nav aria-label="Application" className="flex-1 space-y-5 overflow-y-auto">
        {GROUPS.map((g) => (
          <div key={g.title}>
            <p className="px-3.5 pb-1.5 text-xs font-semibold text-white/40">{g.title}</p>
            <ul className="space-y-0.5">{g.items.map(item)}</ul>
          </div>
        ))}
        <div>
          <p className="px-3.5 pb-1.5 text-xs font-semibold text-white/40">Account</p>
          <ul className="space-y-0.5">{extra.map(item)}</ul>
        </div>
      </nav>
      <div className="mt-4 rounded-2xl bg-white/5 px-3.5 py-3 text-sm text-white/70">
        <div className="truncate font-semibold text-white">{user?.name}</div>
        <div className="capitalize">{user?.role}{user?.organisation_name ? `, ${user.organisation_name}` : ""}</div>
        <button onClick={async () => { await logout(); router.push("/"); }}
                className="mt-2 inline-flex items-center gap-2 text-white/70 hover:text-white">
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [loading, user, router, path]);

  if (loading || !user) return <div className="p-10"><Loading label="Checking your session" /></div>;

  return (
    <FarmProvider>
      <div className="min-h-screen lg:grid lg:grid-cols-[264px_1fr]">
        <div className="hidden lg:block">
          <aside className="sticky top-0 h-screen p-3 pr-0"><Sidebar /></aside>
        </div>
        {open && (
          <div className="fixed inset-0 z-[1000] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
            <div className="absolute inset-y-0 left-0 w-72 p-2">
              <Sidebar onNavigate={() => setOpen(false)} />
              <button className="absolute right-5 top-7 text-white" onClick={() => setOpen(false)} aria-label="Close navigation">
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
        )}
        <div className="min-w-0">
          <header className="sticky top-0 z-[500] flex items-center justify-between gap-3 bg-paper/90 px-4 py-3 backdrop-blur sm:px-8">
            <button className="btn-secondary px-3 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
              <Menu className="h-5 w-5" />
            </button>
            <div className="ml-auto"><FarmPicker /></div>
          </header>
          <main className="mx-auto max-w-6xl px-4 pb-16 pt-4 sm:px-8">{children}</main>
        </div>
      </div>
    </FarmProvider>
  );
}
