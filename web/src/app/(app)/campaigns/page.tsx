import Link from "next/link";

import { stateLabel } from "@/components/prospect-state";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";

export default async function CampaignsPage() {
  const client = await api();
  const campaigns = (await client.GET("/campaigns")).data ?? [];

  return (
    <>
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">3. Campaigns</h1>
        <p className="text-muted-foreground">
          Each campaign looks for companies in the selected segments, confirms their website and
          finds a decision maker with a verified professional address. Launch one from the{" "}
          <Link href="/segments" className="underline underline-offset-4">
            segments page
          </Link>
          .
        </p>
      </header>
      {campaigns.length === 0 ? (
        <p className="text-muted-foreground">No campaign yet.</p>
      ) : (
        <div className="grid gap-4">
          {campaigns.map((campaign) => {
            const total = Object.values(campaign.counts).reduce((sum, n) => sum + n, 0);
            return (
              <Card key={campaign.id}>
                <CardHeader>
                  <CardTitle>
                    <Link
                      href={`/campaigns/${campaign.id}`}
                      className="underline-offset-4 hover:underline"
                    >
                      {campaign.name}
                    </Link>
                  </CardTitle>
                  <CardDescription>
                    Created{" "}
                    {new Date(campaign.created_at).toLocaleString("fr-FR", {
                      timeZone: "Europe/Paris",
                      dateStyle: "short",
                      timeStyle: "short",
                    })}{" "}
                    · {campaign.segment_ids.length} segment
                    {campaign.segment_ids.length > 1 ? "s" : ""} · {total} prospect
                    {total > 1 ? "s" : ""}
                    {campaign.jobs.pending > 0 ? " · in progress…" : ""}
                  </CardDescription>
                </CardHeader>
                {total > 0 ? (
                  <CardContent className="text-muted-foreground text-sm">
                    {Object.entries(campaign.counts)
                      .map(([state, count]) => `${stateLabel(state)}: ${count}`)
                      .join(" · ")}
                  </CardContent>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
