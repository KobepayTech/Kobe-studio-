'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';

// Small pill showing the signed-in user's credit balance + plan; links to /account.
// Drop <CreditBadge /> into any client shell/header.
export default function CreditBadge() {
  const { status } = useSession();
  const [me, setMe] = useState(null);

  useEffect(() => {
    if (status !== 'authenticated') return;
    let active = true;
    const load = () =>
      fetch('/api/me')
        .then((r) => r.json())
        .then((d) => active && d.authenticated && setMe(d))
        .catch(() => {});
    load();
    // Refresh after generations spend credits.
    const id = setInterval(load, 20000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [status]);

  if (status !== 'authenticated') {
    return (
      <Link href="/login" className="text-sm font-semibold text-white/70 hover:text-white">
        Sign in
      </Link>
    );
  }

  return (
    <Link
      href="/account"
      className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:border-[#22d3ee]/40 transition-colors"
      title="Manage account & billing"
    >
      <span className="text-[#22d3ee] font-bold">{me ? me.credits.toLocaleString() : '—'}</span>
      <span className="text-white/40">credits</span>
      {me?.planName && me.plan !== 'free' && (
        <span className="ml-1 rounded bg-[#22d3ee]/15 text-[#22d3ee] px-1.5 py-0.5 font-semibold">{me.planName}</span>
      )}
    </Link>
  );
}
