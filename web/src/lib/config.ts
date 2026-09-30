import "server-only";

// Server-side configuration (read at request time, never sent to the browser).
export const config = {
  apiInternalUrl: process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000",
  apiPublicUrl: process.env.API_PUBLIC_URL ?? "http://localhost:8000",
  mailpitUiUrl: process.env.MAILPIT_UI_URL ?? "http://localhost:8025",
  sessionCookieName: process.env.SESSION_COOKIE_NAME ?? "oa_session",
  // Same rule as the API: Secure unless explicitly disabled for plain-http local use.
  sessionCookieSecure: (process.env.SESSION_COOKIE_SECURE ?? "true").toLowerCase() !== "false",
};
