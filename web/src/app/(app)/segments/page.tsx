import Link from "next/link";

import { api } from "@/lib/api/client";

import { SegmentCard } from "./segment-card";

export default async function SegmentsPage() {
  const client = await api();
  const { data: profile } = await client.GET("/offer-profiles/current");
  const segments = profile
    ? ((
        await client.GET("/offer-profiles/{profile_id}/segments", {
          params: { path: { profile_id: profile.id } },
        })
      ).data ?? [])
    : [];

  return (
    <>
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">2. Who needs it?</h1>
        <p className="text-muted-foreground">
          Customer segments proposed from your validated offer. Each one comes with search criteria
          from the official French company registry, a fit score and its justification. Select the
          segments to prospect.
        </p>
      </header>
      {segments.length === 0 ? (
        <p className="text-muted-foreground">
          No segments yet.{" "}
          <Link href="/onboarding" className="underline underline-offset-4">
            Validate your offer profile first
          </Link>
          , then ask for segments.
        </p>
      ) : (
        <div className="grid gap-6">
          {segments.map((segment) => (
            <SegmentCard key={segment.id} segment={segment} />
          ))}
        </div>
      )}
    </>
  );
}
