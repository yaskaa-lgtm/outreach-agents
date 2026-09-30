"use client";

import { useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Segment } from "@/lib/api/client";

import { setSegmentSelected } from "../actions";

// INSEE headcount ranges (same codes as backend/app/reference_data/headcount_ranges.json).
const HEADCOUNT: Record<string, string> = {
  "01": "1–2",
  "02": "3–5",
  "03": "6–9",
  "11": "10–19",
  "12": "20–49",
  "21": "50–99",
  "22": "100–199",
  "31": "200–249",
  "32": "250–499",
  "41": "500–999",
  "42": "1 000–1 999",
  "51": "2 000–4 999",
  "52": "5 000–9 999",
  "53": "10 000+",
};

export function SegmentCard({ segment }: { segment: Segment }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const { criteria } = segment;

  function toggle() {
    startTransition(async () => {
      const result = await setSegmentSelected(segment.id, !segment.selected);
      setError(result.error ?? null);
    });
  }

  return (
    <Card className={segment.selected ? "ring-primary ring-2" : undefined}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <CardTitle>{segment.name}</CardTitle>
          <Badge variant={segment.fit_score >= 70 ? "default" : "outline"}>
            Fit {segment.fit_score}/100
          </Badge>
        </div>
        <CardDescription>{segment.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm">
        <p>
          <span className="font-medium">Why this score: </span>
          {segment.fit_rationale}
        </p>
        <p>
          <span className="font-medium">Main pain: </span>
          {segment.main_pain}
        </p>
        <p>
          <span className="font-medium">Email angle: </span>
          {segment.hook_angle}
        </p>
        <p>
          <span className="font-medium">Decision makers: </span>
          {segment.target_titles.join(", ")}
        </p>
        <div className="flex flex-wrap gap-2" aria-label="Search criteria">
          {criteria.naf_codes.map((code) => (
            <Badge key={code} variant="outline">
              NAF {code}
            </Badge>
          ))}
          {criteria.headcount_ranges.map((code) => (
            <Badge key={code} variant="outline">
              {HEADCOUNT[code] ?? code} employees
            </Badge>
          ))}
          {criteria.departements.length === 0 ? (
            <Badge variant="outline">All France</Badge>
          ) : (
            criteria.departements.map((code) => (
              <Badge key={code} variant="outline">
                Dept {code}
              </Badge>
            ))
          )}
        </div>
        {error ? (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        ) : null}
        <div>
          <Button
            type="button"
            variant={segment.selected ? "secondary" : "default"}
            onClick={toggle}
            disabled={pending}
            aria-pressed={segment.selected}
          >
            {segment.selected ? "Selected — click to remove" : "Select this segment"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
