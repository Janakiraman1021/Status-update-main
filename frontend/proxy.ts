import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "worklog_session";

/**
 * Optimistic route protection: send visitors without a session cookie to the login page.
 * This is only a UX shortcut — the Flask API verifies the session on every request.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  const login = new URL("/login", request.url);
  if (pathname !== "/") login.searchParams.set("next", pathname + search);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/calendar/:path*", "/work-log/:path*", "/projects/:path*", "/eod/:path*", "/history/:path*", "/settings/:path*"],
};
