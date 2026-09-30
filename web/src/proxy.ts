import { NextResponse, type NextRequest } from "next/server";

// Runs before every page request (Next.js 16 "proxy", formerly "middleware").
// 1. Strict Content-Security-Policy with a per-request nonce
//    (node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md).
// 2. Optimistic auth redirect: no session cookie -> /login. The real check is done by the
//    API on every call; this only avoids rendering pages that would fail anyway.

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "oa_session";
const PUBLIC_PATHS = ["/login"];

function contentSecurityPolicy(nonce: string): string {
  const isDev = process.env.NODE_ENV === "development";
  // style-src keeps 'unsafe-inline': UI components set inline style attributes, which
  // nonces cannot cover. Scripts, the real XSS risk, are nonce-only.
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  if (!hasSession && !PUBLIC_PATHS.includes(pathname)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
