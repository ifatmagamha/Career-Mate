import { useEffect, useRef, useState } from 'react';
import { API, apiFetch } from '@/app/api';
import { Sparkles, X, Send, Paperclip, Trash2, RotateCw, Check } from 'lucide-react';

// What the assistant is about: the offer on screen, or the profile everywhere else
export type AssistantContext = { kind: 'offer'; offerId: string; title: string } | { kind: 'profile' };

interface Message { id: number; role: 'user' | 'assistant' | 'event'; content: string; attachments: { id: string; label: string }[] }
interface Action { id: string; summary: string; status: 'pending' | 'done' | 'cancelled' | 'failed'; tool: string }
interface Doc { id: string; doc_type: string; version: number }

// Models add **bold** even when asked for plain text: show it as bold instead of raw asterisks (no HTML injection)
const withBold = (text: string) =>
  text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part));

const DOC_LABELS: Record<string, string> ={ 'cover-letter': 'Cover letter', 'cold-email': 'Cold email', 'interview': 'Interview prep' };

const QUICK: Record<AssistantContext['kind'], string[]> = {
  offer: [
    'How well does my profile match this offer?',
    'What should I ask the recruiter?',
    'Which of my projects should I highlight?',
    'Draft a short follow-up email.',
  ],
  profile: [
    'Improve my profile summary.',
    'Which skills appear most in my saved offers that I lack?',
    'Which of my saved offers fit me best?',
  ],
};

export function AssistantPanel({ context: pageContext, onDataChanged }: { context: AssistantContext; onDataChanged?: () => void }) {
  const [open, setOpen] = useState(false);
  // Outside an offer page you can still pick any saved offer to talk about
  const [offerList, setOfferList] = useState<{ id: string; title: string; company?: string }[]>([]);
  const [picked, setPicked] = useState<{ id: string; title: string } | null>(null);
  useEffect(() => { setPicked(null); }, [pageContext.kind === 'offer' ? pageContext.offerId : '']);
  const context: AssistantContext = pageContext.kind === 'offer' || !picked
    ? pageContext : { kind: 'offer', offerId: picked.id, title: picked.title };
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [attached, setAttached] = useState<Doc[]>([]);
  const [showDocs, setShowDocs] = useState(false);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const offerId = context.kind === 'offer' ? context.offerId : '';

  // Ctrl+K (or Cmd+K) opens and closes; Esc closes
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen((o) => !o); }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Load the conversation of this context when the panel is open
  useEffect(() => {
    if (!open) return;
    setConversationId(null);
    setMessages([]);
    setActions([]);
    setAttached([]);
    setError('');
    apiFetch(`${API}/api/assistant/conversation${offerId ? `?offer_id=${offerId}` : ''}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { setConversationId(d.conversation.id); setMessages(d.messages); setActions(d.actions); })
      .catch((e) => setError(`Could not open the assistant: ${e.message}`));
    if (offerId) {
      apiFetch(`${API}/api/offers/${offerId}/documents`).then((r) => (r.ok ? r.json() : [])).then(setDocs).catch(() => setDocs([]));
    } else {
      setDocs([]);
    }
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [open, offerId]);

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }); }, [messages, actions, busy]);

  useEffect(() => {
    if (!open || pageContext.kind === 'offer') return;
    apiFetch(`${API}/api/offers?sort=recent`).then((r) => (r.ok ? r.json() : []))
      .then((list) => setOfferList(list.map((o: any) => ({ id: o.id, title: o.title, company: o.company }))))
      .catch(() => setOfferList([]));
  }, [open, pageContext.kind]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || !conversationId || busy) return;
    setBusy(true);
    setError('');
    setText('');
    const optimistic: Message = { id: -Date.now(), role: 'user', content: q, attachments: attached.map((d) => ({ id: d.id, label: `${DOC_LABELS[d.doc_type] ?? d.doc_type} v${d.version}` })) };
    setMessages((m) => [...m, optimistic]);
    try {
      const res = await apiFetch(`${API}/api/assistant/conversations/${conversationId}/messages`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: q, attachments: attached.map((d) => d.id) }),
      });
      if (!res.ok) {
        setError((await res.json().catch(() => ({}))).detail || `Request failed (HTTP ${res.status})`);
        return;
      }
      const out = await res.json();
      setMessages((m) => [...m.filter((x) => x.id !== optimistic.id), out.user_message, out.message]);
      setActions((a) => [...a, ...out.actions]);
      setAttached([]);
    } catch {
      setError('Error connecting to server.');
    } finally {
      setBusy(false);
    }
  };

  const decide = async (action: Action, confirm: boolean) => {
    setError('');
    const res = await apiFetch(`${API}/api/assistant/actions/${action.id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm }),
    }).catch(() => null);
    if (!res) return setError('Error connecting to server.');
    if (!res.ok) return setError((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    const out = await res.json();
    setActions((a) => a.map((x) => (x.id === action.id ? out.action : x)));
    setMessages(out.messages);
    if (out.action.status === 'done') onDataChanged?.();
  };

  const clear = async () => {
    if (!conversationId || !confirm('Clear this conversation? Pending suggestions are dropped too.')) return;
    const res = await apiFetch(`${API}/api/assistant/conversations/${conversationId}/messages`, { method: 'DELETE' }).catch(() => null);
    if (res?.ok) { setMessages([]); setActions((a) => a.filter((x) => x.status !== 'pending')); }
  };

  const pending = actions.filter((a) => a.status === 'pending');
  const title = context.kind === 'offer' ? context.title : 'Your profile';

  return (
    <>
      {!open && (
        <button onClick={() => setOpen(true)} aria-label="Open the assistant (Ctrl+K)" title="Assistant (Ctrl+K)"
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg flex items-center justify-center hover:scale-105 transition-transform">
          <Sparkles className="w-6 h-6 text-white" />
        </button>
      )}

      {open && (
        <aside role="dialog" aria-label="Assistant"
          className="fixed z-50 top-16 right-0 bottom-0 w-full sm:w-[420px] bg-zinc-950 border-l border-zinc-800 flex flex-col">
          <header className="px-4 py-3 border-b border-zinc-800 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="font-semibold flex items-center gap-2"><Sparkles className="w-4 h-4 text-purple-400" />Assistant</p>
              {pageContext.kind === 'offer' ? (
                <p className="text-xs text-zinc-500 truncate">About: {title} · sees the offer, your CV, notes and documents</p>
              ) : (
                <select aria-label="Talk about" value={picked?.id ?? ''}
                  onChange={(e) => {
                    const o = offerList.find((x) => x.id === e.target.value);
                    setPicked(o ? { id: o.id, title: o.title } : null);
                  }}
                  className="mt-1 max-w-full bg-zinc-900 border border-zinc-800 rounded-md px-2 py-1 text-xs text-zinc-300">
                  <option value="">About: your profile and saved offers</option>
                  {offerList.map((o) => <option key={o.id} value={o.id}>About the offer: {o.title}{o.company ? ` · ${o.company}` : ''}</option>)}
                </select>
              )}
            </div>
            <div className="flex gap-1">
              <button onClick={clear} aria-label="Clear conversation" title="Clear conversation"
                className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-900"><Trash2 className="w-4 h-4" /></button>
              <button onClick={() => setOpen(false)} aria-label="Close the assistant"
                className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-900"><X className="w-4 h-4" /></button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3" aria-live="polite">
            {messages.length === 0 && !busy && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-500">Ask anything, or start with:</p>
                {QUICK[context.kind].map((q) => (
                  <button key={q} onClick={() => send(q)} disabled={!conversationId}
                    className="block w-full text-left text-sm px-3 py-2 rounded-lg border border-zinc-800 hover:border-zinc-600 disabled:opacity-50">{q}</button>
                ))}
              </div>
            )}
            {messages.map((m) => m.role === 'event' ? (
              <p key={m.id} className="text-xs text-center text-zinc-500">{m.content}</p>
            ) : (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${m.role === 'user' ? 'bg-white text-black' : 'bg-zinc-900 border border-zinc-800'}`}>
                  {m.role === 'assistant' ? withBold(m.content) : m.content}
                  {m.attachments?.length > 0 && (
                    <span className="block mt-1 text-xs opacity-70">📎 {m.attachments.map((a) => a.label).join(', ')}</span>
                  )}
                </div>
              </div>
            ))}
            {busy && <p className="text-sm text-zinc-500 flex items-center gap-2"><RotateCw className="w-4 h-4 animate-spin" />Thinking… (the first answer can take a minute if the server was asleep)</p>}
            {pending.map((a) => (
              <div key={a.id} className="border border-purple-800 bg-purple-950/30 rounded-xl p-3 text-sm">
                <p className="mb-2">{a.summary}?</p>
                <div className="flex gap-2">
                  <button onClick={() => decide(a, true)} className="px-3 py-1.5 rounded-lg bg-white text-black font-medium flex items-center gap-1"><Check className="w-4 h-4" />Confirm</button>
                  <button onClick={() => decide(a, false)} className="px-3 py-1.5 rounded-lg border border-zinc-700 text-zinc-300">Cancel</button>
                </div>
              </div>
            ))}
            {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
            <div ref={endRef} />
          </div>

          <footer className="border-t border-zinc-800 p-3 space-y-2">
            {attached.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {attached.map((d) => (
                  <span key={d.id} className="text-xs px-2 py-1 rounded-full bg-zinc-800 flex items-center gap-1">
                    📎 {DOC_LABELS[d.doc_type] ?? d.doc_type} v{d.version}
                    <button onClick={() => setAttached((a) => a.filter((x) => x.id !== d.id))} aria-label="Remove attachment"><X className="w-3 h-3" /></button>
                  </span>
                ))}
              </div>
            )}
            {showDocs && (
              <div className="border border-zinc-800 rounded-lg max-h-40 overflow-y-auto">
                {docs.length === 0 ? (
                  <p className="text-xs text-zinc-500 p-2">No documents for this offer yet. Generate one in the AI Generator.</p>
                ) : docs.map((d) => (
                  <button key={d.id} disabled={attached.length >= 3 || attached.some((x) => x.id === d.id)}
                    onClick={() => { setAttached((a) => [...a, d]); setShowDocs(false); }}
                    className="block w-full text-left text-sm px-3 py-1.5 hover:bg-zinc-900 disabled:opacity-40">
                    {DOC_LABELS[d.doc_type] ?? d.doc_type} v{d.version}
                  </button>
                ))}
              </div>
            )}
            <div className="flex items-end gap-2">
              {context.kind === 'offer' && (
                <button onClick={() => setShowDocs((s) => !s)} aria-label="Attach a document" title="Attach a saved document"
                  className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-900"><Paperclip className="w-5 h-5" /></button>
              )}
              <textarea ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={4000}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text); } }}
                placeholder="Ask anything… (Enter to send, Shift+Enter for a new line)" aria-label="Message"
                className="flex-1 resize-none bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600" />
              <button onClick={() => send(text)} disabled={busy || !text.trim() || !conversationId} aria-label="Send"
                className="p-2 rounded-lg bg-white text-black disabled:opacity-40"><Send className="w-5 h-5" /></button>
            </div>
          </footer>
        </aside>
      )}
    </>
  );
}
