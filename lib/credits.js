import { prisma } from './prisma';

// Current spendable balance.
export async function getBalance(userId) {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { credits: true },
  });
  return user?.credits ?? 0;
}

// Atomically spend credits. Returns { ok, balance }.
// Uses a conditional update so two concurrent generations can't overspend.
export async function spendCredits(userId, amount, { reason = 'generation', meta = null } = {}) {
  if (amount <= 0) {
    const balance = await getBalance(userId);
    return { ok: true, balance };
  }

  return prisma.$transaction(async (tx) => {
    // Conditional decrement: only succeeds if balance is sufficient.
    const res = await tx.user.updateMany({
      where: { id: userId, credits: { gte: amount } },
      data: { credits: { decrement: amount } },
    });

    if (res.count === 0) {
      const user = await tx.user.findUnique({ where: { id: userId }, select: { credits: true } });
      return { ok: false, balance: user?.credits ?? 0 };
    }

    const user = await tx.user.findUnique({ where: { id: userId }, select: { credits: true } });
    const balanceAfter = user.credits;

    await tx.creditLedger.create({
      data: { userId, delta: -amount, reason, balanceAfter, meta },
    });

    return { ok: true, balance: balanceAfter };
  });
}

// Grant credits (purchase, plan renewal, bonus, refund). Returns new balance.
export async function grantCredits(userId, amount, { reason = 'plan_grant', meta = null } = {}) {
  if (amount <= 0) return getBalance(userId);

  return prisma.$transaction(async (tx) => {
    const user = await tx.user.update({
      where: { id: userId },
      data: { credits: { increment: amount } },
      select: { credits: true },
    });

    await tx.creditLedger.create({
      data: { userId, delta: amount, reason, balanceAfter: user.credits, meta },
    });

    return user.credits;
  });
}

// Set the monthly balance to exactly `monthlyCredits` (used on plan renewal so
// quotas don't stack forever). Keeps any positive top-up credits if you prefer
// — here we treat the plan as a refill floor: top up to at least the quota.
export async function refillToMonthlyQuota(userId, monthlyCredits, { plan, periodEnd } = {}) {
  return prisma.$transaction(async (tx) => {
    const current = await tx.user.findUnique({ where: { id: userId }, select: { credits: true } });
    const target = Math.max(current?.credits ?? 0, monthlyCredits);
    const delta = target - (current?.credits ?? 0);

    const user = await tx.user.update({
      where: { id: userId },
      data: {
        credits: target,
        ...(plan ? { plan } : {}),
        ...(periodEnd ? { planRenewsAt: periodEnd } : {}),
      },
      select: { credits: true },
    });

    if (delta !== 0) {
      await tx.creditLedger.create({
        data: { userId, delta, reason: 'plan_grant', balanceAfter: user.credits, meta: { plan } },
      });
    }

    return user.credits;
  });
}
