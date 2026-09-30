import { connection } from "next/server";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth } from "@/lib/api";

const API_PUBLIC_URL = process.env.API_PUBLIC_URL ?? "http://localhost:8000";
const MAILPIT_UI_URL = process.env.MAILPIT_UI_URL ?? "http://localhost:8025";

function StatusRow({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-muted-foreground">{label}</span>
      <Badge variant={ok ? "secondary" : "destructive"}>{value}</Badge>
    </div>
  );
}

export default async function Home() {
  await connection();
  const health = await getHealth();

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">outreach-agents</h1>
        <p className="text-muted-foreground">
          AI agents that research B2B prospects and draft sourced, compliant emails. A human
          approves every email before it is sent.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>Phase 0 skeleton: services are wired together.</CardDescription>
        </CardHeader>
        <CardContent className="divide-y">
          <StatusRow
            label="API"
            ok={health !== null}
            value={health ? `up (v${health.version})` : "unreachable"}
          />
          <StatusRow
            label="Database"
            ok={health?.database === "ok"}
            value={health?.database ?? "unknown"}
          />
          <StatusRow label="Mode" ok={health !== null} value={health?.mode ?? "unknown"} />
        </CardContent>
      </Card>

      <nav className="flex flex-wrap gap-4 text-sm">
        <a className="underline underline-offset-4" href={`${API_PUBLIC_URL}/docs`}>
          API documentation (OpenAPI)
        </a>
        <a className="underline underline-offset-4" href={MAILPIT_UI_URL}>
          Mailpit inbox (captured emails)
        </a>
      </nav>
    </main>
  );
}
