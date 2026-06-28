// Edge-safe Auth.js config (no Node-only deps like Prisma or Nodemailer).
// Used by middleware to read the JWT session at the edge. The full config in
// lib/auth.js extends this with the Prisma adapter and providers.

export const authConfig = {
  pages: {
    signIn: '/login',
  },
  session: { strategy: 'jwt' },
  callbacks: {
    // Expose the user id on the session for the client + API routes.
    async jwt({ token, user }) {
      if (user) token.uid = user.id;
      return token;
    },
    async session({ session, token }) {
      if (session.user && token?.uid) session.user.id = token.uid;
      return session;
    },
    // Protect the app: only signed-in users can reach the studio + account.
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const path = nextUrl.pathname;
      const isProtected =
        path.startsWith('/studio') ||
        path.startsWith('/account') ||
        path.startsWith('/workflow') ||
        path.startsWith('/agents');
      if (isProtected) return isLoggedIn;
      return true;
    },
  },
  // Providers are added in lib/auth.js (Node runtime).
  providers: [],
};
