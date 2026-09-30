"use client";

import { useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { OfferProfile, OfferProfileData, SourcedClaim } from "@/lib/api/client";

import { generateSegments, saveProfile, validateProfile, type ActionState } from "../actions";

type ClaimListField =
  | "offerings"
  | "target_customers"
  | "differentiators"
  | "pricing"
  | "geography"
  | "proof_points"
  | "competitors_mentioned";

const SECTIONS: { field: ClaimListField; title: string }[] = [
  { field: "offerings", title: "What you sell" },
  { field: "target_customers", title: "Who you sell to" },
  { field: "differentiators", title: "Differentiators" },
  { field: "pricing", title: "Pricing" },
  { field: "geography", title: "Geography" },
  { field: "proof_points", title: "Proof points" },
  { field: "competitors_mentioned", title: "Competitors mentioned" },
];

function SourceLink({ url }: { url: string }) {
  if (!url.startsWith("http")) {
    return <span className="text-muted-foreground text-xs">Source: your description</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-muted-foreground text-xs break-all underline underline-offset-2"
    >
      Source: {url}
    </a>
  );
}

function ClaimEditor({
  name,
  claim,
  onChange,
  onRemove,
}: {
  name: string;
  claim: SourcedClaim;
  onChange: (text: string) => void;
  onRemove: () => void;
}) {
  return (
    <li className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex items-start gap-2">
        <Textarea
          aria-label="Claim"
          name={name}
          value={claim.claim}
          rows={2}
          onChange={(event) => onChange(event.target.value)}
        />
        <Button type="button" variant="outline" onClick={onRemove} aria-label="Remove this claim">
          Remove
        </Button>
      </div>
      <blockquote className="text-muted-foreground border-l-2 pl-3 text-sm italic">
        “{claim.excerpt}”
      </blockquote>
      <SourceLink url={claim.source_url} />
    </li>
  );
}

export function ProfileEditor({ profile }: { profile: OfferProfile }) {
  const [data, setData] = useState<OfferProfileData>(profile.data);
  const [dirty, setDirty] = useState(false);
  const [result, setResult] = useState<ActionState>({});
  const [pending, startTransition] = useTransition();
  const validated = profile.status === "validated" && !dirty;

  function update(next: OfferProfileData) {
    setData(next);
    setDirty(true);
  }

  function run(action: () => Promise<ActionState>, after?: () => void) {
    startTransition(async () => {
      const outcome = await action();
      setResult(outcome);
      if (outcome.ok && after) {
        after();
      }
    });
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center gap-3">
        <Badge variant={validated ? "secondary" : "outline"}>
          {validated ? "Validated" : dirty ? "Unsaved changes" : "Draft — please review"}
        </Badge>
        {profile.source_url ? (
          <span className="text-muted-foreground text-sm">Analysed: {profile.source_url}</span>
        ) : null}
      </div>

      {profile.warnings.length > 0 ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
          <p className="font-medium">Removed or adjusted by the evidence check:</p>
          <ul className="mt-2 list-disc pl-5">
            {profile.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="company_name">Company name</Label>
          <Input
            id="company_name"
            value={data.company_name ?? ""}
            onChange={(event) => update({ ...data, company_name: event.target.value || null })}
          />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="summary">Summary</Label>
        <Textarea
          id="summary"
          rows={3}
          value={data.summary}
          onChange={(event) => update({ ...data, summary: event.target.value })}
        />
      </div>

      {data.value_proposition ? (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium">Value proposition</h2>
          <ul>
            <ClaimEditor
              name="value_proposition"
              claim={data.value_proposition}
              onChange={(text) =>
                update({ ...data, value_proposition: { ...data.value_proposition!, claim: text } })
              }
              onRemove={() => update({ ...data, value_proposition: null })}
            />
          </ul>
        </section>
      ) : null}

      {SECTIONS.map(({ field, title }) => (
        <section key={field} className="flex flex-col gap-2">
          <h2 className="font-medium">{title}</h2>
          {data[field].length === 0 ? (
            <p className="text-muted-foreground text-sm">Nothing found in the sources.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {data[field].map((claim, index) => (
                <ClaimEditor
                  key={`${field}-${index}`}
                  name={`${field}-${index}`}
                  claim={claim}
                  onChange={(text) =>
                    update({
                      ...data,
                      [field]: data[field].map((c, i) => (i === index ? { ...c, claim: text } : c)),
                    })
                  }
                  onRemove={() =>
                    update({ ...data, [field]: data[field].filter((_c, i) => i !== index) })
                  }
                />
              ))}
            </ul>
          )}
        </section>
      ))}

      {data.missing_information.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h2 className="font-medium">Not found in the sources</h2>
          <ul className="text-muted-foreground list-disc pl-5 text-sm">
            {data.missing_information.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {result.error ? (
        <p role="alert" className="text-destructive text-sm">
          {result.error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          variant="outline"
          disabled={pending || !dirty}
          onClick={() =>
            run(
              () => saveProfile(profile.id, data),
              () => setDirty(false),
            )
          }
        >
          Save changes
        </Button>
        <Button
          type="button"
          disabled={pending || dirty || validated}
          onClick={() => run(() => validateProfile(profile.id))}
        >
          Validate this profile
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={pending || !validated}
          onClick={() => run(() => generateSegments(profile.id))}
        >
          {pending ? "Working…" : "Propose customer segments →"}
        </Button>
      </div>
    </div>
  );
}
