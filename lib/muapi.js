// Server-side MuAPI helpers for SaaS mode.
//
// In SaaS mode the *platform* holds a single MuAPI key (MUAPI_PLATFORM_KEY) and
// every user request is proxied through it after auth + credit checks. Client
// supplied keys are ignored. If MUAPI_PLATFORM_KEY is unset we fall back to the
// legacy bring-your-own-key behaviour so the app still works in dev.

import {
  DEFAULT_COST,
  COST_BY_KIND,
  COST_BY_MODEL,
} from './billing-config';

export const MUAPI_BASE = process.env.MUAPI_BASE || 'https://api.muapi.ai';

export function platformKey() {
  return process.env.MUAPI_PLATFORM_KEY || null;
}

export function isSaasMode() {
  return !!platformKey();
}

// Resolve the upstream key: platform key in SaaS mode, else the client's key
// (header or muapi_key cookie) for legacy/self-key mode.
export function resolveUpstreamKey(request) {
  const pk = platformKey();
  if (pk) return pk;
  const headerKey = request.headers.get('x-api-key');
  if (headerKey) return headerKey;
  const auth = request.headers.get('authorization');
  if (auth?.startsWith('Bearer ')) return auth.slice(7);
  return request.cookies?.get?.('muapi_key')?.value || null;
}

export function cleanHeaders(request) {
  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('connection');
  headers.delete('cookie');
  headers.delete('authorization');
  headers.delete('x-api-key');
  return headers;
}

// Coarse classification of a request into a billing "kind".
function classify(path) {
  const p = path.toLowerCase();
  if (p.includes('lipsync') || p.includes('lip-sync') || p.includes('lip_sync')) return 'lipsync';
  if (p.includes('video') || p.includes('veo') || p.includes('kling') || p.includes('seedance') || p.includes('wan')) return 'video';
  if (p.includes('audio') || p.includes('music') || p.includes('tts') || p.includes('speech')) return 'audio';
  if (p.includes('workflow')) return 'workflow';
  if (p.includes('image') || p.includes('flux') || p.includes('sdxl') || p.includes('midjourney') || p.includes('ideogram')) return 'image';
  return 'other';
}

// Is this request a billable *generation create*? We charge on POSTs that kick
// off work, not on GET status polls / model listings.
export function isBillable(method, path) {
  if (method !== 'POST') return false;
  const p = path.toLowerCase();
  // Don't charge for plumbing endpoints.
  const free = ['upload', 'get_upload_url', 'get_file_upload_url', 'status', 'result', 'models', 'me', 'account'];
  if (free.some((f) => p.includes(f))) return false;
  return true;
}

// Estimate the credit cost of a billable request from its path + body.
export function estimateCost({ path, body }) {
  const hay = `${path} ${typeof body === 'string' ? body.slice(0, 2000) : ''}`.toLowerCase();
  for (const rule of COST_BY_MODEL) {
    if (hay.includes(rule.match)) return rule.cost;
  }
  const kind = classify(path);
  return COST_BY_KIND[kind] ?? DEFAULT_COST;
}

export function kindOf(path) {
  return classify(path);
}

// Forward a request to MuAPI with the resolved upstream key.
export async function forwardToMuapi({ request, targetUrl, method, body }) {
  const headers = cleanHeaders(request);
  const key = resolveUpstreamKey(request);
  if (key) headers.set('x-api-key', key);

  const init = { method, headers };
  if (body !== undefined && method !== 'GET' && method !== 'HEAD') {
    init.body = body;
  }
  return fetch(targetUrl, init);
}
