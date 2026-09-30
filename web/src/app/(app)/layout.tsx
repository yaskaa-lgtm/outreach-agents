import { redirect } from "next/navigation";

import { AppHeader } from "@/components/app-header";
import { BudgetBanner } from "@/components/budget-banner";
import { api } from "@/lib/api/client";

/** Every page of the app needs a valid session; the budget banner is shown on all of them. */
export default async function AppLayout({ children }: LayoutProps<"/">) {
  const client = await api();
  const [{ data: user }, { data: budget }] = await Promise.all([
    client.GET("/auth/me"),
    client.GET("/budget"),
  ]);
  if (!user) {
    redirect("/login");
  }

  return (
    <>
      <AppHeader email={user.email} />
      {budget ? <BudgetBanner budget={budget} /> : null}
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-10">
        {children}
      </main>
    </>
  );
}
