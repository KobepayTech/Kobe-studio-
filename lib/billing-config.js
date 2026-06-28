// kobeAi — central billing configuration.
//
// Credits are the universal currency. 1 credit ≈ your smallest billable unit;
// set CREDIT_USD below to whatever you want a credit to cost the user, and tune
// the model costs to stay above your real MuAPI cost so you never lose money.
//
// Stripe price IDs are read from env so you can swap test/live without code
// changes. Create the products/prices in the Stripe dashboard, then paste the
// price IDs into your .env.

// Approx retail value of one credit, in USD (used only for display).
export const CREDIT_USD = 0.01;

// Subscription plans. `monthlyCredits` are granted on each successful invoice.
export const PLANS = {
  free: {
    id: 'free',
    name: 'Free',
    priceUsd: 0,
    monthlyCredits: 50,
    stripePriceId: null,
    features: ['50 credits / month', 'Standard models', 'Community support'],
  },
  pro: {
    id: 'pro',
    name: 'Pro',
    priceUsd: 19,
    monthlyCredits: 2500,
    stripePriceId: process.env.STRIPE_PRICE_PRO || '',
    features: ['2,500 credits / month', 'All models', 'Priority queue', 'Email support'],
  },
  studio: {
    id: 'studio',
    name: 'Studio',
    priceUsd: 79,
    monthlyCredits: 12000,
    stripePriceId: process.env.STRIPE_PRICE_STUDIO || '',
    features: ['12,000 credits / month', 'All models', 'Highest priority', 'Commercial license'],
  },
};

// One-time credit top-up packs (Stripe one-time prices, `mode: payment`).
export const CREDIT_PACKS = {
  small: {
    id: 'small',
    name: '1,000 credits',
    credits: 1000,
    priceUsd: 12,
    stripePriceId: process.env.STRIPE_PRICE_PACK_SMALL || '',
  },
  medium: {
    id: 'medium',
    name: '5,000 credits',
    credits: 5000,
    priceUsd: 50,
    stripePriceId: process.env.STRIPE_PRICE_PACK_MEDIUM || '',
  },
  large: {
    id: 'large',
    name: '20,000 credits',
    credits: 20000,
    priceUsd: 180,
    stripePriceId: process.env.STRIPE_PRICE_PACK_LARGE || '',
  },
};

// Credits granted to a brand-new account on first sign-in.
export const SIGNUP_BONUS_CREDITS = 25;

// ---------------------------------------------------------------------------
// Generation cost model
// ---------------------------------------------------------------------------
// MuAPI charges per generation and varies wildly by model (an SDXL image is
// cheap; a Veo/Kling video is expensive). We approximate that with a cost table
// keyed by a coarse "kind" plus optional per-model overrides. Tune these to sit
// safely above your real upstream cost.

export const DEFAULT_COST = 5;

export const COST_BY_KIND = {
  image: 5,
  audio: 8,
  lipsync: 25,
  video: 40,
  workflow: 10,
  other: 5,
};

// Substring match on the model id / path → fixed cost. First match wins.
export const COST_BY_MODEL = [
  // expensive video models
  { match: 'veo', cost: 120 },
  { match: 'kling', cost: 90 },
  { match: 'seedance', cost: 80 },
  { match: 'wan', cost: 60 },
  // mid-tier
  { match: 'midjourney', cost: 12 },
  { match: 'flux', cost: 8 },
  { match: 'ideogram', cost: 8 },
  // cheap
  { match: 'sdxl', cost: 4 },
  { match: 'sd15', cost: 3 },
];

export function planFromPriceId(priceId) {
  for (const plan of Object.values(PLANS)) {
    if (plan.stripePriceId && plan.stripePriceId === priceId) return plan;
  }
  return null;
}

export function packFromPriceId(priceId) {
  for (const pack of Object.values(CREDIT_PACKS)) {
    if (pack.stripePriceId && pack.stripePriceId === priceId) return pack;
  }
  return null;
}
