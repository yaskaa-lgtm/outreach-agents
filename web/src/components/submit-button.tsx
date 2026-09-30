"use client";

import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";

/** A submit button that shows a pending label while its form's server action runs. */
export function SubmitButton({
  children,
  pendingLabel,
  variant,
}: {
  children: React.ReactNode;
  pendingLabel: string;
  variant?: "default" | "outline" | "secondary" | "destructive";
}) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending} variant={variant} aria-busy={pending}>
      {pending ? pendingLabel : children}
    </Button>
  );
}
