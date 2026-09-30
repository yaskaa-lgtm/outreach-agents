import type { RunMode } from "@/lib/api";

const MODES: Record<RunMode, { label: string; detail: string; className: string }> = {
  DEMO: {
    label: "DEMO",
    detail: "Fake data and fake LLM. No email leaves this machine.",
    className: "bg-sky-600 text-white",
  },
  DRY_RUN: {
    label: "DRY RUN (Mailpit)",
    detail: "Real APIs, but every email is captured by Mailpit.",
    className: "bg-amber-500 text-black",
  },
  LIVE: {
    label: "LIVE",
    detail: "Emails are really sent after human approval.",
    className: "bg-red-600 text-white",
  },
};

/** Permanent banner showing which mode is active. Visible on every page. */
export function ModeBanner({ mode }: { mode: RunMode | null }) {
  const current = mode ? MODES[mode] : null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`sticky top-0 z-50 w-full px-4 py-2 text-center text-sm font-medium ${
        current ? current.className : "bg-neutral-700 text-white"
      }`}
    >
      {current ? (
        <>
          <span className="font-bold">{current.label}</span> — {current.detail}
        </>
      ) : (
        <>
          <span className="font-bold">API UNREACHABLE</span> — mode unknown, nothing can be sent.
        </>
      )}
    </div>
  );
}
