"use client";

import { useActionState } from "react";

import { SubmitButton } from "@/components/submit-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { analyzeOffer, type ActionState } from "../actions";

export function AnalyzeForm({ demoUrl }: { demoUrl: string | null }) {
  const [state, formAction] = useActionState<ActionState, FormData>(analyzeOffer, {});

  return (
    <form action={formAction} className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <Label htmlFor="website_url">Your website</Label>
        <Input
          id="website_url"
          name="website_url"
          type="url"
          placeholder="https://www.your-company.fr/"
          defaultValue={demoUrl ?? undefined}
        />
        {demoUrl ? (
          <p className="text-muted-foreground text-sm">
            Demo mode: the fictional website {demoUrl} is always analysed.
          </p>
        ) : (
          <p className="text-muted-foreground text-sm">
            The agent reads a few pages of this site only (robots.txt respected).
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="description">Or describe your offer (optional)</Label>
        <Textarea
          id="description"
          name="description"
          rows={5}
          maxLength={5000}
          placeholder="What you sell, to whom, at what price, with which results…"
        />
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
      <div>
        <SubmitButton pendingLabel="Analysing… (up to a few minutes)">
          Analyse my offer
        </SubmitButton>
      </div>
    </form>
  );
}
