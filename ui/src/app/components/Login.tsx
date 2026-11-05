import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { supabase, getAuthError, clearAuthError } from '@/app/api';

// Email + password sign-in / sign-up with Supabase Auth. The session is kept by supabase-js (local storage).
export function Login() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(() => {
    const e = getAuthError();
    return e ? { text: e, error: true } : null;
  });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setMessage(null);
    clearAuthError();
    const { data, error } = mode === 'signin'
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (error) setMessage({ text: error.message, error: true });
    else if (mode === 'signup' && !data.session) setMessage({ text: 'Check your inbox to confirm your email, then sign in.', error: false });
  };

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm bg-zinc-950 border border-zinc-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-semibold">Career Mate AI</span>
        </div>
        <h1 className="text-lg font-medium">{mode === 'signin' ? 'Sign in' : 'Create an account'}</h1>
        <label className="block text-sm text-zinc-400">
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white focus:outline-none focus:border-zinc-600" />
        </label>
        <label className="block text-sm text-zinc-400">
          Password
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            className="mt-1 w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white focus:outline-none focus:border-zinc-600" />
        </label>
        {message && <p role="alert" className={`text-sm ${message.error ? 'text-red-400' : 'text-green-400'}`}>{message.text}</p>}
        <button type="submit" disabled={busy}
          className="w-full py-2 bg-white text-black rounded-lg font-medium hover:bg-zinc-200 disabled:opacity-50">
          {busy ? '...' : mode === 'signin' ? 'Sign in' : 'Sign up'}
        </button>
        <button type="button" onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setMessage(null); }}
          className="w-full text-sm text-zinc-400 hover:text-white">
          {mode === 'signin' ? 'No account yet? Sign up' : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  );
}
