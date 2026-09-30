import { cache } from "react";

// Phase 0: hand-written types for the only endpoint. From Phase 1 on, the API client is
// generated from the FastAPI OpenAPI schema so that types can never drift.

export type RunMode = "DEMO" | "DRY_RUN" | "LIVE";

export interface HealthResponse {
  status: "ok" | "degraded";
  mode: RunMode;
  database: "ok" | "unavailable";
  version: string;
}

// Server-side URL of the API (inside docker compose: http://api:8000).
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

/** Fetch /health once per request (React `cache` deduplicates calls). Null = unreachable. */
export const getHealth = cache(async (): Promise<HealthResponse | null> => {
  try {
    const response = await fetch(`${API_INTERNAL_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as HealthResponse;
  } catch {
    return null;
  }
});
