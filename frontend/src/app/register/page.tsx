"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { ErrorState, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const ROLES = [
  { value: "farmer", title: "Farmer", body: "Manage your farms and plan rotations." },
  { value: "researcher", title: "Researcher", body: "Analyse data, adjust model assumptions and export datasets." },
  { value: "organisation", title: "Organisation", body: "Monitor member farms and regional indicators." },
];

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "farmer", organisation_name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await register({ ...form, organisation_name: form.organisation_name.trim() || null });
      router.push(user.role === "farmer" ? "/app/farms/new" : user.role === "organisation" ? "/app/organisation" : "/app");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Create your free account" intro="It takes a minute. Next, you'll add your first farm." aside="Start with one farm. Agri Nova predicts the crops that suit it and plans your rotation.">
      <form onSubmit={submit} className="space-y-4">
        {error && <ErrorState message={error} />}
        <fieldset>
          <legend className="label">I am a</legend>
          <div className="grid gap-2">
            {ROLES.map((r) => (
              <label key={r.value}
                     className={`flex cursor-pointer gap-3 rounded-2xl border px-4 py-3 text-sm transition-colors ${form.role === r.value ? "border-forest bg-lime-100" : "border-line bg-white hover:border-forest/30"}`}>
                <input type="radio" name="role" value={r.value} checked={form.role === r.value}
                       onChange={() => set("role", r.value)} className="mt-1 accent-forest" />
                <span>
                  <span className="font-semibold">{r.title}</span>
                  <span className="block text-ink-soft">{r.body}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" required minLength={2} className="input" value={form.name} onChange={(e) => set("name", e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" required className="input" value={form.email} onChange={(e) => set("email", e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" required minLength={8} className="input" value={form.password}
                 onChange={(e) => set("password", e.target.value)} />
          <p className="hint">At least 8 characters.</p>
        </div>
        <div>
          <label className="label" htmlFor="org">
            Organisation {form.role === "organisation" ? "name" : "(optional)"}
          </label>
          <input id="org" className="input" required={form.role === "organisation"} value={form.organisation_name}
                 onChange={(e) => set("organisation_name", e.target.value)} />
          <p className="hint">
            {form.role === "organisation"
              ? "Creates your organisation. Members join by entering the same name when they register."
              : "Join an existing organisation, such as a cooperative or advisory programme, so its staff can view your farms."}
          </p>
        </div>
        <button className="btn-primary w-full py-3" disabled={busy}>
          {busy && <Spinner />} Create account
        </button>
        <p className="text-sm text-ink-soft">
          Already registered? <Link href="/login" className="font-semibold text-forest hover:underline">Sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
