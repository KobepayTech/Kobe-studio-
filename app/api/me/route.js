import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import { prisma } from '@/lib/prisma';
import { PLANS } from '@/lib/billing-config';

// GET /api/me -> the signed-in user's plan, credit balance and subscription.
export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ authenticated: false }, { status: 200 });
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    include: { subscription: true },
  });

  if (!user) return NextResponse.json({ authenticated: false }, { status: 200 });

  return NextResponse.json({
    authenticated: true,
    user: {
      id: user.id,
      name: user.name,
      email: user.email,
      image: user.image,
    },
    plan: user.plan,
    planName: PLANS[user.plan]?.name || user.plan,
    credits: user.credits,
    renewsAt: user.planRenewsAt,
    subscription: user.subscription
      ? {
          status: user.subscription.status,
          cancelAtPeriodEnd: user.subscription.cancelAtPeriodEnd,
          currentPeriodEnd: user.subscription.currentPeriodEnd,
        }
      : null,
  });
}
