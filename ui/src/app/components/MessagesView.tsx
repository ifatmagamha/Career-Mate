import { useEffect, useState } from 'react';
import { API, apiFetch } from '@/app/api';
import { Plus, Pin, PinOff, Trash2, Copy, Send, Save, History, Pencil, FileText, Check, Sparkles } from 'lucide-react';

type Channel = 'linkedin-note' | 'linkedin-message' | 'email' | 'other';
interface Category { id: string; name: string; templates_count: number }
interface Template {
  id: string; category_id: string | null; title: string; channel: Channel; body: string; pinned: boolean;
  version: number; history: { version: number; body: string; replaced_at: string }[]; updated_at: string;
}
interface Message {
  id: string; category_id: string | null; template_id: string | null; offer_id: string | null; contact_id: string | null;
  channel: Channel; body: string; status: 'draft' | 'sent'; sent_at: string | null; updated_at: string;
  offer_title?: string | null; offer_company?: string | null; contact_name?: string | null;
}
interface Draft { id?: string; category_id: string; channel: Channel; offer_id: string; contact_id: string; template_id: string; body: string; status?: 'draft' | 'sent'; sent_at?: string | null }

const CHANNELS: { id: Channel; label: string; max: number }[] = [
  { id: 'linkedin-note', label: 'LinkedIn connection note', max: 300 },
  { id: 'linkedin-message', label: 'LinkedIn message', max: 8000 },
  { id: 'email', label: 'Email', max: 20000 },
  { id: 'other', label: 'Other', max: 20000 },
];
const channelOf = (c: Channel) => CHANNELS.find((x) => x.id === c)!;
const PLACEHOLDER_HELP = '{first_name} {contact_name} {their_role} {company} {role} {my_name}';
const emptyDraft = (category_id = ''): Draft => ({ category_id, channel: 'linkedin-message', offer_id: '', contact_id: '', template_id: '', body: '' });

const errorOf = async (res: Response) => {
  const body = await res.json().catch(() => ({}));
  return typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? String(body.detail[0]?.msg).replace(/^Value error, /, '') : `HTTP ${res.status}`;
};

// Messages: categories, a library of reference messages (pinned first) and a drafting space.
export function MessagesView({ initialOfferId = '', initialContactId = '' }: { initialOfferId?: string; initialContactId?: string }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<string>('');           // category id, or 'uncategorized'
  const [templates, setTemplates] = useState<Template[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [offers, setOffers] = useState<{ id: string; title: string; company?: string; application_id: string }[]>([]);
  const [contacts, setContacts] = useState<{ id: string; name: string; role?: string }[]>([]);
  const [draft, setDraft] = useState<Draft>({ ...emptyDraft(), offer_id: initialOfferId, contact_id: initialContactId });
  const [missing, setMissing] = useState<string[]>([]);
  const [newCategory, setNewCategory] = useState('');
  const [pinTitle, setPinTitle] = useState<string | null>(null);
  const [generalize, setGeneralize] = useState(true);  // pin with names turned back into placeholders
  // Adapt with AI: optional emphasis, the AI's list of changes, and the text before it (for Undo)
  const [emphasis, setEmphasis] = useState('');
  const [adapting, setAdapting] = useState(false);
  const [adapted, setAdapted] = useState<{ changes: string[]; before: string; overLimit: boolean } | null>(null);
  const [editing, setEditing] = useState<{ id: string; title: string; body: string } | null>(null);
  const [historyOf, setHistoryOf] = useState('');
  const [info, setInfo] = useState('');
  const [error, setError] = useState('');

  const request = async (url: string, method = 'GET', body?: object) => {
    setError('');
    const res = await apiFetch(`${API}${url}`, {
      method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
    }).catch(() => null);
    if (!res) { setError('Error connecting to server.'); return null; }
    if (!res.ok) { setError(await errorOf(res)); return null; }
    return res.status === 204 ? true : res.json();
  };
  const flash = (text: string) => { setInfo(text); setTimeout(() => setInfo(''), 1800); };

  const loadCategories = async () => {
    const cats = await request('/api/outreach/categories');
    if (cats) {
      setCategories(cats);
      setSelected((s) => s || cats[0]?.id || 'uncategorized');
    }
  };
  const loadTemplates = async () => {
    if (!selected) return;
    const list = await request(`/api/outreach/templates?category_id=${selected}`);
    if (list) setTemplates(list);
  };
  const loadMessages = async () => { const list = await request('/api/outreach/messages'); if (list) setMessages(list); };

  useEffect(() => {
    loadCategories();
    loadMessages();
    apiFetch(`${API}/api/offers?sort=recent`).then((r) => (r.ok ? r.json() : [])).then((list) =>
      setOffers(list.map((o: any) => ({ id: o.id, title: o.title, company: o.company, application_id: o.application_id })))).catch(() => {});
  }, []);
  useEffect(() => { loadTemplates(); setEditing(null); }, [selected]);
  useEffect(() => { if (!draft.category_id && selected && selected !== 'uncategorized') setDraft((d) => ({ ...d, category_id: selected })); }, [selected]);

  // Contacts of the chosen offer
  useEffect(() => {
    setContacts([]);
    const offer = offers.find((o) => o.id === draft.offer_id);
    if (!offer) return;
    apiFetch(`${API}/api/applications/${offer.application_id}/contacts`).then((r) => (r.ok ? r.json() : [])).then(setContacts).catch(() => {});
  }, [draft.offer_id, offers]);

  // Fill the placeholders of a text for the chosen offer and contact
  const render = async (body: string, offer_id = draft.offer_id, contact_id = draft.contact_id) => {
    const out = await request('/api/outreach/render', 'POST', { body, offer_id: offer_id || null, contact_id: contact_id || null });
    if (!out) return body;
    setMissing(out.missing);
    return out.body as string;
  };

  const useTemplate = async (t: Template) => {
    const body = await render(t.body);
    setDraft((d) => ({ ...d, id: undefined, status: undefined, sent_at: null, body, channel: t.channel,
      template_id: t.id, category_id: t.category_id || d.category_id }));
    setPinTitle(null);
    setAdapted(null);
  };

  const payload = () => ({
    body: draft.body, channel: draft.channel, category_id: draft.category_id || null, template_id: draft.template_id || null,
    offer_id: draft.offer_id || null, contact_id: draft.contact_id || null,
  });

  const saveDraft = async () => {
    const { template_id, ...rest } = payload();
    const saved = draft.id
      ? await request(`/api/outreach/messages/${draft.id}`, 'PATCH', rest)
      : await request('/api/outreach/messages', 'POST', { ...rest, template_id });
    if (saved) { setDraft((d) => ({ ...d, id: saved.id, status: saved.status })); flash('Draft saved'); loadMessages(); }
    return saved;
  };

  const markSent = async () => {
    const saved = await saveDraft();
    if (!saved) return;
    const sent = await request(`/api/outreach/messages/${saved.id}`, 'PATCH', { status: 'sent' });
    if (sent) { setDraft((d) => ({ ...d, status: 'sent', sent_at: sent.sent_at })); flash(draft.contact_id ? 'Marked as sent · contact ticked as reached out' : 'Marked as sent'); loadMessages(); }
  };

  const adaptWithAI = async () => {
    setAdapting(true);
    const out = await request('/api/outreach/adapt', 'POST', {
      body: draft.body, channel: draft.channel, offer_id: draft.offer_id || null, contact_id: draft.contact_id || null, extra: emphasis,
    });
    setAdapting(false);
    if (!out) return;
    setAdapted({ changes: out.changes, before: draft.body, overLimit: out.over_limit });
    setDraft((d) => ({ ...d, body: out.body }));
    setMissing(out.missing);
  };

  const pinToLibrary = async () => {
    if (!pinTitle?.trim()) return;
    const t = await request('/api/outreach/templates', 'POST', {
      title: pinTitle, body: draft.body, channel: draft.channel, category_id: draft.category_id || null, pinned: true,
      ...(generalize ? { generalize_offer_id: draft.offer_id || null, generalize_contact_id: draft.contact_id || null } : {}),
    });
    if (t) {
      setPinTitle(null);
      flash('Pinned to the library');
      if (draft.category_id) setSelected(draft.category_id);
      loadTemplates(); loadCategories();
    }
  };

  const openMessage = async (m: Message) => {
    setDraft({ id: m.id, category_id: m.category_id || '', channel: m.channel, offer_id: m.offer_id || '', contact_id: m.contact_id || '',
      template_id: m.template_id || '', body: m.body, status: m.status, sent_at: m.sent_at });
    setMissing([]);
    setPinTitle(null);
    setAdapted(null);
  };

  const addCategory = async () => {
    if (!newCategory.trim()) return;
    const c = await request('/api/outreach/categories', 'POST', { name: newCategory });
    if (c) { setNewCategory(''); await loadCategories(); setSelected(c.id); }
  };

  const max = channelOf(draft.channel).max;
  const over = draft.body.length > max;
  const input = 'bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600';
  const selectedName = selected === 'uncategorized' ? 'Uncategorized' : categories.find((c) => c.id === selected)?.name || '';
  const drafts = messages.filter((m) => m.status === 'draft');
  const sent = messages.filter((m) => m.status === 'sent');
  const msgLabel = (m: Message) => `${m.contact_name || m.offer_company || m.offer_title || 'No recipient'} · ${m.body.slice(0, 40)}`;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold mb-2">Messages</h1>
      <p className="text-zinc-400 mb-6">Reference messages by category, and a space to draft from them. Pin a draft that works to reuse it.</p>
      {error && <p role="alert" className="mb-4 px-4 py-3 rounded-xl border border-red-900 bg-red-950/40 text-red-300 text-sm">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Categories + drafts / sent */}
        <aside className="space-y-5">
          <div>
            <p className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Categories</p>
            <ul className="space-y-1">
              {categories.map((c) => (
                <li key={c.id} className="group flex items-center">
                  <button onClick={() => setSelected(c.id)}
                    className={`flex-1 text-left px-3 py-1.5 rounded-lg text-sm ${selected === c.id ? 'bg-white text-black' : 'text-zinc-300 hover:bg-zinc-900'}`}>
                    {c.name} <span className="opacity-60">{c.templates_count}</span>
                  </button>
                  <button aria-label={`Rename ${c.name}`} title="Rename" className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-white"
                    onClick={async () => { const n = prompt('Rename category', c.name); if (n && n !== c.name && await request(`/api/outreach/categories/${c.id}`, 'PATCH', { name: n })) loadCategories(); }}>
                    <Pencil className="w-3 h-3" />
                  </button>
                  <button aria-label={`Delete ${c.name}`} title="Delete" className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-red-400"
                    onClick={async () => { if (confirm(`Delete the category “${c.name}”? Its messages are kept as Uncategorized.`) && await request(`/api/outreach/categories/${c.id}`, 'DELETE')) { if (selected === c.id) setSelected(''); loadCategories(); } }}>
                    <Trash2 className="w-3 h-3" />
                  </button>
                </li>
              ))}
              <li>
                <button onClick={() => setSelected('uncategorized')}
                  className={`w-full text-left px-3 py-1.5 rounded-lg text-sm ${selected === 'uncategorized' ? 'bg-white text-black' : 'text-zinc-500 hover:bg-zinc-900'}`}>Uncategorized</button>
              </li>
            </ul>
            <div className="flex gap-1 mt-2">
              <input value={newCategory} onChange={(e) => setNewCategory(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addCategory()}
                placeholder="New category…" aria-label="New category name" className={`${input} flex-1 min-w-0 py-1.5`} />
              <button onClick={addCategory} disabled={!newCategory.trim()} aria-label="Add category" className="px-2 rounded-lg bg-white text-black disabled:opacity-40"><Plus className="w-4 h-4" /></button>
            </div>
          </div>

          {[['Drafts', drafts], ['Sent', sent]].map(([label, list]) => (
            <div key={label as string}>
              <p className="text-xs uppercase tracking-wider text-zinc-500 mb-2">{label as string} ({(list as Message[]).length})</p>
              <ul className="space-y-1 max-h-48 overflow-y-auto">
                {(list as Message[]).length === 0 && <li className="text-xs text-zinc-600 px-1">None yet.</li>}
                {(list as Message[]).map((m) => (
                  <li key={m.id}>
                    <button onClick={() => openMessage(m)}
                      className={`w-full text-left px-2 py-1.5 rounded-lg text-xs truncate ${draft.id === m.id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-900'}`}>
                      {msgLabel(m)}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </aside>

        {/* Library of the selected category */}
        <section aria-label="Reference messages">
          <p className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Library · {selectedName}</p>
          {templates.length === 0 && (
            <div className="border border-dashed border-zinc-800 rounded-xl p-6 text-sm text-zinc-500">
              No reference message here yet. Write one in the draft panel, then “Pin to library”.
            </div>
          )}
          <ul className="space-y-3">
            {templates.map((t) => (
              <li key={t.id} className={`rounded-xl border p-4 ${t.pinned ? 'border-zinc-500 bg-zinc-900' : 'border-zinc-800 bg-zinc-950'}`}>
                {editing?.id === t.id ? (
                  <div className="space-y-2">
                    <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} aria-label="Reference title" className={`${input} w-full`} />
                    <textarea value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} rows={6} aria-label="Reference text" className={`${input} w-full resize-y`} />
                    <div className="flex gap-2 justify-end">
                      <button onClick={() => setEditing(null)} className="px-3 py-1.5 rounded-lg border border-zinc-700 text-sm">Cancel</button>
                      <button onClick={async () => { if (await request(`/api/outreach/templates/${t.id}`, 'PATCH', { title: editing.title, body: editing.body })) { setEditing(null); loadTemplates(); } }}
                        className="px-3 py-1.5 rounded-lg bg-white text-black text-sm">Save as v{editing.body !== t.body ? t.version + 1 : t.version}</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start gap-2 mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{t.pinned && '📌 '}{t.title}</p>
                        <p className="text-xs text-zinc-500">{channelOf(t.channel).label} · v{t.version}</p>
                      </div>
                      <button onClick={async () => { if (await request(`/api/outreach/templates/${t.id}`, 'PATCH', { pinned: !t.pinned })) loadTemplates(); }}
                        aria-label={t.pinned ? 'Unpin' : 'Pin'} title={t.pinned ? 'Unpin' : 'Pin'} className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400">
                        {t.pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
                      </button>
                      <button onClick={() => setEditing({ id: t.id, title: t.title, body: t.body })} aria-label="Edit reference" title="Edit" className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400"><Pencil className="w-4 h-4" /></button>
                      {t.history.length > 0 && (
                        <button onClick={() => setHistoryOf(historyOf === t.id ? '' : t.id)} aria-label="Previous versions" title="Previous versions" className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400"><History className="w-4 h-4" /></button>
                      )}
                      <button onClick={async () => { if (confirm(`Delete “${t.title}”?`) && await request(`/api/outreach/templates/${t.id}`, 'DELETE')) { loadTemplates(); loadCategories(); } }}
                        aria-label="Delete reference" title="Delete" className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
                    </div>
                    <p className="text-sm text-zinc-300 whitespace-pre-wrap break-words line-clamp-6">{t.body}</p>
                    {historyOf === t.id && (
                      <ul className="mt-3 space-y-2 border-t border-zinc-800 pt-3">
                        {t.history.map((h) => (
                          <li key={h.version} className="text-xs text-zinc-500">
                            <span className="font-medium text-zinc-400">v{h.version}</span> · replaced {h.replaced_at.slice(0, 10)}
                            <p className="whitespace-pre-wrap break-words mt-1">{h.body}</p>
                          </li>
                        ))}
                      </ul>
                    )}
                    <button onClick={() => useTemplate(t)} className="mt-3 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm flex items-center gap-2">
                      <FileText className="w-4 h-4" />Use as draft
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>

        {/* Draft */}
        <section aria-label="Draft" className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3 self-start">
          <div className="flex items-center justify-between">
            <p className="font-semibold">{draft.id ? (draft.status === 'sent' ? 'Sent message' : 'Draft') : 'New draft'}</p>
            <button onClick={() => { setDraft(emptyDraft(selected !== 'uncategorized' ? selected : '')); setMissing([]); setPinTitle(null); setAdapted(null); }}
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1"><Plus className="w-3 h-3" />New draft</button>
          </div>
          {draft.status === 'sent' && draft.sent_at && <p className="text-xs text-green-400">Sent on {new Date(draft.sent_at).toLocaleDateString()}</p>}

          <div className="grid grid-cols-2 gap-2">
            <select value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })} aria-label="Category" className={input}>
              <option value="">No category</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select value={draft.channel} onChange={(e) => setDraft({ ...draft, channel: e.target.value as Channel })} aria-label="Channel" className={input}>
              {CHANNELS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
            <select value={draft.offer_id} onChange={(e) => setDraft({ ...draft, offer_id: e.target.value, contact_id: '' })} aria-label="For offer" className={input}>
              <option value="">No offer</option>
              {offers.map((o) => <option key={o.id} value={o.id}>{o.title}{o.company ? ` · ${o.company}` : ''}</option>)}
            </select>
            <select value={draft.contact_id} onChange={(e) => setDraft({ ...draft, contact_id: e.target.value })} aria-label="To contact" className={input} disabled={!draft.offer_id}>
              <option value="">{draft.offer_id ? (contacts.length ? 'No contact' : 'No contacts on this offer') : 'Pick an offer first'}</option>
              {contacts.map((k) => <option key={k.id} value={k.id}>{k.name}{k.role ? ` · ${k.role}` : ''}</option>)}
            </select>
          </div>

          <textarea value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} rows={10} aria-label="Message text"
            placeholder={`Write your message, or use a reference from the library.\nPlaceholders: ${PLACEHOLDER_HELP}`}
            className={`${input} w-full resize-y font-sans`} />
          <div className="flex items-center justify-between text-xs">
            <span className={over ? 'text-red-400' : 'text-zinc-500'}>{draft.body.length} / {max} characters{over ? ' · too long for this channel' : ''}</span>
            {/\{[a-z_]+\}/.test(draft.body) && (
              <button onClick={async () => { const body = await render(draft.body); setDraft((d) => ({ ...d, body })); }} className="text-blue-400 hover:underline">Fill placeholders</button>
            )}
          </div>
          {missing.length > 0 && <p className="text-xs text-amber-400">To fill by hand: {missing.map((m) => `{${m}}`).join(' ')}</p>}

          <div className="rounded-lg border border-purple-900/60 bg-purple-950/20 p-3 space-y-2">
            <div className="flex gap-2">
              <input value={emphasis} onChange={(e) => setEmphasis(e.target.value)} maxLength={500}
                placeholder="Optional: what to emphasize (e.g. their dbt talk, more formal)" aria-label="What to emphasize"
                className={`${input} flex-1 min-w-0 py-1.5`} />
              <button onClick={adaptWithAI} disabled={adapting || !draft.body.trim()}
                className="px-3 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-40">
                <Sparkles className={`w-4 h-4 ${adapting ? 'animate-pulse' : ''}`} />{adapting ? 'Adapting…' : 'Adapt with AI'}
              </button>
            </div>
            {!draft.offer_id && <p className="text-xs text-zinc-500">Pick an offer (and a contact) so the AI can use the offer and your company notes.</p>}
            {adapted && (
              <div className="text-xs space-y-1">
                <p className="text-zinc-400">What the AI says it changed:</p>
                <ul className="list-disc pl-5 text-zinc-300">
                  {adapted.changes.length ? adapted.changes.map((c, i) => <li key={i}>{c}</li>) : <li>No change listed.</li>}
                </ul>
                {/* measured by the app, not claimed by the AI */}
                <p className="text-zinc-500">Length: {adapted.before.length} → {draft.body.length} characters</p>
                {adapted.overLimit && <p className="text-red-400">Still over the limit for this channel: shorten it before sending.</p>}
                <p className="text-zinc-500">Check every detail before sending: it only uses your profile, the offer and your notes, but it can still get things wrong.</p>
                <button onClick={() => { setDraft((d) => ({ ...d, body: adapted.before })); setAdapted(null); }}
                  className="text-blue-400 hover:underline">Undo: restore my text</button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <button onClick={() => { navigator.clipboard.writeText(draft.body); flash('Copied'); }} disabled={!draft.body}
              className="px-3 py-2 rounded-lg border border-zinc-700 text-sm flex items-center gap-2 disabled:opacity-40"><Copy className="w-4 h-4" />Copy</button>
            <button onClick={saveDraft} disabled={!draft.body.trim() || over}
              className="px-3 py-2 rounded-lg border border-zinc-700 text-sm flex items-center gap-2 disabled:opacity-40"><Save className="w-4 h-4" />Save draft</button>
            <button onClick={() => setPinTitle(pinTitle === null ? '' : null)} disabled={!draft.body.trim() || over}
              className="px-3 py-2 rounded-lg border border-zinc-700 text-sm flex items-center gap-2 disabled:opacity-40"><Pin className="w-4 h-4" />Pin to library</button>
            <button onClick={markSent} disabled={!draft.body.trim() || over || draft.status === 'sent'}
              className="ml-auto px-3 py-2 rounded-lg bg-white text-black text-sm font-medium flex items-center gap-2 disabled:opacity-40"><Send className="w-4 h-4" />Mark as sent</button>
          </div>
          {pinTitle !== null && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <input autoFocus value={pinTitle} onChange={(e) => setPinTitle(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && pinToLibrary()}
                  placeholder="Name it, e.g. Warm intro to a recruiter" aria-label="Reference title" className={`${input} flex-1`} />
                <button onClick={pinToLibrary} disabled={!pinTitle.trim()} className="px-3 rounded-lg bg-white text-black text-sm disabled:opacity-40">Pin</button>
              </div>
              {(draft.offer_id || draft.contact_id) && (
                <label className="flex items-center gap-2 text-xs text-zinc-400">
                  <input type="checkbox" checked={generalize} onChange={(e) => setGeneralize(e.target.checked)} className="accent-white" />
                  Turn this offer's and contact's names back into placeholders, so the reference is reusable
                </label>
              )}
            </div>
          )}
          {info && <p className="text-xs text-green-400 flex items-center gap-1"><Check className="w-3 h-3" />{info}</p>}
        </section>
      </div>
    </div>
  );
}
