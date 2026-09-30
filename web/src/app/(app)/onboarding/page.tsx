import { api } from "@/lib/api/client";
import { getHealth } from "@/lib/api/health";

import { AnalyzeForm } from "./analyze-form";
import { ProfileEditor } from "./profile-editor";

// Mirror of app.demo.site.DEMO_WEBSITE_URL (the fictional demo company).
const DEMO_WEBSITE_URL = "https://nimbus-ledger.example.com/";

export default async function OnboardingPage() {
  const client = await api();
  const [{ data: profile }, health] = await Promise.all([
    client.GET("/offer-profiles/current"),
    getHealth(),
  ]);
  const demoUrl = health?.mode === "DEMO" ? DEMO_WEBSITE_URL : null;

  return (
    <>
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">1. What do you sell?</h1>
        <p className="text-muted-foreground">
          An agent reads your website and lists what you sell, to whom and why — each claim with the
          exact sentence and page it comes from. Review it, correct it, then validate.
        </p>
      </header>
      {profile ? (
        <>
          <ProfileEditor key={profile.updated_at} profile={profile} />
          <details className="text-sm">
            <summary className="text-muted-foreground cursor-pointer">Analyse again</summary>
            <div className="mt-4">
              <AnalyzeForm demoUrl={demoUrl} />
            </div>
          </details>
        </>
      ) : (
        <AnalyzeForm demoUrl={demoUrl} />
      )}
    </>
  );
}
