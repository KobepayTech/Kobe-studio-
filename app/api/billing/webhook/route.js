import { NextResponse } from 'next/server';
import { getStripe } from '@/lib/stripe';
import { prisma } from '@/lib/prisma';
import { grantCredits, refillToMonthlyQuota } from '@/lib/credits';
import { planFromPriceId, packFromPriceId, PLANS } from '@/lib/billing-config';

// Stripe needs the raw request body to verify the signature.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

async function findUser({ userId, customerId }) {
  if (userId) {
    const u = await prisma.user.findUnique({ where: { id: userId } });
    if (u) return u;
  }
  if (customerId) {
    return prisma.user.findUnique({ where: { stripeCustomerId: customerId } });
  }
  return null;
}

// Idempotency: skip if a ledger row already references this Stripe object.
async function alreadyProcessed(ref) {
  const existing = await prisma.creditLedger.findFirst({
    where: { meta: { path: ['ref'], equals: ref } },
    select: { id: true },
  });
  return !!existing;
}

export async function POST(request) {
  const stripe = getStripe();
  const sig = request.headers.get('stripe-signature');
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  const raw = await request.text();

  let event;
  try {
    event = stripe.webhooks.constructEvent(raw, sig, secret);
  } catch (err) {
    console.error('[stripe webhook] signature verification failed:', err.message);
    return NextResponse.json({ error: 'invalid signature' }, { status: 400 });
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const cs = event.data.object;
        const meta = cs.metadata || {};
        // Only credit packs are settled here; subscriptions settle via invoice.paid.
        if (meta.kind === 'credit_pack') {
          const user = await findUser({ userId: meta.userId, customerId: cs.customer });
          const credits = Number(meta.credits || 0);
          if (user && credits > 0 && !(await alreadyProcessed(cs.id))) {
            await grantCredits(user.id, credits, {
              reason: 'credit_pack',
              meta: { ref: cs.id, pack: meta.pack },
            });
          }
        }
        break;
      }

      case 'customer.subscription.created':
      case 'customer.subscription.updated': {
        const sub = event.data.object;
        const user = await findUser({
          userId: sub.metadata?.userId,
          customerId: sub.customer,
        });
        if (!user) break;

        const priceId = sub.items?.data?.[0]?.price?.id;
        const plan = planFromPriceId(priceId);
        const planId = plan?.id || user.plan || 'free';
        const periodEnd = sub.current_period_end
          ? new Date(sub.current_period_end * 1000)
          : null;
        const active = ['active', 'trialing'].includes(sub.status);

        await prisma.subscription.upsert({
          where: { userId: user.id },
          create: {
            userId: user.id,
            stripeSubscriptionId: sub.id,
            stripePriceId: priceId,
            plan: planId,
            status: sub.status,
            currentPeriodEnd: periodEnd,
            cancelAtPeriodEnd: !!sub.cancel_at_period_end,
          },
          update: {
            stripeSubscriptionId: sub.id,
            stripePriceId: priceId,
            plan: planId,
            status: sub.status,
            currentPeriodEnd: periodEnd,
            cancelAtPeriodEnd: !!sub.cancel_at_period_end,
          },
        });

        await prisma.user.update({
          where: { id: user.id },
          data: {
            plan: active ? planId : 'free',
            planRenewsAt: periodEnd,
          },
        });
        break;
      }

      case 'customer.subscription.deleted': {
        const sub = event.data.object;
        const user = await findUser({
          userId: sub.metadata?.userId,
          customerId: sub.customer,
        });
        if (!user) break;
        await prisma.subscription.updateMany({
          where: { userId: user.id },
          data: { status: 'canceled', plan: 'free' },
        });
        await prisma.user.update({ where: { id: user.id }, data: { plan: 'free' } });
        break;
      }

      case 'invoice.paid': {
        const invoice = event.data.object;
        if (!['subscription_create', 'subscription_cycle'].includes(invoice.billing_reason)) {
          break;
        }
        const user = await findUser({ customerId: invoice.customer });
        if (!user) break;
        if (await alreadyProcessed(invoice.id)) break;

        const priceId = invoice.lines?.data?.[0]?.price?.id;
        const plan = planFromPriceId(priceId) || PLANS[user.plan] || PLANS.free;
        const periodEnd = invoice.lines?.data?.[0]?.period?.end
          ? new Date(invoice.lines.data[0].period.end * 1000)
          : null;

        await refillToMonthlyQuota(user.id, plan.monthlyCredits, {
          plan: plan.id,
          periodEnd,
        });
        // Tag the refill with the invoice id for idempotency.
        await prisma.creditLedger.create({
          data: {
            userId: user.id,
            delta: 0,
            reason: 'plan_grant',
            balanceAfter: (await prisma.user.findUnique({ where: { id: user.id }, select: { credits: true } })).credits,
            meta: { ref: invoice.id, plan: plan.id, marker: true },
          },
        });
        break;
      }

      default:
        break;
    }
  } catch (err) {
    console.error('[stripe webhook] handler error:', err);
    return NextResponse.json({ error: 'handler error' }, { status: 500 });
  }

  return NextResponse.json({ received: true });
}
