import Link from "next/link";
import { notFound } from "next/navigation";

import { StateBadge, safeHref, stateLabel } from "@/components/prospect-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";

const VERIFICATION_LABELS: Record<string, string> = {
  unverified: "not verified",
  valid: "valid (sendable)",
  accept_all: "accept-all server (not sendable)",
  unknown: "unknown (not sendable)",
  invalid: "invalid",
  webmail: "personal webmail (excluded: B2B only)",
  disposable: "disposable (excluded)",
};

function formatDate(value: string): string {
  return new Date(value).toLocaleString("fr-FR", {
    timeZone: "Europe/Paris",
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export default async function ProspectPage(props: PageProps<"/prospects/[id]">) {
  const { id } = await props.params;
  const client = await api();
  const { data: prospect } = await client.GET("/prospects/{prospect_id}", {
    params: { path: { prospect_id: id } },
  });
  if (!prospect) {
    notFound();
  }
  const { company, contact } = prospect;
  const evidence = safeHref(company.domain_evidence_url);

  return (
    <>
      <header className="flex flex-col gap-2">
        <Link
          href={`/campaigns/${prospect.campaign_id}`}
          className="text-muted-foreground text-sm hover:underline"
        >
          ← Back to the campaign
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{company.name}</h1>
          <StateBadge state={prospect.state} />
        </div>
        {prospect.state_reason ? (
          <p className="text-muted-foreground">{prospect.state_reason}</p>
        ) : null}
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Company</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col gap-2 text-sm">
            <Field label="SIREN">{company.siren ?? "—"}</Field>
            <Field label="Activity (NAF)">{company.naf_code ?? "—"}</Field>
            <Field label="Location">
              {[company.city, company.departement && `dept ${company.departement}`]
                .filter(Boolean)
                .join(", ") || "—"}
            </Field>
            <Field label="Sole trader">{company.is_sole_trader ? "yes" : "no"}</Field>
            <Field label="Source">{company.source_provider}</Field>
            <Field label="Website">
              {company.website_domain ?? "—"}{" "}
              <span className="text-muted-foreground">({company.domain_status})</span>
            </Field>
            <Field label="Proof">
              {evidence ? (
                <a
                  href={evidence}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-4"
                >
                  SIREN found on {evidence}
                </a>
              ) : (
                "No page of the website shows this company's SIREN."
              )}
            </Field>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Decision maker</CardTitle>
        </CardHeader>
        <CardContent>
          {contact ? (
            <dl className="flex flex-col gap-2 text-sm">
              <Field label="Name">
                {[contact.first_name, contact.last_name].filter(Boolean).join(" ") || "—"}
              </Field>
              <Field label="Title">{contact.title ?? "—"}</Field>
              <Field label="Email">
                {contact.email ?? "—"}
                {contact.is_generic ? (
                  <span className="text-muted-foreground"> (generic address)</span>
                ) : null}
              </Field>
              <Field label="Verification">
                {VERIFICATION_LABELS[contact.verification_status] ?? contact.verification_status}
              </Field>
              <Field label="Source">{contact.source_provider}</Field>
            </dl>
          ) : (
            <p className="text-muted-foreground text-sm">No decision maker found.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="flex flex-col gap-3 text-sm">
            {prospect.transitions.map((transition) => (
              <li key={`${transition.created_at}-${transition.to_state}`}>
                <span className="font-medium">{stateLabel(transition.to_state)}</span>
                <span className="text-muted-foreground">
                  {" "}
                  · {formatDate(transition.created_at)} · {transition.actor}
                </span>
                {transition.reason ? (
                  <div className="text-muted-foreground">{transition.reason}</div>
                ) : null}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </>
  );
}
