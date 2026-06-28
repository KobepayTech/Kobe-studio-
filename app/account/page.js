'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { signOut } from 'next-auth/react';

export default function AccountPage() {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/me')
      .then((r) => r.json())
      .then((d) => setMe(d))
      .finally(() => setLoading(false));
  }, []);

  const openPortal = async () => {
    const res = await fetch('/api/billing/portal', { method: 'POST' });
    const data = await res.json();
    if (data.url) window.location.href = data.url;
    else alert(data.error || 'Could not open billing portal');
  };

  if (loading) return <div className="min-h-screen bg-[#030303]" />;

  if (!me?.authenticated) {
    return (
      <div className="min-h-screen bg-[#030303] text-white flex items-center justify-center font-inter">
        <div className="text-center">
          <p className="text-white/60 mb-4">You are not signed in.</p>
          <Link href="/login" className="text-[#22d3ee]">Sign in →</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#030303] text-white font-inter px-6 py-16">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-10">
          <Link href="/studio" className="text-sm text-white/40 hover:text-white">← Back to studio</Link>
          <button onClick={() => signOut({ callbackUrl: '/login' })} className="text-sm text-white/40 hover:text-white">
            Sign out
          </button>
        </div>

        <div className="flex items-center gap-4 mb-10">
          {me.user.image && <img src={me.user.image} alt="" className="w-14 h-14 rounded-full" />}
          <div>
            <h1 className="text-xl font-bold">{me.user.name || me.user.email}</h1>
            <p className="text-white/40 text-sm">{me.user.email}</p>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-5">
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <p className="text-white/40 text-xs uppercase tracking-wide">Credit balance</p>
            <p className="text-4xl font-bold mt-2 text-[#22d3ee]">{me.credits.toLocaleString()}</p>
            <Link href="/pricing" className="inline-block mt-4 text-sm text-[#22d3ee] hover:underline">
              Buy more credits →
            </Link>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <p className="text-white/40 text-xs uppercase tracking-wide">Current plan</p>
            <p className="text-2xl font-bold mt-2">{me.planName}</p>
            {me.renewsAt && (
              <p className="text-white/40 text-xs mt-1">
                Renews {new Date(me.renewsAt).toLocaleDateString()}
              </p>
            )}
            {me.subscription?.cancelAtPeriodEnd && (
              <p className="text-amber-400 text-xs mt-1">Cancels at period end</p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 mt-8">
          <Link
            href="/pricing"
            className="bg-[#22d3ee] text-black rounded-lg px-5 py-2.5 text-sm font-bold hover:bg-[#22d3ee]/90"
          >
            Upgrade plan
          </Link>
          <button
            onClick={openPortal}
            className="border border-white/15 rounded-lg px-5 py-2.5 text-sm font-semibold hover:bg-white/5"
          >
            Manage billing &amp; invoices
          </button>
        </div>
      </div>
    </div>
  );
}
