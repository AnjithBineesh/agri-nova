"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { ErrorState, Notice, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      const next = params.get("next");
      router.push(next && next.startsWith("/app") ? next : "/app");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      {params.get("expired") && <Notice>Your session ended. Sign in again to continue.</Notice>}
      {error && <ErrorState message={error} />}
      <div>
        <label className="label" htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="email" required className="input" value={email}
               onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div>
        <label className="label" htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" required className="input"
               value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      <button className="btn-primary w-full py-3" disabled={busy}>
        {busy && <Spinner />} Sign in
      </button>
      <p className="text-sm text-ink-soft">
        New to Agri Nova? <Link href="/register" className="font-semibold text-forest underline-offset-2 hover:underline">Create an account</Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthShell title="Welcome back" intro="Sign in to see your farms, crop predictions and rotation plans." aside="Your farms, soil tests and rotation plans, wherever you are.">
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
