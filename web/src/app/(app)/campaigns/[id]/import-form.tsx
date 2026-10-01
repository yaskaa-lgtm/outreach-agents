"use client";

import { useActionState } from "react";

import { SubmitButton } from "@/components/submit-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { importCompaniesCsv, type CsvImportState } from "../../actions";

/** Adds companies from a CSV file; they go through the same checks as discovered ones. */
export function ImportForm({ campaignId }: { campaignId: string }) {
  const [state, formAction] = useActionState<CsvImportState, FormData>(
    importCompaniesCsv.bind(null, campaignId),
    {},
  );

  return (
    <form action={formAction} className="flex flex-col gap-4 rounded-xl border p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">Import companies from a CSV file</h2>
        <p className="text-muted-foreground text-sm">
          Comma or semicolon separated, 500 rows and 900 KB at most. Required column:{" "}
          <code>name</code>. Optional: <code>siren</code>, <code>website</code>,{" "}
          <code>naf_code</code>, <code>postal_code</code>, <code>city</code>,{" "}
          <code>first_name</code>, <code>last_name</code>, <code>title</code>, <code>email</code>.
          Imported addresses are only sendable once the website is confirmed by the SIREN and the
          address is verified.
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="csv_file">CSV file</Label>
        <Input id="csv_file" name="file" type="file" accept=".csv,text/csv" required />
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
      {state.ok ? (
        <div role="status" className="flex flex-col gap-1 text-sm">
          <p>
            {state.imported} compan{state.imported === 1 ? "y" : "ies"} added, {state.duplicates}{" "}
            already in this campaign.
          </p>
          {state.rowErrors && state.rowErrors.length > 0 ? (
            <ul className="text-muted-foreground list-disc pl-5">
              {state.rowErrors.slice(0, 20).map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div>
        <SubmitButton pendingLabel="Importing…" variant="outline">
          Import
        </SubmitButton>
      </div>
    </form>
  );
}
