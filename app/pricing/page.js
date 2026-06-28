import Link from 'next/link';
import CheckoutButton from '@/components/CheckoutButton';
import { PLANS, CREDIT_PACKS } from '@/lib/billing-config';

export const metadata = { title: 'Pricing — kobeAi' };

export default function PricingPage() {
  const plans = Object.values(PLANS);
  const packs = Object.values(CREDIT_PACKS);

  return (
    <div className="min-h-screen bg-[#030303] text-white font-inter px-6 py-16">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <Link href="/studio" className="text-sm text-white/40 hover:text-white">← Back to studio</Link>
          <h1 className="text-4xl font-bold tracking-tight mt-4">Plans &amp; Pricing</h1>
          <p className="text-white/50 mt-3">Subscribe for monthly credits, or top up any time. Pay in your local currency.</p>
        </div>

        {/* Subscription plans */}
        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`rounded-2xl border p-7 flex flex-col ${
                plan.id === 'pro' ? 'border-[#22d3ee]/40 bg-[#22d3ee]/[0.04]' : 'border-white/10 bg-white/[0.02]'
              }`}
            >
              <h3 className="text-lg font-bold">{plan.name}</h3>
              <div className="mt-3 mb-1">
                <span className="text-4xl font-bold">${plan.priceUsd}</span>
                <span className="text-white/40 text-sm">/mo</span>
              </div>
              <p className="text-[#22d3ee] text-sm font-semibold">{plan.monthlyCredits.toLocaleString()} credits / month</p>
              <ul className="mt-5 space-y-2 text-sm text-white/60 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex gap-2"><span className="text-[#22d3ee]">✓</span>{f}</li>
                ))}
              </ul>
              <div className="mt-7">
                {plan.id === 'free' ? (
                  <Link href="/login" className="block text-center w-full border border-white/15 rounded-lg py-3 text-sm font-semibold hover:bg-white/5">
                    Get started
                  </Link>
                ) : (
                  <CheckoutButton
                    plan={plan.id}
                    className="w-full bg-[#22d3ee] text-black rounded-lg py-3 text-sm font-bold hover:bg-[#22d3ee]/90 transition-colors"
                  >
                    Subscribe to {plan.name}
                  </CheckoutButton>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Credit packs */}
        <div className="mt-16">
          <h2 className="text-2xl font-bold text-center">Need more? Buy credit packs</h2>
          <p className="text-white/50 text-center mt-2 text-sm">One-time top-ups that never expire. Stack on top of any plan.</p>
          <div className="grid sm:grid-cols-3 gap-6 mt-8">
            {packs.map((pack) => (
              <div key={pack.id} className="rounded-2xl border border-white/10 bg-white/[0.02] p-7 text-center">
                <p className="text-3xl font-bold">{pack.credits.toLocaleString()}</p>
                <p className="text-white/40 text-sm">credits</p>
                <p className="text-xl font-semibold mt-4">${pack.priceUsd}</p>
                <CheckoutButton
                  pack={pack.id}
                  className="mt-5 w-full border border-[#22d3ee]/30 text-[#22d3ee] rounded-lg py-2.5 text-sm font-semibold hover:bg-[#22d3ee]/10 transition-colors"
                >
                  Buy
                </CheckoutButton>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
