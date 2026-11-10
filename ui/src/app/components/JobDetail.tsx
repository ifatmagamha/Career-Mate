import { useEffect, useState } from 'react';
import { API, apiFetch } from '@/app/api';
import {
  ArrowLeft, MapPin, DollarSign, Briefcase, Calendar, Building2, CheckCircle2, ExternalLink, Laptop, TrendingUp,
  StickyNote, Users, Plus, Trash2, FileText, Pencil,
} from 'lucide-react';
import { AddOfferDialog } from '@/app/components/AddOfferDialog';
import type { GeneratorType } from '@/app/components/GeneratorView';

const DOC_LABELS: Record<GeneratorType, string> = {
  'cover-letter': 'Cover letter', 'cold-email': 'Cold email', 'interview': 'Interview prep',
};

// Documents generated for this offer: latest version of each type, opened in the AI Generator to iterate
function DocumentsPanel({ offerId, onOpen }: { offerId: string; onOpen: (docType: GeneratorType) => void }) {
  const [docs, setDocs] = useState<{ doc_type: GeneratorType; version: number; created_at: string }[] | null>(null);

  useEffect(() => {
    apiFetch(`${API}/api/offers/${offerId}/documents`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setDocs)
      .catch(() => setDocs([]));
  }, [offerId]);

  // The API lists newest first per type: the first row of each type is its latest version
  const latest = (docs || []).filter((d, i, all) => all.findIndex((x) => x.doc_type === d.doc_type) === i);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-1 flex items-center gap-2"><FileText className="w-4 h-4" />Documents</h2>
      {docs === null ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : latest.length === 0 ? (
        <p className="text-sm text-zinc-500">No documents yet. Use “Generate Cover Letter” to write one for this offer.</p>
      ) : (
        <ul className="space-y-2 mt-3">
          {latest.map((d) => (
            <li key={d.doc_type}>
              <button onClick={() => onOpen(d.doc_type)}
                className="w-full text-left px-3 py-2 rounded-lg border border-zinc-800 hover:border-zinc-600">
                <span className="font-medium">{DOC_LABELS[d.doc_type] ?? d.doc_type}</span>
                <span className="block text-xs text-zinc-500">
                  v{d.version} · {new Date(d.created_at).toLocaleDateString()} · open to revise
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const label = (s?: string) => (s && s !== 'unknown' ? (s.charAt(0).toUpperCase() + s.slice(1)).replace('_', ' ') : 'Not specified');

interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  type: string;
  matchScore: number;
  description: string;
  requirements: string[];
  postedDate: string;
  url?: string;
  deadline?: string;
  missions?: string[];
  summary?: string;
  tags?: string[];
  status?: string;
  applicationId?: string;
  notes?: string;
  rawText?: string;
  remotePolicy?: string;
  seniority?: string;
  niceToHave?: string[];
}

interface Contact {
  id: string;
  name: string;
  role?: string;
  linkedin_url?: string;
  notes?: string;
  reached_out: boolean;
  reached_at?: string;
}

interface JobDetailProps {
  job: Job | null;
  onBack: () => void;
  onGenerateCoverLetter: (description: string, offerId?: string, docType?: GeneratorType) => void;
  onUpdated?: (offer: any) => void;
}

export function JobDetail({ job, onBack, onGenerateCoverLetter, onUpdated }: JobDetailProps) {
  const [status, setStatus] = useState(job?.status);
  const [editing, setEditing] = useState<any>(null); // raw offer being edited

  // Captured offers are already in the tracker: only their stage changes
  const handleAction = async (stage: 'applied') => {
    if (!job?.applicationId) return;

    try {
      const res = await apiFetch(`${API}/api/applications/${job.applicationId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage })
      });

      if (res.ok) {
        setStatus(stage);
      } else {
        alert('Failed to process action.');
      }
    } catch (e) {
      console.error(e);
      alert('Error connecting to server.');
    }
  };

  if (!job) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <p className="text-zinc-400">No job selected</p>
      </div>
    );
  }

  const getMatchColor = (score: number) => {
    if (score >= 90) return 'from-green-500 to-emerald-500';
    if (score >= 80) return 'from-blue-500 to-cyan-500';
    if (score >= 70) return 'from-yellow-500 to-orange-500';
    return 'from-zinc-500 to-zinc-600';
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Back Button */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-zinc-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        <span>Back to Jobs</span>
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header Card */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="flex-1 min-w-0">
                <h1 className="text-3xl font-bold mb-2">{job.title}</h1>
                <div className="flex items-center gap-2 text-xl text-zinc-400">
                  <Building2 className="w-5 h-5" />
                  <span>{job.company}</span>
                </div>
              </div>
              <button
                onClick={async () => {
                  const res = await apiFetch(`${API}/api/offers/${job.id}`).catch(() => null);
                  if (res?.ok) setEditing(await res.json());
                }}
                className="shrink-0 px-3 py-2 rounded-lg text-sm text-zinc-300 bg-zinc-800 hover:bg-zinc-700 flex items-center gap-2"
              >
                <Pencil className="w-4 h-4" />Edit
              </button>
              {job.matchScore > 0 && (
                <div className={`px-4 py-2 rounded-xl bg-gradient-to-r ${getMatchColor(job.matchScore)} text-white font-semibold`}>
                  {job.matchScore}% Match
                </div>
              )}
            </div>

            {/* Quick Info */}
            <div className="grid grid-cols-2 gap-4 mt-6">
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                  <MapPin className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-600">Location</p>
                  <p className="text-white">{job.location}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                  <DollarSign className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-600">Salary</p>
                  <p className="text-white">{job.salary}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                  <Briefcase className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-600">Type</p>
                  <p className="text-white">{job.type}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-600">Deadline</p>
                  <p className="text-white">{job.deadline || 'Not specified'}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                  <Laptop className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-600">Remote</p>
                  <p className="text-white">{label(job.remotePolicy)}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-zinc-600">Seniority</p>
                  <p className="text-white">{label(job.seniority)}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Summary */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4">Summary</h2>
            <p className="text-zinc-400 leading-relaxed">{job.summary || job.description}</p>
          </div>

          {/* Missions */}
          {(job.missions || []).length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <h2 className="text-xl font-semibold mb-4">Missions</h2>
              <ul className="space-y-2 list-disc list-inside text-zinc-400">
                {(job.missions || []).map((m, idx) => <li key={idx}>{m}</li>)}
              </ul>
            </div>
          )}

          {/* Requirements */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4">Requirements</h2>
            <div className="space-y-3">
              {job.requirements.map((req, idx) => (
                <div key={idx} className="flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-zinc-400">{req}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Skills */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4">Key Skills</h2>
            <div className="flex flex-wrap gap-3">
              {(job.tags || []).map((skill, idx) => (
                <span
                  key={idx}
                  className="px-4 py-2 bg-zinc-800 rounded-lg text-zinc-300"
                >
                  {skill}
                </span>
              ))}
            </div>
            {(job.niceToHave || []).length > 0 && (
              <>
                <h3 className="text-sm font-medium text-zinc-500 mt-5 mb-3">Nice to have</h3>
                <div className="flex flex-wrap gap-2">
                  {(job.niceToHave || []).map((skill, idx) => (
                    <span key={idx} className="px-3 py-1.5 border border-zinc-800 rounded-lg text-sm text-zinc-400">{skill}</span>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Original posting text, kept even if the posting disappears */}
          {job.rawText && (
            <details className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 group">
              <summary className="text-xl font-semibold cursor-pointer flex items-center gap-2 list-none">
                <FileText className="w-5 h-5 text-zinc-500" />
                Original posting text
                <span className="ml-auto text-sm font-normal text-zinc-500 group-open:hidden">Show</span>
                <span className="ml-auto text-sm font-normal text-zinc-500 hidden group-open:inline">Hide</span>
              </summary>
              <p className="mt-4 text-sm text-zinc-400 leading-relaxed whitespace-pre-wrap break-words">{job.rawText}</p>
            </details>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-1">Quick Actions</h2>
            <p className="text-sm text-zinc-500 mb-4 capitalize">Status: {status}</p>
            <div className="space-y-3">
              <button
                onClick={() => handleAction('applied')}
                disabled={status === 'applied'}
                className="w-full py-3 bg-white text-black rounded-lg font-medium hover:bg-zinc-200 transition-colors disabled:opacity-50"
              >
                {status === 'applied' ? 'Applied' : 'Mark as Applied'}
              </button>
              <button
                onClick={() => onGenerateCoverLetter(job.description, job.id)}
                className="w-full py-3 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700 transition-colors"
              >
                Generate Cover Letter
              </button>
              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-3 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700 transition-colors flex items-center justify-center gap-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  Original Posting
                </a>
              )}
            </div>
          </div>

          <DocumentsPanel offerId={job.id} onOpen={(docType) => onGenerateCoverLetter(job.description, job.id, docType)} />
          {job.applicationId && <OfferNotes applicationId={job.applicationId} initial={job.notes || ''} />}
          {job.applicationId && <ContactsPanel applicationId={job.applicationId} />}
        </div>
      </div>

      {editing && (
        <AddOfferDialog
          folders={[]}
          offer={editing}
          onClose={() => setEditing(null)}
          onCreated={(offer) => {
            setEditing(null);
            onUpdated?.(offer);
          }}
        />
      )}
    </div>
  );
}

const fieldClass =
  'w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50';

function OfferNotes({ applicationId, initial }: { applicationId: string; initial: string }) {
  const [notes, setNotes] = useState(initial);
  const [saved, setSaved] = useState(initial);
  const [state, setState] = useState<'idle' | 'saving' | 'error'>('idle');

  const save = async () => {
    if (notes === saved) return;
    setState('saving');
    const res = await apiFetch(`${API}/api/applications/${applicationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    }).catch(() => null);
    if (res?.ok) {
      setSaved(notes);
      setState('idle');
    } else {
      setState('error');
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-3 flex items-center gap-2"><StickyNote className="w-4 h-4 text-zinc-500" />Notes</h2>
      <label htmlFor="offer-notes" className="sr-only">Notes on this offer</label>
      <textarea
        id="offer-notes"
        rows={5}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        onBlur={save}
        placeholder="Anything about this offer: impressions, questions to ask, follow-ups…"
        className={fieldClass}
      />
      <p className="mt-2 text-xs text-zinc-500" aria-live="polite">
        {state === 'saving' ? 'Saving…' : state === 'error' ? 'Not saved: the server did not answer.' : notes === saved ? (saved ? 'Saved' : '') : 'Saves when you click outside'}
      </p>
    </div>
  );
}

function ContactsPanel({ applicationId }: { applicationId: string }) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ name: '', role: '', linkedin_url: '', notes: '' });
  const [error, setError] = useState('');

  const load = () =>
    apiFetch(`${API}/api/applications/${applicationId}/contacts`).then((r) => r.json()).then(setContacts).catch(() => {});

  useEffect(() => {
    load();
  }, [applicationId]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const res = await apiFetch(`${API}/api/applications/${applicationId}/contacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...draft, linkedin_url: draft.linkedin_url || null }),
    });
    if (!res.ok) {
      const d = (await res.json().catch(() => ({}))).detail;
      setError(Array.isArray(d) ? d.map((x: any) => `${x.loc?.slice(-1)[0]}: ${String(x.msg).replace(/^Value error, /, "")}`).join(' · ') : d || 'Could not add the contact.');
      return;
    }
    setDraft({ name: '', role: '', linkedin_url: '', notes: '' });
    setAdding(false);
    load();
  };

  const toggle = async (c: Contact) => {
    setContacts(contacts.map((x) => (x.id === c.id ? { ...x, reached_out: !c.reached_out } : x)));
    await apiFetch(`${API}/api/contacts/${c.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reached_out: !c.reached_out }),
    });
    load();
  };

  const remove = async (c: Contact) => {
    if (!window.confirm(`Remove ${c.name} from this offer?`)) return;
    await apiFetch(`${API}/api/contacts/${c.id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
        <Users className="w-4 h-4 text-zinc-500" />People to reach
        <span className="ml-auto text-xs font-normal text-zinc-500 tabular-nums">
          {contacts.filter((c) => c.reached_out).length}/{contacts.length} reached
        </span>
      </h2>

      <ul className="flex flex-col gap-3">
        {contacts.map((c) => (
          <li key={c.id} className="flex gap-3 items-start border-b border-zinc-800 pb-3 last:border-0">
            <input
              type="checkbox"
              id={`reached-${c.id}`}
              checked={c.reached_out}
              onChange={() => toggle(c)}
              className="mt-1 accent-blue-500"
              aria-label={`Reached out to ${c.name}`}
            />
            <div className="flex-1 min-w-0">
              <label htmlFor={`reached-${c.id}`} className={`text-sm font-medium ${c.reached_out ? 'text-zinc-500 line-through' : 'text-white'}`}>
                {c.name}
              </label>
              {c.role && <p className="text-xs text-zinc-400">{c.role}</p>}
              {c.linkedin_url && (
                <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:underline inline-flex items-center gap-1">
                  LinkedIn <ExternalLink className="w-3 h-3" />
                </a>
              )}
              {c.notes && <p className="mt-1 text-xs text-zinc-500 whitespace-pre-wrap break-words">{c.notes}</p>}
              {c.reached_out && c.reached_at && <p className="mt-1 text-[11px] text-zinc-600">Reached {c.reached_at.slice(0, 10)}</p>}
            </div>
            <button onClick={() => remove(c)} aria-label={`Remove ${c.name}`} className="p-1 text-zinc-600 hover:text-red-400 rounded">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </li>
        ))}
      </ul>

      {adding ? (
        <form onSubmit={add} className="mt-3 flex flex-col gap-2">
          <label htmlFor="contact-name" className="sr-only">Name</label>
          <input id="contact-name" required autoFocus placeholder="Name *" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className={fieldClass} />
          <label htmlFor="contact-role" className="sr-only">Role</label>
          <input id="contact-role" placeholder="Role (recruiter, team lead…)" value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} className={fieldClass} />
          <label htmlFor="contact-linkedin" className="sr-only">LinkedIn</label>
          <input id="contact-linkedin" type="url" placeholder="https://linkedin.com/in/…" value={draft.linkedin_url} onChange={(e) => setDraft({ ...draft, linkedin_url: e.target.value })} className={fieldClass} />
          <label htmlFor="contact-notes" className="sr-only">Notes</label>
          <textarea id="contact-notes" rows={2} placeholder="Notes (how you know them, what to ask…)" value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} className={fieldClass} />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setAdding(false)} className="px-3 py-1.5 text-sm text-zinc-400 hover:text-white rounded-lg">Cancel</button>
            <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 rounded-lg">Add person</button>
          </div>
        </form>
      ) : (
        <button onClick={() => setAdding(true)} className="mt-3 w-full py-2 text-sm text-zinc-300 bg-zinc-800 hover:bg-zinc-700 rounded-lg flex items-center justify-center gap-2">
          <Plus className="w-4 h-4" />Add a person
        </button>
      )}
    </div>
  );
}
