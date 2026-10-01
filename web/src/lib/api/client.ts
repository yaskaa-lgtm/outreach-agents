import "server-only";

import createClient from "openapi-fetch";
import { cookies } from "next/headers";

import { config } from "@/lib/config";

import type { components, paths } from "./schema";

// Types generated from the FastAPI OpenAPI schema (npm run api:types).
export type OfferProfile = components["schemas"]["OfferProfileRead"];
export type OfferProfileData = components["schemas"]["OfferProfileData"];
export type SourcedClaim = components["schemas"]["SourcedClaim"];
export type Segment = components["schemas"]["SegmentRead"];
export type BudgetStatus = components["schemas"]["BudgetStatus"];
export type User = components["schemas"]["UserRead"];
export type RunMode = components["schemas"]["RunMode"];
export type Campaign = components["schemas"]["CampaignRead"];
export type ProspectRow = components["schemas"]["ProspectRow"];
export type ProspectDetail = components["schemas"]["ProspectDetail"];
export type CsvImportResult = components["schemas"]["CsvImportResult"];

/**
 * API client for server components and server actions. The session cookie of the
 * incoming request is forwarded, so the API sees the logged-in user. The browser never
 * talks to the API directly (backend-for-frontend pattern).
 */
export async function api() {
  const session = (await cookies()).get(config.sessionCookieName)?.value;
  return createClient<paths>({
    baseUrl: config.apiInternalUrl,
    headers: session ? { Cookie: `${config.sessionCookieName}=${session}` } : {},
    cache: "no-store",
  });
}

/** Human-readable message from an API error body (our `{code, message}` or FastAPI's `detail`). */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error && typeof error === "object") {
    if ("message" in error && typeof error.message === "string") {
      return error.message;
    }
    if ("detail" in error && Array.isArray(error.detail)) {
      return error.detail
        .map((item: { msg?: string }) => item.msg)
        .filter(Boolean)
        .join(" ");
    }
  }
  return fallback;
}

/** Stable machine-readable code of an API error, when there is one. */
export function errorCode(error: unknown): string | undefined {
  if (error && typeof error === "object" && "code" in error && typeof error.code === "string") {
    return error.code;
  }
  return undefined;
}
