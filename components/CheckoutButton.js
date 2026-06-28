'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';

// Kicks off Stripe Checkout for a plan or credit pack.
export default function CheckoutButton({ plan, pack, children, className }) {
  const router = useRouter();
  const { status } = useSession();
  const [loading, setLoading] = useState(false);

  const go = async () => {
    if (status !== 'authenticated') {
      router.push(`/login?callbackUrl=/pricing`);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/billing/checkout', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(plan ? { plan } : { pack }),
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
      else {
        alert(data.error || 'Could not start checkout');
        setLoading(false);
      }
    } catch (e) {
      alert('Checkout failed');
      setLoading(false);
    }
  };

  return (
    <button onClick={go} disabled={loading} className={className}>
      {loading ? 'Redirecting…' : children}
    </button>
  );
}
