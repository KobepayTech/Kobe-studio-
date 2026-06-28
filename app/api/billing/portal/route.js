import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import { prisma } from '@/lib/prisma';
import { getStripe, getOrCreateCustomer } from '@/lib/stripe';

// POST /api/billing/portal -> { url }  (Stripe customer portal for self-serve
// plan changes, cancellation, invoices, payment methods).
export async function POST(request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const user = await prisma.user.findUnique({ where: { id: session.user.id } });
  if (!user) return NextResponse.json({ error: 'no user' }, { status: 404 });

  const origin =
    process.env.APP_URL || request.headers.get('origin') || new URL(request.url).origin;

  const stripe = getStripe();
  const customerId = await getOrCreateCustomer(prisma, user);

  const portal = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: `${origin}/account`,
  });

  return NextResponse.json({ url: portal.url });
}
