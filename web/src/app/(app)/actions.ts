"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { api, errorMessage, type OfferProfileData } from "@/lib/api/client";
import { config } from "@/lib/config";

export type ActionState = { error?: string; ok?: boolean };

export async function analyzeOffer(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const websiteUrl = String(formData.get("website_url") ?? "").trim();
  const description = String(formData.get("description") ?? "").trim();
  const client = await api();
  const { error } = await client.POST("/offer-profiles/analyze", {
    body: {
      website_url: websiteUrl || null,
      description: description || null,
    },
  });
  if (error) {
    return { error: errorMessage(error, "The analysis failed.") };
  }
  revalidatePath("/onboarding");
  return { ok: true };
}

export async function saveProfile(profileId: string, data: OfferProfileData): Promise<ActionState> {
  const client = await api();
  const { error } = await client.PUT("/offer-profiles/{profile_id}", {
    params: { path: { profile_id: profileId } },
    body: { data },
  });
  if (error) {
    return { error: errorMessage(error, "The profile could not be saved.") };
  }
  revalidatePath("/onboarding");
  return { ok: true };
}

export async function validateProfile(profileId: string): Promise<ActionState> {
  const client = await api();
  const { error } = await client.POST("/offer-profiles/{profile_id}/validate", {
    params: { path: { profile_id: profileId } },
  });
  if (error) {
    return { error: errorMessage(error) };
  }
  revalidatePath("/onboarding");
  return { ok: true };
}

export async function generateSegments(profileId: string): Promise<ActionState> {
  const client = await api();
  const { error } = await client.POST("/offer-profiles/{profile_id}/segments", {
    params: { path: { profile_id: profileId } },
  });
  if (error) {
    return { error: errorMessage(error, "Segments could not be generated.") };
  }
  redirect("/segments");
}

export async function setSegmentSelected(
  segmentId: string,
  selected: boolean,
): Promise<ActionState> {
  const client = await api();
  const { error } = await client.PATCH("/segments/{segment_id}", {
    params: { path: { segment_id: segmentId } },
    body: { selected },
  });
  if (error) {
    return { error: errorMessage(error) };
  }
  revalidatePath("/segments");
  return { ok: true };
}

export async function updateBudget(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const value = Number(String(formData.get("daily_limit_eur") ?? "").replace(",", "."));
  const client = await api();
  const { error } = await client.PUT("/budget", { body: { daily_limit_eur: value } });
  if (error) {
    return { error: errorMessage(error, "Enter an amount between 0 and 1000 €.") };
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

export async function logout(): Promise<void> {
  const client = await api();
  await client.POST("/auth/logout");
  (await cookies()).delete(config.sessionCookieName);
  redirect("/login");
}
