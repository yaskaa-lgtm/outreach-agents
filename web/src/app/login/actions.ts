"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { api, errorMessage } from "@/lib/api/client";
import { config } from "@/lib/config";

export type LoginState = { error?: string };

/** Logs in through the API and keeps the session token in an HttpOnly cookie of this site. */
export async function login(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const client = await api();
  const { error, response } = await client.POST("/auth/login", { body: { email, password } });
  if (error) {
    return { error: errorMessage(error, "Login failed.") };
  }

  const token = sessionTokenFrom(response.headers.getSetCookie());
  if (!token) {
    return { error: "The API did not open a session." };
  }
  (await cookies()).set(config.sessionCookieName, token.value, {
    httpOnly: true,
    secure: config.sessionCookieSecure,
    sameSite: "lax",
    path: "/",
    expires: token.expires,
  });
  redirect("/onboarding");
}

function sessionTokenFrom(setCookies: string[]): { value: string; expires?: Date } | null {
  for (const header of setCookies) {
    const [pair, ...attributes] = header.split(";");
    const [name, ...rest] = pair.split("=");
    if (name.trim() !== config.sessionCookieName) {
      continue;
    }
    const expires = attributes
      .map((attribute) => attribute.trim())
      .find((attribute) => attribute.toLowerCase().startsWith("expires="));
    return {
      value: rest.join("=").trim(),
      expires: expires ? new Date(expires.slice("expires=".length)) : undefined,
    };
  }
  return null;
}
