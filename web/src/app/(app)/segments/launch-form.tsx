"use client";

import { useActionState } from "react";

import { SubmitButton } from "@/components/submit-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { launchCampaign, type ActionState } from "../actions";

/** Launches discovery on the selected segments (the worker does the rest in the background). */
export function LaunchForm({
  segmentIds,
  defaultName,
}: {
  segmentIds: string[];
  defaultName: string;
}) {
  const [state, formAction] = useActionState<ActionState, FormData>(launchCampaign, {});

  return (
    <form action={formAction} className="flex flex-col gap-4 rounded-xl border p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">Find companies</h2>
        <p className="text-muted-foreground text-sm">
          {segmentIds.length} selected segment{segmentIds.length > 1 ? "s" : ""}. Companies come
          from the official French registry; their website is checked against their SIREN, then a
          decision maker and a verified professional address are looked for. Nothing is sent.
        </p>
      </div>
      {segmentIds.map((id) => (
        <input key={id} type="hidden" name="segment_id" value={id} />
      ))}
      <div className="flex flex-col gap-2">
        <Label htmlFor="campaign_name">Campaign name</Label>
        <Input id="campaign_name" name="name" required maxLength={200} defaultValue={defaultName} />
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
      <div>
        <SubmitButton pendingLabel="Launching…">Launch the search</SubmitButton>
      </div>
    </form>
  );
}
