"use client";

import { useActionState } from "react";

import { updateBudget, type ActionState } from "@/app/(app)/actions";
import { SubmitButton } from "@/components/submit-button";
import { Input } from "@/components/ui/input";

type Budget = {
  spent_eur: number;
  limit_eur: number;
  ratio: number;
  state: "ok" | "warning" | "exhausted";
  resets_at: string;
};

const euros = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });

/** Daily LLM budget: silent below 80 %, warning above, "paused" at 100 % with a way to raise it. */
export function BudgetBanner({ budget }: { budget: Budget }) {
  const [state, formAction] = useActionState<ActionState, FormData>(updateBudget, {});
  if (budget.state === "ok") {
    return null;
  }
  const exhausted = budget.state === "exhausted";
  const resetTime = new Date(budget.resets_at).toLocaleString("fr-FR", {
    timeZone: "Europe/Paris",
    dateStyle: "short",
    timeStyle: "short",
  });

  return (
    <div
      role="alert"
      className={`border-b px-6 py-3 text-sm ${exhausted ? "bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100" : "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-100"}`}
    >
      <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-3">
        <p>
          <span className="font-semibold">
            {exhausted ? "LLM work paused." : "LLM budget almost used."}
          </span>{" "}
          {euros.format(budget.spent_eur)} spent of {euros.format(budget.limit_eur)} today (
          {Math.round(budget.ratio * 100)} %).{" "}
          {exhausted ? `It resumes on ${resetTime}, or now if you raise the budget.` : null}
        </p>
        <form action={formAction} className="flex items-center gap-2">
          <label htmlFor="daily_limit_eur" className="sr-only">
            New daily budget in euros
          </label>
          <Input
            id="daily_limit_eur"
            name="daily_limit_eur"
            type="number"
            min="0.01"
            max="1000"
            step="0.01"
            defaultValue={budget.limit_eur}
            className="bg-background w-28"
          />
          <SubmitButton pendingLabel="Saving…" variant="outline">
            Set daily budget
          </SubmitButton>
        </form>
      </div>
      {state.error ? <p className="mx-auto mt-2 max-w-4xl">{state.error}</p> : null}
    </div>
  );
}
