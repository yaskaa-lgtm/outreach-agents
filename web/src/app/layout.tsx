import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { connection } from "next/server";

import { ModeBanner } from "@/components/mode-banner";
import { getHealth } from "@/lib/api/health";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "outreach-agents",
  description: "Autonomous B2B prospecting agents with a human in the loop.",
  robots: { index: false, follow: false },
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // Render at request time: the mode must reflect the running API, not the build.
  await connection();
  const health = await getHealth();

  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <ModeBanner mode={health?.mode ?? null} />
        {children}
      </body>
    </html>
  );
}
