import Link from "next/link";
import { notFound } from "next/navigation";

import { AutoRefresh } from "@/components/auto-refresh";
import { STATE_LABELS, StateBadge, stateLabel } from "@/components/prospect-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";

import { ImportForm } from "./import-form";

const DOMAIN_LABELS: Record<string, string> = {
  confirmed: "confirmed by SIREN",
  unconfirmed: "SIREN not found on the site",
  not_found: "site could not be read",
  unknown: "not checked yet",
};

const SELECT_CLASS =
  "border-input bg-background h-8 rounded-lg border px-2 text-sm focus-visible:ring-3 focus-visible:ring-ring/50 outline-none";

function single(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value || undefined;
}

export default async function CampaignPage(props: PageProps<"/campaigns/[id]">) {
  const { id } = await props.params;
  const searchParams = await props.searchParams;
  const state = single(searchParams.state);
  const segmentId = single(searchParams.segment);

  const client = await api();
  const { data: campaign } = await client.GET("/campaigns/{campaign_id}", {
    params: { path: { campaign_id: id } },
  });
  if (!campaign) {
    notFound();
  }
  const [{ data: prospects }, { data: profile }] = await Promise.all([
    client.GET("/campaigns/{campaign_id}/prospects", {
      params: { path: { campaign_id: id }, query: { state, segment_id: segmentId } },
    }),
    client.GET("/offer-profiles/current"),
  ]);
  const segments = profile
    ? ((
        await client.GET("/offer-profiles/{profile_id}/segments", {
          params: { path: { profile_id: profile.id } },
        })
      ).data ?? [])
    : [];
  const segmentNames = new Map(segments.map((segment) => [segment.id, segment.name]));
  const rows = prospects ?? [];
  const total = Object.values(campaign.counts).reduce((sum, n) => sum + n, 0);
  const running = campaign.jobs.pending > 0;

  return (
    <>
      <AutoRefresh active={running} />
      <header className="flex flex-col gap-2">
        <Link href="/campaigns" className="text-muted-foreground text-sm hover:underline">
          ← All campaigns
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">{campaign.name}</h1>
        <p className="text-muted-foreground" aria-live="polite">
          {running
            ? `Searching… ${campaign.jobs.pending} task${campaign.jobs.pending > 1 ? "s" : ""} left. This page refreshes by itself.`
            : `${total} prospect${total > 1 ? "s" : ""}, up to ${campaign.companies_per_segment} companies per segment.`}
          {campaign.jobs.failed > 0
            ? ` ${campaign.jobs.failed} task${campaign.jobs.failed > 1 ? "s" : ""} failed after several attempts.`
            : ""}
        </p>
      </header>

      <section aria-label="Prospects by state" className="flex flex-wrap gap-2">
        {Object.entries(campaign.counts).map(([key, count]) => (
          <Link key={key} href={`/campaigns/${id}?state=${key}`}>
            <Badge variant={key === state ? "default" : "outline"}>
              {stateLabel(key)}: {count}
            </Badge>
          </Link>
        ))}
      </section>

      <form className="flex flex-wrap items-end gap-3" aria-label="Filter prospects">
        <label className="flex flex-col gap-1 text-sm">
          State
          <select name="state" defaultValue={state ?? ""} className={SELECT_CLASS}>
            <option value="">All</option>
            {Object.entries(STATE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Segment
          <select name="segment" defaultValue={segmentId ?? ""} className={SELECT_CLASS}>
            <option value="">All</option>
            {campaign.segment_ids.map((segment) => (
              <option key={segment} value={segment}>
                {segmentNames.get(segment) ?? "Segment"}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" variant="outline">
          Filter
        </Button>
      </form>

      {rows.length === 0 ? (
        <p className="text-muted-foreground">
          {running ? "Companies will appear here in a moment." : "No prospect matches."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  Company
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Website
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Decision maker
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  State
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t align-top">
                  <td className="px-3 py-2">
                    <Link
                      href={`/prospects/${row.id}`}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {row.company.name}
                    </Link>
                    <div className="text-muted-foreground">
                      {[row.company.city, row.company.naf_code && `NAF ${row.company.naf_code}`]
                        .filter(Boolean)
                        .join(" · ")}
                      {row.company.is_sole_trader ? " · sole trader" : ""}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div>{row.company.website_domain ?? "—"}</div>
                    <div className="text-muted-foreground">
                      {row.company.website_domain
                        ? (DOMAIN_LABELS[row.company.domain_status] ?? row.company.domain_status)
                        : "no website found"}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {row.contact ? (
                      <>
                        <div>
                          {[row.contact.first_name, row.contact.last_name]
                            .filter(Boolean)
                            .join(" ") || "Generic address"}
                          {row.contact.title ? ` — ${row.contact.title}` : ""}
                        </div>
                        <div className="text-muted-foreground">
                          {row.contact.email ?? "no address"}
                          {row.contact.is_generic ? " · generic" : ""}
                        </div>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <StateBadge state={row.state} />
                    {row.state_reason ? (
                      <div className="text-muted-foreground mt-1 max-w-56">{row.state_reason}</div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ImportForm campaignId={id} />
    </>
  );
}
