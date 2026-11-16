import { useEffect, useState } from 'react';
import { API, apiFetch } from '@/app/api';
import { Building2, Plus, Trash2, ExternalLink, Search, Link as LinkIcon, Check } from 'lucide-react';

interface CompanyRow { id: string; name: string; website?: string; offers_count: number; open_todos: number; notes_count: number; flagged_notes: number }
interface Todo { id: string; text: string; done: boolean; due_date?: string | null }
interface LinkItem { label: string; url: string }
type Flag = 'important' | 'follow-up' | 'question' | 'risk';
interface Note { id: string; body: string; flag: Flag | null; pinned: boolean; created_at: string; updated_at: string }
interface Company {
  id: string; name: string; website?: string | null; links: LinkItem[]; notes: Note[];
  todos: Todo[]; offers: any[];
}

const FLAGS: { id: Flag; label: string; cls: string }[] = [
  { id: 'important', label: 'Important', cls: 'bg-amber-500/15 text-amber-300 border-amber-700' },
  { id: 'follow-up', label: 'Follow-up', cls: 'bg-blue-500/15 text-blue-300 border-blue-700' },
  { id: 'question', label: 'Question', cls: 'bg-purple-500/15 text-purple-300 border-purple-700' },
  { id: 'risk', label: 'Risk', cls: 'bg-red-500/15 text-red-300 border-red-800' },
];
const flagOf = (f: Flag | null) => FLAGS.find((x) => x.id === f);

// Dated notes on a company: add, flag, pin, edit, delete, and filter by flag
function NotesSection({ company, reload, setError, input }: {
  company: Company; reload: () => Promise<void>; setError: (e: string) => void; input: string;
}) {
  const [draft, setDraft] = useState({ body: '', flag: '' as Flag | '', pinned: false });
  const [filter, setFilter] = useState<'all' | 'pinned' | Flag>('all');
  const [editing, setEditing] = useState<{ id: string; body: string } | null>(null);

  const call = async (url: string, method: string, body?: object) => {
    setError('');
    const res = await apiFetch(url, {
      method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
    }).catch(() => null);
    if (!res) { setError('Error connecting to server.'); return false; }
    if (!res.ok) { setError(await errorOf(res)); return false; }
    await reload();
    return true;
  };

  const add = async () => {
    if (!draft.body.trim()) return;
    if (await call(`${API}/api/companies/${company.id}/notes`, 'POST',
      { body: draft.body, flag: draft.flag || null, pinned: draft.pinned })) setDraft({ body: '', flag: '', pinned: false });
  };

  const shown = company.notes.filter((n) => filter === 'all' || (filter === 'pinned' ? n.pinned : n.flag === filter));
  const chip = (id: typeof filter, label: string, count: number) => (
    <button key={id} onClick={() => setFilter(id)} aria-pressed={filter === id}
      className={`px-2.5 py-1 rounded-full text-xs border ${filter === id ? 'bg-white text-black border-white' : 'border-zinc-700 text-zinc-400 hover:text-white'}`}>
      {label} <span className="opacity-60">{count}</span>
    </button>
  );

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
      <div>
        <h3 className="font-semibold">Notes</h3>
        <p className="text-xs text-zinc-500">One note per call, interview or finding. Flag or pin what matters: the assistant reads flagged and pinned notes first.</p>
      </div>

      <div className="space-y-2">
        <textarea value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} rows={3} maxLength={5000}
          aria-label="New note" placeholder="e.g. Call with Sam: team of 6, take-home in dbt, decision in 2 weeks"
          className={`${input} w-full resize-y`} />
        <div className="flex flex-wrap items-center gap-2">
          <select value={draft.flag} onChange={(e) => setDraft({ ...draft, flag: e.target.value as Flag | '' })}
            aria-label="Flag for the new note" className={input}>
            <option value="">No flag</option>
            {FLAGS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-zinc-400">
            <input type="checkbox" checked={draft.pinned} onChange={(e) => setDraft({ ...draft, pinned: e.target.checked })} className="accent-white" />
            Pin
          </label>
          <button onClick={add} disabled={!draft.body.trim()} className="ml-auto px-3 py-2 rounded-lg bg-white text-black text-sm disabled:opacity-40">Add note</button>
        </div>
      </div>

      {company.notes.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter notes">
          {chip('all', 'All', company.notes.length)}
          {chip('pinned', 'Pinned', company.notes.filter((n) => n.pinned).length)}
          {FLAGS.map((f) => chip(f.id, f.label, company.notes.filter((n) => n.flag === f.id).length))}
        </div>
      )}

      <ul className="space-y-2">
        {company.notes.length === 0 && <li className="text-sm text-zinc-500">No notes yet.</li>}
        {company.notes.length > 0 && shown.length === 0 && <li className="text-sm text-zinc-500">No note with this flag.</li>}
        {shown.map((n) => (
          <li key={n.id} className={`rounded-lg border p-3 ${n.pinned ? 'border-zinc-500 bg-zinc-800/60' : 'border-zinc-800'}`}>
            <div className="flex items-center gap-2 mb-1 text-xs text-zinc-500">
              {n.pinned && <span className="text-zinc-300">📌 Pinned</span>}
              {flagOf(n.flag) && <span className={`px-2 py-0.5 rounded-full border ${flagOf(n.flag)!.cls}`}>{flagOf(n.flag)!.label}</span>}
              <span>{new Date(n.created_at).toLocaleDateString()}{n.updated_at.slice(0, 16) !== n.created_at.slice(0, 16) ? ' · edited' : ''}</span>
              <span className="ml-auto flex items-center gap-1">
                <select value={n.flag ?? ''} onChange={(e) => call(`${API}/api/company-notes/${n.id}`, 'PATCH', { flag: e.target.value || null })}
                  aria-label="Change flag" className="bg-transparent border border-zinc-800 rounded px-1 py-0.5 text-zinc-400">
                  <option value="">No flag</option>
                  {FLAGS.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
                </select>
                <button onClick={() => call(`${API}/api/company-notes/${n.id}`, 'PATCH', { pinned: !n.pinned })}
                  aria-label={n.pinned ? 'Unpin note' : 'Pin note'} title={n.pinned ? 'Unpin' : 'Pin'}
                  className="px-1.5 py-0.5 rounded hover:bg-zinc-800">{n.pinned ? 'Unpin' : 'Pin'}</button>
                <button onClick={() => setEditing({ id: n.id, body: n.body })} aria-label="Edit note"
                  className="px-1.5 py-0.5 rounded hover:bg-zinc-800">Edit</button>
                <button onClick={() => confirm('Delete this note?') && call(`${API}/api/company-notes/${n.id}`, 'DELETE')}
                  aria-label="Delete note" className="p-1 rounded hover:bg-zinc-800 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
              </span>
            </div>
            {editing?.id === n.id ? (
              <div className="space-y-2">
                <textarea value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} rows={3}
                  aria-label="Edit note text" className={`${input} w-full resize-y`} />
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setEditing(null)} className="px-3 py-1.5 rounded-lg border border-zinc-700 text-sm">Cancel</button>
                  <button onClick={async () => { if (await call(`${API}/api/company-notes/${n.id}`, 'PATCH', { body: editing.body })) setEditing(null); }}
                    disabled={!editing.body.trim()} className="px-3 py-1.5 rounded-lg bg-white text-black text-sm disabled:opacity-40">Save</button>
                </div>
              </div>
            ) : (
              <p className="text-sm whitespace-pre-wrap break-words">{n.body}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

const errorOf = async (res: Response) => {
  const body = await res.json().catch(() => ({}));
  return typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : `HTTP ${res.status}`;
};

// Company directory: notes, links and a to-do list per company, plus the offers you saved there
export function CompaniesView({ initialCompanyId, onOpenOffer }: { initialCompanyId?: string; onOpenOffer: (offer: any) => void }) {
  const [rows, setRows] = useState<CompanyRow[]>([]);
  const [query, setQuery] = useState('');
  const [newName, setNewName] = useState('');
  const [selectedId, setSelectedId] = useState(initialCompanyId || '');
  const [company, setCompany] = useState<Company | null>(null);
  const [website, setWebsite] = useState('');
  const [newLink, setNewLink] = useState<LinkItem>({ label: '', url: '' });
  const [newTodo, setNewTodo] = useState({ text: '', due_date: '' });
  const [saved, setSaved] = useState('');
  const [error, setError] = useState('');

  const loadList = () =>
    apiFetch(`${API}/api/companies`).then((r) => (r.ok ? r.json() : [])).then(setRows).catch(() => setRows([]));

  useEffect(() => { loadList(); }, []);

  useEffect(() => {
    setCompany(null);
    if (!selectedId) return;
    apiFetch(`${API}/api/companies/${selectedId}`).then((r) => (r.ok ? r.json() : null)).then((c) => {
      setCompany(c);
      setWebsite(c?.website || '');
    });
  }, [selectedId]);

  const reloadCompany = async () => {
    if (!company) return;
    const res = await apiFetch(`${API}/api/companies/${company.id}`).catch(() => null);
    if (res?.ok) setCompany(await res.json());
    loadList();
  };

  const patch = async (body: object, what = 'Saved') => {
    if (!company) return;
    setError('');
    const res = await apiFetch(`${API}/api/companies/${company.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }).catch(() => null);
    if (!res) return setError('Error connecting to server.');
    if (!res.ok) return setError(await errorOf(res));
    setCompany(await res.json());
    setSaved(what);
    setTimeout(() => setSaved(''), 1500);
    loadList();
  };

  const create = async () => {
    const name = newName.trim();
    if (!name) return;
    setError('');
    const res = await apiFetch(`${API}/api/companies`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
    }).catch(() => null);
    if (!res) return setError('Error connecting to server.');
    if (!res.ok) return setError(await errorOf(res));
    const c = await res.json();
    setNewName('');
    await loadList();
    setSelectedId(c.id);
  };

  const remove = async () => {
    if (!company || !confirm(`Delete ${company.name} and its to-dos? Your offers are kept.`)) return;
    const res = await apiFetch(`${API}/api/companies/${company.id}`, { method: 'DELETE' }).catch(() => null);
    if (res?.ok) { setSelectedId(''); loadList(); }
  };

  const todoRequest = async (url: string, method: string, body?: object) => {
    setError('');
    const res = await apiFetch(url, {
      method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
    }).catch(() => null);
    if (!res) return setError('Error connecting to server.');
    if (!res.ok) return setError(await errorOf(res));
    const c = await apiFetch(`${API}/api/companies/${company!.id}`).then((r) => r.json());
    setCompany(c);
    loadList();
  };

  const addTodo = async () => {
    if (!newTodo.text.trim()) return;
    await todoRequest(`${API}/api/companies/${company!.id}/todos`, 'POST',
      { text: newTodo.text, ...(newTodo.due_date ? { due_date: newTodo.due_date } : {}) });
    setNewTodo({ text: '', due_date: '' });
  };

  const shown = rows.filter((r) => r.name.toLowerCase().includes(query.toLowerCase()));
  const input = 'bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold mb-2">Companies</h1>
      <p className="text-zinc-400 mb-8">What you know about each company, useful links and your to-dos. Offers are linked by company name.</p>

      <div className="grid gap-6 md:grid-cols-[280px_1fr]">
        <aside className="space-y-3">
          <div className="flex gap-2">
            <input value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && create()}
              placeholder="Add a company…" aria-label="New company name" className={`${input} flex-1 min-w-0`} />
            <button onClick={create} disabled={!newName.trim()} aria-label="Add company"
              className="px-3 rounded-lg bg-white text-black disabled:opacity-40"><Plus className="w-4 h-4" /></button>
          </div>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-zinc-500" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search"
              aria-label="Search companies" className={`${input} w-full pl-9`} />
          </div>
          {shown.length === 0 && <p className="text-sm text-zinc-500 px-1">{rows.length ? 'No match.' : 'No companies yet.'}</p>}
          <ul className="space-y-1">
            {shown.map((r) => (
              <li key={r.id}>
                <button onClick={() => setSelectedId(r.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg border text-sm ${r.id === selectedId ? 'border-white bg-zinc-900' : 'border-transparent hover:bg-zinc-900'}`}>
                  <span className="font-medium flex items-center gap-2"><Building2 className="w-4 h-4 text-zinc-500" />{r.name}</span>
                  <span className="block text-xs text-zinc-500 mt-0.5">
                    {r.offers_count} offer{r.offers_count === 1 ? '' : 's'} · {r.notes_count} note{r.notes_count === 1 ? '' : 's'}
                    {r.flagged_notes > 0 ? ` (${r.flagged_notes} flagged)` : ''} · {r.open_todos} to-do{r.open_todos === 1 ? '' : 's'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section>
          {error && <p role="alert" className="mb-4 px-4 py-3 rounded-xl border border-red-900 bg-red-950/40 text-red-300 text-sm">{error}</p>}
          {!company ? (
            <div className="border border-dashed border-zinc-800 rounded-xl p-12 text-center text-zinc-500">
              {selectedId ? 'Loading…' : 'Pick a company, or add one on the left.'}
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold">{company.name}</h2>
                  {saved && <p className="text-xs text-green-400 flex items-center gap-1 mt-1"><Check className="w-3 h-3" />{saved}</p>}
                </div>
                <button onClick={remove} aria-label="Delete company" title="Delete company"
                  className="p-2 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-zinc-900"><Trash2 className="w-4 h-4" /></button>
              </div>

              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
                <label className="block text-sm text-zinc-400">Website
                  <div className="flex gap-2 mt-1">
                    <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://…"
                      className={`${input} flex-1`} />
                    <button onClick={() => patch({ website })} disabled={website === (company.website || '')}
                      className="px-3 rounded-lg border border-zinc-700 text-sm disabled:opacity-40">Save</button>
                    {company.website && (
                      <a href={company.website} target="_blank" rel="noopener noreferrer" aria-label="Open website"
                        className="p-2 rounded-lg border border-zinc-700"><ExternalLink className="w-4 h-4" /></a>
                    )}
                  </div>
                </label>

                <div>
                  <p className="text-sm text-zinc-400 mb-2">Links</p>
                  <ul className="space-y-1 mb-2">
                    {company.links.map((l, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <LinkIcon className="w-4 h-4 text-zinc-500" />
                        <a href={l.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline truncate">{l.label || l.url}</a>
                        <button onClick={() => patch({ links: company.links.filter((_, j) => j !== i) }, 'Link removed')}
                          aria-label="Remove link" className="text-zinc-500 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-2 flex-wrap">
                    <input value={newLink.label} onChange={(e) => setNewLink({ ...newLink, label: e.target.value })}
                      placeholder="Label (e.g. Glassdoor)" aria-label="Link label" className={`${input} w-40`} />
                    <input value={newLink.url} onChange={(e) => setNewLink({ ...newLink, url: e.target.value })}
                      placeholder="https://…" aria-label="Link URL" className={`${input} flex-1 min-w-40`} />
                    <button onClick={async () => { await patch({ links: [...company.links, newLink] }, 'Link added'); setNewLink({ label: '', url: '' }); }}
                      disabled={!newLink.url.trim()} className="px-3 rounded-lg border border-zinc-700 text-sm disabled:opacity-40">Add link</button>
                  </div>
                </div>

              </div>

              <NotesSection company={company} reload={reloadCompany} setError={setError} input={input} />

              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                <h3 className="font-semibold mb-3">To-do</h3>
                <ul className="space-y-2 mb-3">
                  {company.todos.length === 0 && <li className="text-sm text-zinc-500">Nothing yet.</li>}
                  {company.todos.map((t) => (
                    <li key={t.id} className="flex items-center gap-3 text-sm">
                      <input type="checkbox" checked={t.done} aria-label={`Done: ${t.text}`}
                        onChange={() => todoRequest(`${API}/api/todos/${t.id}`, 'PATCH', { done: !t.done })}
                        className="w-4 h-4 accent-white" />
                      <span className={`flex-1 ${t.done ? 'line-through text-zinc-500' : ''}`}>{t.text}</span>
                      {t.due_date && <span className={`text-xs ${!t.done && t.due_date < new Date().toISOString().slice(0, 10) ? 'text-red-400' : 'text-zinc-500'}`}>{t.due_date}</span>}
                      <button onClick={() => todoRequest(`${API}/api/todos/${t.id}`, 'DELETE')} aria-label={`Delete to-do: ${t.text}`}
                        className="text-zinc-500 hover:text-red-400"><Trash2 className="w-3 h-3" /></button>
                    </li>
                  ))}
                </ul>
                <div className="flex gap-2 flex-wrap">
                  <input value={newTodo.text} onChange={(e) => setNewTodo({ ...newTodo, text: e.target.value })}
                    onKeyDown={(e) => e.key === 'Enter' && addTodo()} placeholder="e.g. Ask Sam about the team"
                    aria-label="New to-do" className={`${input} flex-1 min-w-48`} />
                  <input type="date" value={newTodo.due_date} onChange={(e) => setNewTodo({ ...newTodo, due_date: e.target.value })}
                    aria-label="Due date" className={input} />
                  <button onClick={addTodo} disabled={!newTodo.text.trim()} className="px-3 rounded-lg bg-white text-black text-sm disabled:opacity-40">Add</button>
                </div>
              </div>

              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                <h3 className="font-semibold mb-3">Offers at {company.name}</h3>
                {company.offers.length === 0 ? (
                  <p className="text-sm text-zinc-500">No saved offer has “{company.name}” as its company.</p>
                ) : (
                  <ul className="space-y-1">
                    {company.offers.map((o) => (
                      <li key={o.id}>
                        <button onClick={() => onOpenOffer(o)} className="w-full text-left px-3 py-2 rounded-lg border border-zinc-800 hover:border-zinc-600 text-sm">
                          <span className="font-medium">{o.title}</span>
                          <span className="ml-2 text-xs text-zinc-500 capitalize">{String(o.status).replace('_', ' ')}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
