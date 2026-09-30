import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth } from "@/lib/api/health";

import { LoginForm } from "./login-form";

export default async function LoginPage() {
  const health = await getHealth();
  const demo = health?.mode === "DEMO";

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Sign in to outreach-agents</CardTitle>
          <CardDescription>
            {demo
              ? "Demo mode: the fictional demo account is pre-filled (demo@example.com / demo-password)."
              : "Use the admin account defined in your .env file."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm demo={demo} />
        </CardContent>
      </Card>
    </main>
  );
}
