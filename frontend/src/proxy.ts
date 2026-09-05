// Auth gate for the editorial admin panel (design.md Open Question,
// resolved: single shared token, not per-user accounts — this is a
// single-operator internal tool, per the explicit Non-Goal against
// multi-user roles/permissions). Next.js 16 renamed `middleware.ts` to
// `proxy.ts`; see docs/frontend-standards.md.
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "@/app/api/login/route";

export function proxy(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const expected = process.env.ADMIN_PANEL_TOKEN;

  if (expected && session === expected) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    // Everything except /login, /api/login, and Next.js internals.
    "/((?!login|api/login|_next/static|_next/image|favicon.ico).*)",
  ],
};
