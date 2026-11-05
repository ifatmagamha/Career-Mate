/// <reference types="vite/client" />
import { createClient } from '@supabase/supabase-js';

// Backend address. To run the API elsewhere, create ui/.env.local with e.g. VITE_API_URL=http://localhost:8010
export const API: string = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Login (Supabase Auth). Without these two variables there is no login: the local API serves one dev user.
// The anon/publishable key is public by design: it only lets the browser talk to Supabase Auth.
const SUPABASE_URL: string | undefined = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_KEY: string | undefined = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const supabase = SUPABASE_URL && SUPABASE_KEY ? createClient(SUPABASE_URL, SUPABASE_KEY) : null;

// fetch() + the signed-in user's access token. supabase-js refreshes the token before it expires.
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`);
  }
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401 && supabase) await supabase.auth.signOut(); // session no longer valid: back to the login page
  return res;
}
