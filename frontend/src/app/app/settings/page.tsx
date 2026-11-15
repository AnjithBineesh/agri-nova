"use client";

import { useState } from "react";
import { ErrorState, Notice, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [units, setUnits] = useState<string>(user?.preferences?.nutrient_unit ?? "kg/ha");
  const [pw, setPw] = useState({ current: "", next: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async (body: Record<string, unknown>, done: string) => {
    setBusy(true); setErr(null); setMsg(null);
    try { await api.put("/api/auth/me", body); await refresh(); setMsg(done); setPw({ current: "", next: "" }); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Profile and settings" />
      {msg && <Notice>{msg}</Notice>}
      {err && <ErrorState message={err} />}
      <section className="panel panel-pad space-y-4">
        <h2 className="section-title">Profile</h2>
        <div>
          <label className="label" htmlFor="n">Name</label>
          <input id="n" className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <div><span className="text-ink-soft">Email</span><div>{user?.email}</div></div>
          <div><span className="text-ink-soft">Role</span><div className="capitalize">{user?.role}{user?.organisation_name ? `, ${user.organisation_name}` : ""}</div></div>
        </div>
        <div>
          <label className="label" htmlFor="u">Preferred nutrient unit for new soil entries</label>
          <select id="u" className="input max-w-xs" value={units} onChange={(e) => setUnits(e.target.value)}>
            <option value="kg/ha">kg/ha</option><option value="mg/kg">mg/kg</option><option value="ppm">ppm</option>
          </select>
        </div>
        <button className="btn-primary" disabled={busy} onClick={() => save({ name, preferences: { nutrient_unit: units } }, "Profile saved.")}>{busy && <Spinner />} Save profile</button>
      </section>
      <section className="panel panel-pad space-y-4">
        <h2 className="section-title">Change password</h2>
        <div>
          <label className="label" htmlFor="cp">Current password</label>
          <input id="cp" type="password" className="input" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} autoComplete="current-password" />
        </div>
        <div>
          <label className="label" htmlFor="np">New password</label>
          <input id="np" type="password" minLength={8} className="input" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} autoComplete="new-password" />
        </div>
        <button className="btn-secondary" disabled={busy || pw.next.length < 8 || !pw.current}
                onClick={() => save({ current_password: pw.current, new_password: pw.next }, "Password changed.")}>Change password</button>
      </section>
      <section className="panel panel-pad text-sm text-ink-soft">
        <h2 className="section-title text-ink">Privacy</h2>
        <p className="mt-1">Your farm data is visible only to you and, if you joined one, to staff of your organisation. Researchers see anonymised aggregates only. Location is never requested from your device unless you select “Use my location”.</p>
      </section>
    </div>
  );
}
