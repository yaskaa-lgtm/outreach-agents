import Link from "next/link";

import { logout } from "@/app/(app)/actions";
import { Button } from "@/components/ui/button";

const LINKS = [
  { href: "/onboarding", label: "1. Offer" },
  { href: "/segments", label: "2. Segments" },
  { href: "/campaigns", label: "3. Campaigns" },
];

export function AppHeader({ email }: { email: string }) {
  return (
    <header className="border-b">
      <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-4 px-6 py-3">
        <nav aria-label="Main" className="flex items-center gap-6">
          <span className="font-semibold">outreach-agents</span>
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <form action={logout} className="flex items-center gap-3">
          <span className="text-muted-foreground text-sm">{email}</span>
          <Button type="submit" variant="outline">
            Log out
          </Button>
        </form>
      </div>
    </header>
  );
}
