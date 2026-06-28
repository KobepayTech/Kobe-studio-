import NextAuth from 'next-auth';
import { authConfig } from '@/lib/auth.config';

// Edge-safe auth instance (no Prisma/Nodemailer) for route protection.
// The `authorized` callback in authConfig gates /studio, /account, etc.
//
// NOTE: we no longer rewrite /api/v1 to MuAPI here — in SaaS mode those
// requests must hit the gated Node route handlers (app/api/v1/...) which
// enforce auth + credit metering and inject the platform key.
export const { auth: middleware } = NextAuth(authConfig);

export default middleware;

export const config = {
  matcher: [
    // Run on everything except Next internals, auth endpoints, and static files.
    '/((?!api/auth|_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico)$).*)',
  ],
};
