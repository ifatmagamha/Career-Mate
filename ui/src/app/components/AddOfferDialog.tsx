import { useEffect, useState } from 'react';
import { API, apiFetch } from '@/app/api';
import { X, Loader } from 'lucide-react';


export interface Folder {
  id: string;
  name: string;
  count: number;
}

interface Options {
  statuses: string[];
  contract_types: string[];
  remote_policies: string[];
  seniorities: string[];
}

interface AddOfferDialogProps {
  folders: Folder[];
  defaultFolderId?: string;
  offer?: any; // set = edit this offer (posting fields only; status, folder and notes live on the sheet)
  onClose: () => void;
  onCreated: (offer: any) => void;
}

const label = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace('_', ' ');
const lines = (s: string) => s.split('\n').map((x) => x.trim()).filter(Boolean);
const commas = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

const inputClass =
  'w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50';

function Field({ id, label: text, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 min-w-0">
      <label htmlFor={id} className="text-xs text-zinc-400">{text}</label>
      {children}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3 border-t border-zinc-800 pt-4">
      <legend className="text-xs font-medium uppercase tracking-wider text-zinc-500 pr-2">{title}</legend>
      {children}
    </fieldset>
  );
}

export function AddOfferDialog({ folders, defaultFolderId, offer, onClose, onCreated }: AddOfferDialogProps) {
  const [options, setOptions] = useState<Options | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const editing = !!offer;
  const [form, setForm] = useState({
    title: offer?.title || '', company: offer?.company || '', location: offer?.location || '', url: offer?.url || '',
    contract_type: offer?.contract_type || 'unknown', remote_policy: offer?.remote_policy || 'unknown',
    seniority: offer?.seniority || 'unknown', salary: offer?.salary || '', deadline: offer?.deadline || '',
    summary: offer?.summary || '', missions: (offer?.missions || []).join('\n'), requirements: (offer?.requirements || []).join('\n'),
    skills: (offer?.skills || []).join(', '), nice_to_have: (offer?.nice_to_have || []).join(', '),
    raw_text: offer?.raw_text || '', status: 'saved', folder_id: defaultFolderId || '', notes: '',
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    apiFetch(`${API}/api/offer-options`).then((r) => r.json()).then(setOptions).catch(() => setError('Could not load form options.'));
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const fields = {
        ...form,
        missions: lines(form.missions),
        requirements: lines(form.requirements),
        skills: commas(form.skills),
        nice_to_have: commas(form.nice_to_have),
        deadline: form.deadline || null,
      };
      const { status, folder_id, notes, ...posting } = fields;
      const res = await apiFetch(editing ? `${API}/api/offers/${offer.id}` : `${API}/api/offers`, {
        method: editing ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editing ? posting : { ...fields, folder_id: folder_id || null }),
      });
      const data = await res.json();
      if (!res.ok) {
        const d = data.detail;
        setError(Array.isArray(d) ? d.map((x: any) => `${x.loc?.slice(-1)[0]}: ${String(x.msg).replace(/^Value error, /, "")}`).join(' · ') : d?.message || d || 'Could not save the offer.');
        return;
      }
      onCreated(data);
    } catch {
      setError('Error connecting to server.');
    } finally {
      setSaving(false);
    }
  };

  const select = (id: keyof typeof form, values: string[] = []) => (
    <select id={id} value={form[id]} onChange={set(id)} className={inputClass}>
      {values.map((v) => <option key={v} value={v}>{label(v)}</option>)}
    </select>
  );

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-start justify-center overflow-y-auto px-4 py-10" onMouseDown={onClose}>
      <form
        onSubmit={submit}
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-2xl bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col gap-5"
        aria-labelledby="add-offer-title"
      >
        <div className="flex items-center justify-between">
          <h2 id="add-offer-title" className="text-xl font-semibold">{editing ? 'Edit offer' : 'Add an offer'}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 text-zinc-400 hover:text-white rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <Section title="Role">
          <Field id="title" label="Job title *">
            <input id="title" required value={form.title} onChange={set('title')} className={inputClass} placeholder="Data Engineer" autoFocus />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field id="company" label="Company">
              <input id="company" value={form.company} onChange={set('company')} className={inputClass} placeholder="Doctolib" />
            </Field>
            <Field id="location" label="Location">
              <input id="location" value={form.location} onChange={set('location')} className={inputClass} placeholder="Paris" />
            </Field>
          </div>
          <Field id="url" label="Link to the posting">
            <input id="url" type="url" value={form.url} onChange={set('url')} className={inputClass} placeholder="https://..." />
          </Field>
        </Section>

        <Section title="Contract">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field id="contract_type" label="Contract">{select('contract_type', options?.contract_types)}</Field>
            <Field id="remote_policy" label="Remote">{select('remote_policy', options?.remote_policies)}</Field>
            <Field id="seniority" label="Seniority">{select('seniority', options?.seniorities)}</Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field id="salary" label="Salary">
              <input id="salary" value={form.salary} onChange={set('salary')} className={inputClass} placeholder="45–55k EUR / year" />
            </Field>
            <Field id="deadline" label="Application deadline">
              <input id="deadline" type="date" value={form.deadline} onChange={set('deadline')} className={inputClass} />
            </Field>
          </div>
        </Section>

        <Section title="Content">
          <Field id="summary" label="Summary">
            <textarea id="summary" rows={2} value={form.summary} onChange={set('summary')} className={inputClass} />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field id="missions" label="Missions (one per line)">
              <textarea id="missions" rows={4} value={form.missions} onChange={set('missions')} className={inputClass} />
            </Field>
            <Field id="requirements" label="Requirements (one per line)">
              <textarea id="requirements" rows={4} value={form.requirements} onChange={set('requirements')} className={inputClass} />
            </Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field id="skills" label="Required skills (comma separated)">
              <input id="skills" value={form.skills} onChange={set('skills')} className={inputClass} placeholder="Python, SQL, Airflow" />
            </Field>
            <Field id="nice_to_have" label="Nice-to-have skills">
              <input id="nice_to_have" value={form.nice_to_have} onChange={set('nice_to_have')} className={inputClass} placeholder="dbt, Kafka" />
            </Field>
          </div>
          <Field id="raw_text" label="Original posting text">
            <textarea id="raw_text" rows={5} value={form.raw_text} onChange={set('raw_text')} className={inputClass} placeholder="Paste the full description to keep it even if the posting disappears" />
          </Field>
        </Section>

        {!editing && <Section title="Organize">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field id="status" label="Status">{select('status', options?.statuses)}</Field>
            <Field id="folder_id" label="Folder">
              <select id="folder_id" value={form.folder_id} onChange={set('folder_id')} className={inputClass}>
                <option value="">Unfiled</option>
                {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </Field>
          </div>
          <Field id="notes" label="Notes">
            <textarea id="notes" rows={2} value={form.notes} onChange={set('notes')} className={inputClass} />
          </Field>
        </Section>}

        {error && <p className="px-3 py-2 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</p>}

        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800">Cancel</button>
          <button type="submit" disabled={saving || !options} className="px-5 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
            {saving && <Loader className="w-4 h-4 animate-spin" />}
            {editing ? 'Save changes' : 'Save offer'}
          </button>
        </div>
      </form>
    </div>
  );
}
