import NextAuth from 'next-auth';
import { PrismaAdapter } from '@auth/prisma-adapter';
import Google from 'next-auth/providers/google';
import Nodemailer from 'next-auth/providers/nodemailer';

import { prisma } from './prisma';
import { authConfig } from './auth.config';
import { SIGNUP_BONUS_CREDITS, PLANS } from './billing-config';
import { grantCredits } from './credits';

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(prisma),
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      allowDangerousEmailAccountLinking: true,
    }),
    Nodemailer({
      server: {
        host: process.env.EMAIL_SERVER_HOST,
        port: Number(process.env.EMAIL_SERVER_PORT || 587),
        auth: process.env.EMAIL_SERVER_USER
          ? {
              user: process.env.EMAIL_SERVER_USER,
              pass: process.env.EMAIL_SERVER_PASSWORD,
            }
          : undefined,
      },
      from: process.env.EMAIL_FROM || 'kobeAi <no-reply@kobe.ai>',
    }),
  ],
  events: {
    // First time a user is created, give them the free plan + signup bonus.
    async createUser({ user }) {
      try {
        await prisma.subscription.create({
          data: { userId: user.id, plan: 'free', status: 'active' },
        });
        const bonus = SIGNUP_BONUS_CREDITS + (PLANS.free.monthlyCredits || 0);
        if (bonus > 0) {
          await grantCredits(user.id, bonus, { reason: 'signup_bonus' });
        }
      } catch (e) {
        console.error('[auth.createUser] failed to provision user', e);
      }
    },
  },
});
