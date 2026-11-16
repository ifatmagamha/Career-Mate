import { useState, useEffect, useRef } from 'react';
import { API, apiFetch } from '@/app/api';
import { FileText, Mail, MessageSquare, Sparkles, Copy, RotateCw, Pencil, Save, History, Wand2, ArrowLeft } from 'lucide-react';

export type GeneratorType = 'cover-letter' | 'cold-email' | 'interview';

interface GeneratorViewProps {
  initialDescription?: string;
  initialOfferId?: string;
  initialDocType?: GeneratorType;
}

interface OfferOption { id: string; title: string; company?: string }

// One saved version of a generated document (the API returns them newest first)
interface DocVersion {
  id: string;
  doc_type: GeneratorType;
  version: number;
  content: string;
  feedback?: string | null;
  created_at: string;
}

const MAX_INSTRUCTIONS = 2000;

export function GeneratorView({ initialDescription = '', initialOfferId = '', initialDocType }: GeneratorViewProps) {
  const [activeTab, setActiveTab] = useState<GeneratorType>(initialDocType || 'cover-letter');
  const [source, setSource] = useState<'offer' | 'paste'>(initialOfferId || !initialDescription ? 'offer' : 'paste');
  const [offers, setOffers] = useState<OfferOption[]>([]);
  const [offerId, setOfferId] = useState(initialOfferId);
  const [jobDescription, setJobDescription] = useState(initialDescription);
  const [tone, setTone] = useState('professional');
  const [difficulty, setDifficulty] = useState('medium');

  const [instructions, setInstructions] = useState('');
  const [savedInstructions, setSavedInstructions] = useState('');

  const [versions, setVersions] = useState<DocVersion[]>([]);
  const [current, setCurrent] = useState<DocVersion | null>(null); // the version on screen (saved documents)
  const [unsaved, setUnsaved] = useState('');                       // result from a pasted description (not stored)
  const [feedback, setFeedback] = useState('');
  const [editText, setEditText] = useState<string | null>(null);
  const [busy, setBusy] = useState<'' | 'generate' | 'revise' | 'save'>('');
  const [error, setError] = useState('');
  const autoOpen = useRef(Boolean(initialDocType));

  useEffect(() => {
    apiFetch(`${API}/api/offers?sort=recent`).then((r) => (r.ok ? r.json() : [])).then((list) => {
      setOffers(list.map((o: any) => ({ id: o.id, title: o.title, company: o.company })));
      if (!initialOfferId && list.length === 0 && initialDescription === '') setSource('paste');
    }).catch(() => setOffers([]));
    apiFetch(`${API}/api/preferences`).then((r) => (r.ok ? r.json() : { instructions: '' })).then((p) => {
      setInstructions(p.instructions || '');
      setSavedInstructions(p.instructions || '');
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (initialDescription) setJobDescription(initialDescription);
  }, [initialDescription]);

  // Saved versions of the selected offer's document of this type
  useEffect(() => {
    setVersions([]);
    setCurrent(null);
    setUnsaved('');
    if (source !== 'offer' || !offerId) return;
    apiFetch(`${API}/api/offers/${offerId}/documents?type=${activeTab}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: DocVersion[]) => {
        setVersions(list);
        if (autoOpen.current && list.length) setCurrent(list[0]); // opened from the offer page: show the latest
        autoOpen.current = false;
      })
      .catch(() => setVersions([]));
  }, [offerId, activeTab, source]);

  const tabs = [
    { id: 'cover-letter' as GeneratorType, label: 'AI Cover Letter', icon: <FileText className="w-4 h-4" /> },
    { id: 'cold-email' as GeneratorType, label: 'AI Cold Email', icon: <Mail className="w-4 h-4" /> },
    { id: 'interview' as GeneratorType, label: 'AI Interview Prep', icon: <MessageSquare className="w-4 h-4" /> }
  ];
  const tones = ['professional', 'enthusiastic', 'creative', 'formal'];
  const difficulties = ['easy', 'medium', 'hard'];
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

  const readError = async (res: Response) => {
    const body = await res.json().catch(() => ({}));
    return typeof body.detail === 'string' ? body.detail : `Request failed (HTTP ${res.status})`;
  };

  const saveInstructions = async () => {
    setError('');
    const res = await apiFetch(`${API}/api/preferences`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instructions }),
    }).catch(() => null);
    if (!res) return setError('Error connecting to server.');
    if (!res.ok) return setError(await readError(res));
    const p = await res.json();
    setInstructions(p.instructions);
    setSavedInstructions(p.instructions);
  };

  const handleGenerate = async () => {
    const fromOffer = source === 'offer';
    if (fromOffer ? !offerId : !jobDescription.trim()) return;
    setBusy('generate');
    setError('');
    try {
      const res = await apiFetch(`${API}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: activeTab,
          ...(fromOffer ? { offer_id: offerId } : { job_description: jobDescription }),
          extra: activeTab === 'interview' ? difficulty : tone,
          instructions,
        }),
      });
      if (!res.ok) return setError(await readError(res));
      const data = await res.json();
      if (data.document) {
        setVersions((v) => [data.document, ...v]);
        setCurrent(data.document);
      } else {
        setUnsaved(data.content);
      }
    } catch {
      setError('Error contacting the AI agent.');
    } finally {
      setBusy('');
    }
  };

  // New version from the current one: AI rewrite with feedback, or your own edit
  const saveVersion = async (body: { feedback?: string; content?: string }) => {
    if (!current) return;
    setBusy(body.feedback ? 'revise' : 'save');
    setError('');
    try {
      const res = await apiFetch(`${API}/api/documents/${current.id}/revise`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!res.ok) return setError(await readError(res));
      const doc: DocVersion = await res.json();
      setVersions((v) => [doc, ...v]);
      setCurrent(doc);
      setFeedback('');
      setEditText(null);
    } catch {
      setError('Error connecting to server.');
    } finally {
      setBusy('');
    }
  };

  const shown = current?.content ?? unsaved;
  const backToSettings = () => { setCurrent(null); setUnsaved(''); setEditText(null); setError(''); };
  const offerLabel = (o: OfferOption) => `${o.title}${o.company ? ` · ${o.company}` : ''}`;
  const errorBox = error && (
    <div role="alert" className="px-4 py-3 rounded-xl border border-red-900 bg-red-950/40 text-red-300 text-sm">{error}</div>
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex gap-2 mb-8 border-b border-zinc-800 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => { setActiveTab(tab.id); setEditText(null); setError(''); }}
            className={`flex items-center gap-2 px-6 py-3 rounded-t-lg transition-all whitespace-nowrap ${activeTab === tab.id ? 'bg-white text-black font-medium' : 'text-zinc-400 hover:text-white hover:bg-zinc-900'}`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {!shown ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 space-y-6">
          <div>
            <div className="flex items-center justify-between mb-3 gap-4 flex-wrap">
              <label className="text-white font-medium">1. Which job?</label>
              <div className="flex rounded-lg border border-zinc-700 overflow-hidden text-sm">
                {(['offer', 'paste'] as const).map((s) => (
                  <button key={s} onClick={() => setSource(s)}
                    className={`px-3 py-1.5 ${source === s ? 'bg-white text-black' : 'text-zinc-400 hover:text-white'}`}>
                    {s === 'offer' ? 'A saved offer' : 'Paste a description'}
                  </button>
                ))}
              </div>
            </div>
            {source === 'offer' ? (
              offers.length === 0 ? (
                <p className="text-sm text-zinc-500">No saved offers yet: capture one in the Job Explorer, or paste a description.</p>
              ) : (
                <>
                  <select value={offerId} onChange={(e) => setOfferId(e.target.value)} aria-label="Saved offer"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-zinc-600">
                    <option value="">Choose an offer…</option>
                    {offers.map((o) => <option key={o.id} value={o.id}>{offerLabel(o)}</option>)}
                  </select>
                  <p className="text-xs text-zinc-500 mt-2">The result is saved on the offer, and every revision becomes a new version.</p>
                </>
              )
            ) : (
              <>
                <textarea value={jobDescription} onChange={(e) => setJobDescription(e.target.value)}
                  placeholder="Paste the job description here..." aria-label="Job description"
                  className="w-full h-48 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 resize-none" />
                <p className="text-xs text-zinc-500 mt-2">Results from a pasted description are not saved.</p>
              </>
            )}
          </div>

          <div>
            <label className="block text-white font-medium mb-3">
              2. {activeTab === 'interview' ? 'Select difficulty level.' : 'Select your tone.'}
            </label>
            <select
              value={activeTab === 'interview' ? difficulty : tone}
              onChange={(e) => (activeTab === 'interview' ? setDifficulty : setTone)(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-zinc-600"
            >
              {(activeTab === 'interview' ? difficulties : tones).map((v) => <option key={v} value={v}>{cap(v)}</option>)}
            </select>
          </div>

          <div>
            <label htmlFor="instructions" className="block text-white font-medium mb-1">3. Your personal instructions</label>
            <p className="text-sm text-zinc-500 mb-3">
              Applied to every document: language, length, what to highlight, how to sign… They never make the AI invent experience.
            </p>
            <textarea id="instructions" value={instructions} maxLength={MAX_INSTRUCTIONS}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. Write in French. Keep it under 250 words. Highlight my data pipeline projects. Sign as Fatma G."
              className="w-full h-28 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 resize-y" />
            <div className="flex items-center justify-between mt-2 text-xs text-zinc-500">
              <span>{instructions.length}/{MAX_INSTRUCTIONS}{instructions !== savedInstructions ? ' · unsaved: used for this generation only' : ''}</span>
              <button onClick={saveInstructions} disabled={instructions === savedInstructions}
                className="px-3 py-1.5 rounded-lg border border-zinc-700 text-zinc-300 hover:text-white disabled:opacity-40">
                Save as my default
              </button>
            </div>
          </div>

          {versions.length > 0 && (
            <div className="border border-zinc-800 rounded-xl p-4">
              <p className="text-sm text-zinc-400 mb-2 flex items-center gap-2"><History className="w-4 h-4" />Saved for this offer</p>
              <div className="flex flex-wrap gap-2">
                {versions.map((v) => (
                  <button key={v.id} onClick={() => setCurrent(v)}
                    className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 border border-zinc-700 hover:border-zinc-500">
                    v{v.version} · {new Date(v.created_at).toLocaleDateString()}
                  </button>
                ))}
              </div>
            </div>
          )}

          {errorBox}

          <button
            onClick={handleGenerate}
            disabled={busy !== '' || (source === 'offer' ? !offerId : !jobDescription.trim())}
            className="w-full py-4 bg-white text-black rounded-xl font-semibold hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {busy === 'generate' ? <RotateCw className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            <span>{busy === 'generate' ? 'Generating...' : versions.length ? 'Generate a new draft' : 'Generate'}</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <button onClick={backToSettings} aria-label="Back to settings"
                className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-600"><ArrowLeft className="w-4 h-4" /></button>
              <h2 className="text-2xl font-bold">
                {current ? `Version ${current.version}` : 'Generated Result'}
              </h2>
            </div>
            <div className="flex gap-3">
              <button onClick={() => navigator.clipboard.writeText(editText ?? shown)}
                className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-2"><Copy className="w-4 h-4" />Copy</button>
              {current && (editText === null ? (
                <button onClick={() => setEditText(current.content)}
                  className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-2"><Pencil className="w-4 h-4" />Edit</button>
              ) : (
                <button onClick={() => saveVersion({ content: editText })} disabled={busy !== '' || !editText.trim() || editText === current.content}
                  className="px-4 py-2 bg-white text-black rounded-lg flex items-center gap-2 disabled:opacity-50"><Save className="w-4 h-4" />Save as new version</button>
              ))}
            </div>
          </div>

          {current?.feedback && <p className="text-sm text-zinc-400">Changes asked for this version: “{current.feedback}”</p>}
          {!current && <p className="text-sm text-zinc-500">Generated from a pasted description: not saved. Pick a saved offer to keep versions and iterate.</p>}

          <div className="grid gap-6 md:grid-cols-[1fr_220px]">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              {editText === null ? (
                <div className="bg-white text-black rounded-lg p-8 font-sans overflow-auto max-h-[600px]">
                  <pre className="whitespace-pre-wrap font-sans">{shown}</pre>
                </div>
              ) : (
                <textarea value={editText} onChange={(e) => setEditText(e.target.value)} aria-label="Edit document"
                  className="w-full min-h-[480px] bg-white text-black rounded-lg p-6 font-sans focus:outline-none" />
              )}
            </div>

            {current && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-400 flex items-center gap-2"><History className="w-4 h-4" />Versions</p>
                {versions.map((v) => (
                  <button key={v.id} onClick={() => { setCurrent(v); setEditText(null); }}
                    className={`w-full text-left px-3 py-2 rounded-lg border text-sm ${v.id === current.id ? 'border-white bg-zinc-800' : 'border-zinc-800 hover:border-zinc-600'}`}>
                    <span className="font-medium">v{v.version}</span>
                    <span className="block text-xs text-zinc-500 truncate">{v.feedback || 'First draft'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {current && editText === null && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-3">
              <label htmlFor="feedback" className="block text-white font-medium">What should change?</label>
              <textarea id="feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)} maxLength={2000}
                placeholder="e.g. Shorter, more confident opening, mention my dbt project, remove the second paragraph."
                className="w-full h-24 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 resize-y" />
              {errorBox}
              <button onClick={() => saveVersion({ feedback })} disabled={busy !== '' || !feedback.trim()}
                className="w-full py-3 bg-white text-black rounded-xl font-semibold hover:bg-zinc-200 disabled:opacity-50 flex items-center justify-center gap-2">
                {busy === 'revise' ? <RotateCw className="w-5 h-5 animate-spin" /> : <Wand2 className="w-5 h-5" />}
                {busy === 'revise' ? 'Revising...' : `Revise version ${current.version}`}
              </button>
            </div>
          )}
          {(!current || editText !== null) && errorBox}
        </div>
      )}
    </div>
  );
}
