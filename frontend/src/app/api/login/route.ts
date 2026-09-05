import { NextRequest, NextResponse } from "next/server";

export const SESSION_COOKIE_NAME = "admin_session";

export async function POST(request: NextRequest) {
  const { token } = await request.json();
  const expected = process.env.ADMIN_PANEL_TOKEN;

  if (!expected || token !== expected) {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE_NAME, expected, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });
  return response;
}
