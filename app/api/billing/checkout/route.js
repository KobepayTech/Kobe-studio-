import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import { prisma } from '@/lib/prisma';
import { getStripe, getOrCreateCustomer } from '@/lib/stripe';
import { PLANS, CREDIT_PACKS } from '@/lib/billing-config';

// POST /api/billing/checkout  { plan?: "pro"|"studio", pack?: "small"|"medium"|"large" }
// Creates a Stripe Checkout session and returns { url }.
export async function POST(request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  const user = await prisma.user.findUnique({ where: { id: session.user.id } });
  if (!user) return NextResponse.json({ error: 'no user' }, { status: 404 });

  const origin =
    process.env.APP_URL ||
    request.headers.get('origin') ||
    new URL(request.url).origin;

  const stripe = getStripe();
  const customerId = await getOrCreateCustomer(prisma, user);

  let lineItem;
  let mode;
  let metadata = { userId: user.id };

  if (body.plan) {
    const plan = PLANS[body.plan];
    if (!plan || !plan.stripePriceId) {
      return NextResponse.json({ error: 'invalid plan' }, { status: 400 });
    }
    lineItem = { price: plan.stripePriceId, quantity: 1 };
    mode = 'subscription';
    metadata.kind = 'subscription';
    metadata.plan = plan.id;
  } else if (body.pack) {
    const pack = CREDIT_PACKS[body.pack];
    if (!pack || !pack.stripePriceId) {
      return NextResponse.json({ error: 'invalid pack' }, { status: 400 });
    }
    lineItem = { price: pack.stripePriceId, quantity: 1 };
    mode = 'payment';
    metadata.kind = 'credit_pack';
    metadata.pack = pack.id;
    metadata.credits = String(pack.credits);
  } else {
    return NextResponse.json({ error: 'plan or pack required' }, { status: 400 });
  }

  const checkout = await stripe.checkout.sessions.create({
    mode,
    customer: customerId,
    line_items: [lineItem],
    metadata,
    // Mirror metadata onto the subscription/payment_intent so webhooks can read it.
    ...(mode === 'subscription'
      ? { subscription_data: { metadata } }
      : { payment_intent_data: { metadata } }),
    allow_promotion_codes: true,
    success_url: `${origin}/account?checkout=success`,
    cancel_url: `${origin}/pricing?checkout=cancelled`,
  });

  return NextResponse.json({ url: checkout.url });
}
