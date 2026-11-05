/// <reference types="vite/client" />
import { createClient } from '@supabase/supabase-js';

// Backend address. To run the API elsewhere, create ui/.env.local with e.g. VITE_API_URL=http://localhost:8010
export const API: string = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Login (Supabase Auth). Without these two variables there is no login: the local API serves one dev user.
// The anon/publishable key is public by design: it only lets the browser talk to Supabase Auth.
const SUPABASE_URL: string | undefined = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_KEY: string | undefined = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const supabase = SUPABASE_URL && SUPABASE_KEY ? createClient(SUPABASE_URL, SUPABASE_KEY) : null;

// Why the last session ended, shown on the sign-in page (instead of a silent logout loop); cleared on the next attempt.
let authError: string | null = null;
export const getAuthError = (): string | null => authError;
export const clearAuthError = (): void => { authError = null; };

async function send(url: string, init: RequestInit, token?: string): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(url, { ...init, headers });
}

// fetch() + the signed-in user's access token. supabase-js refreshes the token before it expires.
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  if (!supabase) return send(url, init);
  const { data } = await supabase.auth.getSession();
  let res = await send(url, init, data.session?.access_token);
  if (res.status === 401 && data.session) {
    // One retry with a fresh token, then give up: the server does not accept this session.
    const { data: refreshed } = await supabase.auth.refreshSession();
    if (refreshed.session) res = await send(url, init, refreshed.session.access_token);
    if (res.status === 401) {
      const detail = await res.clone().json().then((b) => b.detail).catch(() => res.statusText);
      authError = `The server rejected your session (${detail}). Please sign in again.`;
      await supabase.auth.signOut();
    }
  }
  return res;
}
