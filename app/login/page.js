'use client';

import { useState, Suspense } from 'react';
import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';

function LoginInner() {
  const params = useSearchParams();
  const callbackUrl = params.get('callbackUrl') || '/studio';
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleEmail = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    await signIn('nodemailer', { email: email.trim(), callbackUrl, redirect: false });
    setSent(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#030303] flex items-center justify-center px-4 font-inter text-white">
      <div className="w-full max-w-sm bg-[#0a0a0a]/90 backdrop-blur-xl border border-white/10 rounded-2xl p-10 shadow-2xl">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight">kobeAi</h1>
          <p className="text-white/40 text-sm mt-2">Sign in to start creating</p>
        </div>

        <button
          onClick={() => signIn('google', { callbackUrl })}
          className="w-full flex items-center justify-center gap-3 bg-white text-black font-semibold rounded-lg py-3 hover:bg-white/90 transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/><path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"/><path fill="#EA4335" d="M12 4.75c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 1.46 14.97.5 12 .5A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.3 9.14 4.75 12 4.75z"/></svg>
          Continue with Google
        </button>

        <div className="flex items-center gap-3 my-6 text-white/20 text-xs">
          <div className="h-px bg-white/10 flex-1" /> OR <div className="h-px bg-white/10 flex-1" />
        </div>

        {sent ? (
          <p className="text-center text-[#22d3ee] text-sm">
            Check your inbox — we sent a magic sign-in link to <b>{email}</b>.
          </p>
        ) : (
          <form onSubmit={handleEmail} className="space-y-3">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-3 text-sm outline-none focus:border-[#22d3ee]/50"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#22d3ee]/10 border border-[#22d3ee]/30 text-[#22d3ee] font-semibold rounded-lg py-3 hover:bg-[#22d3ee]/20 transition-colors disabled:opacity-50"
            >
              {loading ? 'Sending…' : 'Email me a magic link'}
            </button>
          </form>
        )}

        <p className="text-center text-white/20 text-[11px] mt-8 leading-relaxed">
          By continuing you agree to the kobeAi Terms & Privacy Policy.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#030303]" />}>
      <LoginInner />
    </Suspense>
  );
}
