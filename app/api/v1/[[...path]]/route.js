import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import { spendCredits, grantCredits } from '@/lib/credits';
import { prisma } from '@/lib/prisma';
import {
  MUAPI_BASE,
  forwardToMuapi,
  isSaasMode,
  isBillable,
  estimateCost,
  kindOf,
} from '@/lib/muapi';

// Gated catch-all proxy for MuAPI generation endpoints.
//
// In SaaS mode (MUAPI_PLATFORM_KEY set):
//   1. require a signed-in user
//   2. for billable POSTs, charge credits up front, refund on upstream failure
//   3. forward to MuAPI using the platform key
//
// More specific routes (creative-agent, get_upload_url, upload-binary) live in
// sibling folders and take precedence over this catch-all.

function buildTarget(request, pathSegments) {
  const path = (pathSegments || []).join('/');
  const { search } = new URL(request.url);
  return { path, url: `${MUAPI_BASE}/api/v1/${path}${search}` };
}

async function handle(request, params, method) {
  const slug = await params;
  const { path, url } = buildTarget(request, slug?.path);

  // Read body once (for cost estimation + forwarding).
  let body;
  if (method === 'POST' || method === 'PUT') {
    body = await request.text();
  }

  const saas = isSaasMode();
  let userId = null;

  if (saas) {
    const session = await auth();
    if (!session?.user?.id) {
      return NextResponse.json({ error: 'Sign in to generate' }, { status: 401 });
    }
    userId = session.user.id;
  }

  const billable = saas && isBillable(method, path);
  let cost = 0;
  let usageId = null;

  if (billable) {
    cost = estimateCost({ path, body });
    const usage = await prisma.usageEvent.create({
      data: { userId, kind: kindOf(path), model: path.split('/')[0] || null, cost, status: 'pending' },
    });
    usageId = usage.id;

    const spend = await spendCredits(userId, cost, {
      reason: 'generation',
      meta: { usageId, path },
    });

    if (!spend.ok) {
      await prisma.usageEvent.update({ where: { id: usageId }, data: { status: 'failed' } });
      return NextResponse.json(
        {
          error: 'insufficient_credits',
          message: 'Not enough credits. Upgrade your plan or buy a credit pack.',
          required: cost,
          balance: spend.balance,
        },
        { status: 402 },
      );
    }
  }

  try {
    const upstream = await forwardToMuapi({ request, targetUrl: url, method, body });
    const text = await upstream.text();

    // Refund on upstream failure so users aren't charged for our/MuAPI errors.
    if (billable && upstream.status >= 400) {
      await grantCredits(userId, cost, { reason: 'refund', meta: { usageId, status: upstream.status } });
      if (usageId) await prisma.usageEvent.update({ where: { id: usageId }, data: { status: 'refunded' } });
    } else if (billable && usageId) {
      await prisma.usageEvent.update({ where: { id: usageId }, data: { status: 'charged' } });
    }

    return new NextResponse(text, {
      status: upstream.status,
      headers: { 'content-type': upstream.headers.get('content-type') || 'application/json' },
    });
  } catch (error) {
    if (billable) {
      await grantCredits(userId, cost, { reason: 'refund', meta: { usageId, error: String(error) } });
      if (usageId) await prisma.usageEvent.update({ where: { id: usageId }, data: { status: 'refunded' } });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function GET(request, { params }) {
  return handle(request, params, 'GET');
}
export async function POST(request, { params }) {
  return handle(request, params, 'POST');
}
export async function PUT(request, { params }) {
  return handle(request, params, 'PUT');
}
export async function DELETE(request, { params }) {
  return handle(request, params, 'DELETE');
}
