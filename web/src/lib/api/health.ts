import "server-only";

import { cache } from "react";

import { api } from "./client";
import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];

/** /health once per request (React `cache` deduplicates calls). Null = API unreachable. */
export const getHealth = cache(async (): Promise<HealthResponse | null> => {
  try {
    const client = await api();
    const { data } = await client.GET("/health", { signal: AbortSignal.timeout(3000) });
    return data ?? null;
  } catch {
    return null;
  }
});
