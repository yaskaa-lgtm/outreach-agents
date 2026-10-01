import { Badge } from "@/components/ui/badge";

/** Human labels of the prospect states (backend/app/orchestrator/states.py). */
export const STATE_LABELS: Record<string, string> = {
  discovered: "Discovered",
  contact_found: "Contact found",
  email_verified: "Email verified",
  researched: "Researched",
  drafted: "Drafted",
  qa_passed: "QA passed",
  awaiting_approval: "Awaiting approval",
  scheduled: "Scheduled",
  sent: "Sent",
  replied: "Replied",
  bounced: "Bounced",
  unsubscribed: "Unsubscribed",
  completed: "Completed",
  failed: "Failed",
  excluded: "Excluded",
};

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state;
}

export function StateBadge({ state }: { state: string }) {
  const variant =
    state === "excluded" || state === "failed" || state === "bounced"
      ? "destructive"
      : state === "email_verified"
        ? "default"
        : "outline";
  return <Badge variant={variant}>{stateLabel(state)}</Badge>;
}

/** Only http(s) links are rendered, whatever the stored value. */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url) {
    return undefined;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}
