import { useState, useEffect, useRef } from 'react';
import { API } from '@/app/api';
import {
  Link2, MapPin, Briefcase, Calendar, Sparkles, Loader, ClipboardPaste, Plus, FolderPlus,
  Folder as FolderIcon, Inbox, Layers, Trash2, StickyNote, Users, Pencil, Search, LayoutGrid,
  Table as TableIcon, Columns3, Bookmark, Check,
} from 'lucide-react';
import { AddOfferDialog, Folder } from '@/app/components/AddOfferDialog';


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
  benefits: string[];
  postedDate: string;
  tags: string[];
  url?: string;
  deadline?: string;
  missions?: string[];
  summary?: string;
  status?: string;
  source?: string;
  applicationId?: string;
  folderId?: string | null;
  notes?: string;
  rawText?: string;
  contactsCount?: number;
  remotePolicy?: string;
  seniority?: string;
  niceToHave?: string[];
}

interface JobExplorerProps {
  onJobSelect: (job: Job) => void;
}

interface Filters {
  q: string;
  status: string;
  contract_type: string;
  remote_policy: string;
  sort: string;
}

interface SavedView {
  id: string;
  name: string;
  filters: any;
  layout: Layout;
}

interface Options {
  statuses: string[];
  contract_types: string[];
  remote_policies: string[];
  seniorities: string[];
}

type Layout = 'grid' | 'table' | 'board';
// 'all' | 'unfiled' | folder id
type Scope = string;

const EMPTY_FILTERS: Filters = { q: '', status: '', contract_type: '', remote_policy: '', sort: '' };

const CONTRACT_LABELS: Record<string, string> = {
  permanent: 'Permanent (CDI)',
  fixed_term: 'Fixed-term (CDD)',
  internship: 'Internship',
  apprenticeship: 'Apprenticeship',
  freelance: 'Freelance',
  part_time: 'Part-time',
  unknown: 'Not specified',
};

const label = (s?: string) => (s ? (s.charAt(0).toUpperCase() + s.slice(1)).replace('_', ' ') : '');

// Backend offer row -> UI job
export const toJob = (o: any): Job => ({
  id: o.id,
  title: o.title || 'Untitled',
  company: o.company || 'Unknown',
  location: o.location || 'Not specified',
  salary: o.salary || 'Not specified',
  type: CONTRACT_LABELS[o.contract_type] || CONTRACT_LABELS.unknown,
  matchScore: o.match_score || 0,
  description: o.raw_text || o.summary || '',
  summary: o.summary || '',
  requirements: o.requirements || [],
  missions: o.missions || [],
  benefits: [],
  postedDate: (o.created_at || '').slice(0, 10),
  tags: o.skills || [],
  url: o.url || undefined,
  deadline: o.deadline || undefined,
  status: o.status,
  source: o.source,
  applicationId: o.application_id,
  folderId: o.folder_id,
  notes: o.notes || '',
  rawText: o.raw_text || '',
  contactsCount: o.contacts_count || 0,
  remotePolicy: o.remote_policy || 'unknown',
  seniority: o.seniority || 'unknown',
  niceToHave: o.nice_to_have || [],
});

// UI filters <-> API / saved-view filters (lists on the API side)
const toApiFilters = (f: Filters, scope: Scope) => {
  const out: any = {};
  if (f.q.trim()) out.q = f.q.trim();
  for (const k of ['status', 'contract_type', 'remote_policy'] as const) if (f[k]) out[k] = [f[k]];
  if (f.sort) out.sort = f.sort;
  if (scope !== 'all') out.folder = scope;
  return out;
};

const fromApiFilters = (v: any): [Filters, Scope] => [
  {
    q: v.q || '',
    status: v.status?.[0] || '',
    contract_type: v.contract_type?.[0] || '',
    remote_policy: v.remote_policy?.[0] || '',
    sort: v.sort || '',
  },
  v.folder || 'all',
];

const selectClass =
  'bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-2 text-sm text-zinc-300 focus:outline-none focus:border-blue-500/50 min-w-0';

export function JobExplorer({ onJobSelect }: JobExplorerProps) {
  const [url, setUrl] = useState('');
  const [pastedText, setPastedText] = useState('');
  const [pasteMode, setPasteMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [facets, setFacets] = useState<{ total: number; unfiled: number; skills: { name: string; count: number }[] }>({ total: 0, unfiled: 0, skills: [] });
  const [options, setOptions] = useState<Options | null>(null);
  const [views, setViews] = useState<SavedView[]>([]);
  const [activeView, setActiveView] = useState<SavedView | null>(null);
  const [scope, setScope] = useState<Scope>('all');
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [layout, setLayout] = useState<Layout>('grid');
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [newFolder, setNewFolder] = useState('');
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null);
  const [savingView, setSavingView] = useState<string | null>(null); // name being typed
  const [showAdd, setShowAdd] = useState(false);
  const [searchMode, setSearchMode] = useState('');
  const requestId = useRef(0);

  const fetchOffers = async () => {
    const id = ++requestId.current;
    const params = new URLSearchParams();
    const api = toApiFilters(filters, scope);
    for (const [k, v] of Object.entries(api)) {
      (Array.isArray(v) ? v : [v]).forEach((x) => params.append(k, String(x)));
    }
    try {
      const res = await fetch(`${API}/api/offers?${params}`);
      const data = await res.json();
      if (id === requestId.current) { // ignore out-of-order answers
        setJobs(data.map(toJob));
        setSearchMode(res.headers.get('X-Search-Mode') || '');
      }
    } catch (e) {
      console.error('Failed to load offers', e);
    }
  };

  const fetchSidebar = async () => {
    try {
      const [f, fc, v] = await Promise.all([
        fetch(`${API}/api/folders`).then((r) => r.json()),
        fetch(`${API}/api/offer-facets`).then((r) => r.json()),
        fetch(`${API}/api/views`).then((r) => r.json()),
      ]);
      setFolders(f);
      setFacets(fc);
      setViews(v);
    } catch (e) {
      console.error('Failed to load sidebar', e);
    }
  };

  const refresh = () => Promise.all([fetchOffers(), fetchSidebar()]);

  // Re-query when filters change; wait for a pause in typing before searching
  useEffect(() => {
    const t = setTimeout(fetchOffers, filters.q ? 250 : 0);
    return () => clearTimeout(t);
  }, [filters, scope]);

  useEffect(() => {
    fetchSidebar();
    fetch(`${API}/api/offer-options`).then((r) => r.json()).then(setOptions).catch(() => {});
  }, []);

  const capture = async () => {
    const text = pasteMode ? pastedText.trim() : '';
    if (!url.trim() && !text) return;
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API}/api/offers/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() || null, text: text || null }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Capture failed');
        // Protected page (LinkedIn, WTTJ...): offer the paste fallback
        if (res.status === 422) setPasteMode(true);
        return;
      }
      setUrl('');
      setPastedText('');
      setPasteMode(false);
      // Captured from inside a folder: file it there
      if (scope !== 'all' && scope !== 'unfiled' && !data.duplicate) {
        await patchApplication(data.offer.application_id, { folder_id: scope });
      }
      await refresh();
      onJobSelect(toJob(data.offer));
    } catch (e) {
      console.error('Capture failed', e);
      setError('Error connecting to server.');
    } finally {
      setLoading(false);
    }
  };

  const patchApplication = async (applicationId: string, body: object) => {
    const res = await fetch(`${API}/api/applications/${applicationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) setError('Could not update the offer.');
  };

  // Drop targets: a folder in the sidebar (files it) or a Board column (changes its status)
  const dropOn = (key: string, onDrop: (applicationId: string) => Promise<void>) => ({
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      setDropTarget(key);
    },
    onDragLeave: () => setDropTarget(null),
    onDrop: async (e: React.DragEvent) => {
      e.preventDefault();
      setDropTarget(null);
      const applicationId = e.dataTransfer.getData('text/plain');
      if (!applicationId) return;
      await onDrop(applicationId);
      await refresh();
    },
  });

  const dragProps = (job: Job) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      e.dataTransfer.setData('text/plain', job.applicationId || '');
      e.dataTransfer.effectAllowed = 'move';
    },
  });

  const createFolder = async () => {
    const name = newFolder.trim();
    if (!name) return;
    const res = await fetch(`${API}/api/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(typeof data.detail === 'string' ? data.detail : 'Could not create the folder.');
      return;
    }
    setNewFolder('');
    setError('');
    await fetchSidebar();
    setScope(data.id);
  };

  const renameFolder = async () => {
    if (!renaming) return;
    const res = await fetch(`${API}/api/folders/${renaming.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: renaming.name }),
    });
    if (!res.ok) {
      const d = (await res.json().catch(() => ({}))).detail;
      setError(typeof d === 'string' ? d : 'Could not rename the folder.');
      return;
    }
    setRenaming(null);
    setError('');
    fetchSidebar();
  };

  const deleteFolder = async (folder: Folder) => {
    if (!window.confirm(`Delete the folder "${folder.name}"? Its ${folder.count} offer(s) become unfiled; nothing else is deleted.`)) return;
    await fetch(`${API}/api/folders/${folder.id}`, { method: 'DELETE' });
    if (scope === folder.id) setScope('all');
    await refresh();
  };

  const applyView = (v: SavedView) => {
    const [f, s] = fromApiFilters(v.filters);
    setFilters(f);
    setScope(s);
    setLayout(v.layout);
    setActiveView(v);
  };

  const saveView = async (asNew: boolean) => {
    const name = asNew ? (savingView || '').trim() : activeView?.name;
    if (!name) return;
    const res = await fetch(asNew ? `${API}/api/views` : `${API}/api/views/${activeView!.id}`, {
      method: asNew ? 'POST' : 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, filters: toApiFilters(filters, scope), layout }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(typeof data.detail === 'string' ? data.detail : 'Could not save the view.');
      return;
    }
    setSavingView(null);
    setError('');
    setActiveView(data);
    fetchSidebar();
  };

  const deleteView = async (v: SavedView) => {
    if (!window.confirm(`Delete the view "${v.name}"? Offers are not affected.`)) return;
    await fetch(`${API}/api/views/${v.id}`, { method: 'DELETE' });
    if (activeView?.id === v.id) setActiveView(null);
    fetchSidebar();
  };

  const setFilter = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch });
  const goScope = (s: Scope) => {
    setScope(s);
    setActiveView(null);
  };
  const filtersActive = JSON.stringify(filters) !== JSON.stringify(EMPTY_FILTERS);
  const folderName = (id?: string | null) => folders.find((f) => f.id === id)?.name;
  const scopeName = activeView ? activeView.name
    : scope === 'all' ? 'All offers' : scope === 'unfiled' ? 'Unfiled' : folderName(scope) || '';
  const viewDirty = activeView && JSON.stringify([toApiFilters(filters, scope), layout]) !== JSON.stringify([activeView.filters, activeView.layout]);

  const scopeButton = (target: Scope, icon: React.ReactNode, name: string, count: number) => (
    <button
      onClick={() => goScope(target)}
      {...(target === 'all' ? {} : dropOn(`folder:${target}`, (id) => patchApplication(id, { folder_id: target === 'unfiled' ? null : target })))}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors ${
        dropTarget === `folder:${target}`
          ? 'bg-blue-600/20 ring-1 ring-blue-500 text-white'
          : scope === target && !activeView
            ? 'bg-zinc-800 text-white'
            : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
      }`}
    >
      {icon}
      <span className="flex-1 truncate">{name}</span>
      <span className="text-xs text-zinc-500 tabular-nums">{count}</span>
    </button>
  );

  const OfferCard = ({ job, compact = false }: { job: Job; compact?: boolean }) => (
    <div
      {...dragProps(job)}
      onClick={() => onJobSelect(job)}
      className={`bg-zinc-900 border border-zinc-800 rounded-xl ${compact ? 'p-3' : 'p-5'} hover:border-blue-500/30 hover:bg-zinc-800/50 transition-all cursor-pointer active:cursor-grabbing group`}
    >
      {!compact && (
        <div className="flex items-center justify-between gap-2 mb-4">
          <span className="px-3 py-1 rounded-full border border-zinc-700 text-xs text-zinc-400">{label(job.status)}</span>
          {folderName(job.folderId) ? (
            <span className="flex items-center gap-1 text-xs text-zinc-500 truncate">
              <FolderIcon className="w-3 h-3 shrink-0" />{folderName(job.folderId)}
            </span>
          ) : (
            <span className="text-xs text-zinc-600">{job.postedDate}</span>
          )}
        </div>
      )}
      <h3 className={`${compact ? 'text-sm' : 'text-lg'} font-semibold mb-1 group-hover:text-blue-400 transition-colors line-clamp-2`}>{job.title}</h3>
      <p className={`text-zinc-400 text-sm ${compact ? '' : 'mb-4'}`}>{job.company}</p>
      {!compact && (
        <div className="space-y-2 mb-4">
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <MapPin className="w-4 h-4 text-zinc-600" /><span className="truncate">{job.location}</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Briefcase className="w-4 h-4 text-zinc-600" /><span>{job.type}</span>
          </div>
        </div>
      )}
      <div className={`flex flex-wrap items-center gap-2 ${compact ? 'mt-2' : ''}`}>
        {job.deadline && (
          <span className="flex items-center gap-1 text-xs text-zinc-500"><Calendar className="w-3.5 h-3.5" />{job.deadline}</span>
        )}
        {!compact && job.tags.slice(0, 3).map((tag, idx) => (
          <span key={idx} className="px-2 py-1 bg-black/40 border border-zinc-800 rounded text-xs text-zinc-400">{tag}</span>
        ))}
        {!compact && job.tags.length > 3 && <span className="px-2 py-1 text-xs text-zinc-500">+{job.tags.length - 3}</span>}
        <span className="ml-auto flex items-center gap-2 text-zinc-600">
          {job.notes && <StickyNote className="w-3.5 h-3.5" aria-label="Has notes" />}
          {!!job.contactsCount && (
            <span className="flex items-center gap-1 text-xs" aria-label={`${job.contactsCount} contacts`}>
              <Users className="w-3.5 h-3.5" />{job.contactsCount}
            </span>
          )}
        </span>
      </div>
    </div>
  );

  const filterSelect = (key: 'status' | 'contract_type' | 'remote_policy', anyLabel: string, values: string[] = []) => (
    <select
      aria-label={anyLabel}
      value={filters[key]}
      onChange={(e) => setFilter({ [key]: e.target.value })}
      className={`${selectClass} ${filters[key] ? 'border-blue-500/50 text-white' : ''}`}
    >
      <option value="">{anyLabel}</option>
      {values.filter((v) => v !== 'unknown').map((v) => <option key={v} value={v}>{key === 'contract_type' ? CONTRACT_LABELS[v] : label(v)}</option>)}
    </select>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 border-b border-zinc-800 pb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-2 text-white">Job Explorer</h1>
          <p className="text-zinc-400">Paste a job link, or add an offer by hand. Drag offers onto a folder to organize them.</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="px-5 py-3 bg-white text-black rounded-xl font-medium hover:bg-zinc-200 transition-colors flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Add offer
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Sidebar: folders + saved views */}
        <aside className="md:w-60 shrink-0 flex flex-col gap-1" aria-label="Folders and views">
          {scopeButton('all', <Layers className="w-4 h-4" />, 'All offers', facets.total)}
          {scopeButton('unfiled', <Inbox className="w-4 h-4" />, 'Unfiled', facets.unfiled)}

          <p className="mt-4 mb-1 px-3 text-[11px] uppercase tracking-wider text-zinc-600">Folders</p>
          {folders.map((f) =>
            renaming?.id === f.id ? (
              <div key={f.id} className="flex items-center gap-1 px-2">
                <label htmlFor={`rename-${f.id}`} className="sr-only">Folder name</label>
                <input
                  id={`rename-${f.id}`}
                  autoFocus
                  value={renaming.name}
                  onChange={(e) => setRenaming({ ...renaming, name: e.target.value })}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') renameFolder();
                    if (e.key === 'Escape') setRenaming(null);
                  }}
                  className="flex-1 min-w-0 bg-zinc-950 border border-blue-500/50 rounded px-2 py-1.5 text-sm text-white focus:outline-none"
                />
                <button onClick={renameFolder} aria-label="Save folder name" className="p-1 text-zinc-400 hover:text-white"><Check className="w-4 h-4" /></button>
              </div>
            ) : (
              <div key={f.id} className="group relative" onDoubleClick={() => setRenaming({ id: f.id, name: f.name })}>
                {scopeButton(f.id, <FolderIcon className="w-4 h-4" />, f.name, f.count)}
                <span className="absolute right-8 top-1/2 -translate-y-1/2 flex gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                  <button onClick={() => setRenaming({ id: f.id, name: f.name })} aria-label={`Rename folder ${f.name}`} className="p-1 rounded text-zinc-500 hover:text-white">
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => deleteFolder(f)} aria-label={`Delete folder ${f.name}`} className="p-1 rounded text-zinc-500 hover:text-red-400">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </span>
              </div>
            ),
          )}
          <div className="mt-2 flex items-center gap-2 px-3">
            <FolderPlus className="w-4 h-4 text-zinc-600 shrink-0" />
            <input
              value={newFolder}
              onChange={(e) => setNewFolder(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && createFolder()}
              placeholder="New folder…"
              aria-label="New folder name"
              className="w-full bg-transparent border-b border-zinc-800 py-1 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          <p className="mt-6 mb-1 px-3 text-[11px] uppercase tracking-wider text-zinc-600">Saved views</p>
          {views.length === 0 && <p className="px-3 text-xs text-zinc-600">Set filters, then “Save view”.</p>}
          {views.map((v) => (
            <div key={v.id} className="group relative">
              <button
                onClick={() => applyView(v)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                  activeView?.id === v.id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                }`}
              >
                <Bookmark className="w-4 h-4" />
                <span className="flex-1 truncate">{v.name}</span>
                <span className="text-[11px] text-zinc-600">{v.layout}</span>
              </button>
              <button onClick={() => deleteView(v)} aria-label={`Delete view ${v.name}`} className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded text-zinc-500 hover:text-red-400 opacity-0 group-hover:opacity-100 focus:opacity-100">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </aside>

        <main className="flex-1 min-w-0">
          {/* Capture Bar */}
          <div className="mb-3 flex gap-4">
            <div className="flex-1 relative group">
              <Link2 className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 group-focus-within:text-blue-400 transition-colors" />
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && capture()}
                placeholder="https://... (job posting link)"
                aria-label="Job posting link"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-12 pr-4 py-4 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
              />
            </div>
            <button
              onClick={capture}
              disabled={loading}
              className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
              <span>Capture</span>
            </button>
          </div>

          <button
            onClick={() => setPasteMode(!pasteMode)}
            className="mb-4 flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <ClipboardPaste className="w-4 h-4" />
            <span>{pasteMode ? 'Hide pasted text' : 'Or paste the job description text'}</span>
          </button>

          {pasteMode && (
            <textarea
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              rows={8}
              placeholder="Paste the full job description here (keep the link above if you have it)..."
              className="w-full mb-4 bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
            />
          )}

          {error && (
            <p className="mb-6 px-4 py-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</p>
          )}

          {/* Search + filters */}
          <div className="mt-2 mb-3 flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[12rem]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <input
                value={filters.q}
                onChange={(e) => setFilter({ q: e.target.value })}
                placeholder="Search by meaning or keywords, e.g. remote data roles, apprentissage automatique…"
                aria-label="Search offers"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500/50"
              />
            </div>
            {filterSelect('status', 'Any status', options?.statuses)}
            {filterSelect('contract_type', 'Any contract', options?.contract_types)}
            {filterSelect('remote_policy', 'Any remote', options?.remote_policies)}
            <select aria-label="Sort" value={filters.sort} onChange={(e) => setFilter({ sort: e.target.value })} className={selectClass}>
              <option value="">{filters.q ? 'Best match' : 'Newest'}</option>
              <option value="deadline">Deadline</option>
              <option value="updated">Recently updated</option>
              <option value="title">Title</option>
              <option value="company">Company</option>
            </select>
          </div>

          <div className="mb-5 flex flex-wrap items-center gap-2">
            {filtersActive && (
              <button onClick={() => setFilters(EMPTY_FILTERS)} className="text-xs text-zinc-500 hover:text-white">Clear filters</button>
            )}

            <span className="ml-auto flex items-center gap-2">
              {savingView !== null ? (
                <>
                  <label htmlFor="view-name" className="sr-only">View name</label>
                  <input
                    id="view-name"
                    autoFocus
                    value={savingView}
                    onChange={(e) => setSavingView(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveView(true);
                      if (e.key === 'Escape') setSavingView(null);
                    }}
                    placeholder="View name"
                    className="bg-zinc-950 border border-blue-500/50 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none w-40"
                  />
                  <button onClick={() => saveView(true)} className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 hover:bg-blue-700">Save</button>
                  <button onClick={() => setSavingView(null)} className="px-2 py-1.5 text-sm text-zinc-400 hover:text-white">Cancel</button>
                </>
              ) : (
                <>
                  {viewDirty && (
                    <button onClick={() => saveView(false)} className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200">
                      Update “{activeView!.name}”
                    </button>
                  )}
                  <button onClick={() => setSavingView('')} className="px-3 py-1.5 text-sm rounded-lg text-zinc-300 hover:bg-zinc-800 flex items-center gap-1.5">
                    <Bookmark className="w-4 h-4" />Save view
                  </button>
                </>
              )}
              <span className="flex rounded-lg border border-zinc-800 overflow-hidden" role="group" aria-label="Layout">
                {([['grid', LayoutGrid], ['table', TableIcon], ['board', Columns3]] as const).map(([key, Icon]) => (
                  <button
                    key={key}
                    onClick={() => setLayout(key)}
                    aria-pressed={layout === key}
                    aria-label={`${label(key)} layout`}
                    className={`p-2 ${layout === key ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-white'}`}
                  >
                    <Icon className="w-4 h-4" />
                  </button>
                ))}
              </span>
            </span>
          </div>

          <h2 className="mb-4 text-sm font-medium text-zinc-400">
            {scopeName} <span className="text-zinc-600 tabular-nums">· {jobs.length}</span>
            {filters.q && searchMode.startsWith('keyword (') && (
              <span className="ml-2 text-xs text-amber-400/80">Keyword matches only: meaning-based search is unavailable right now</span>
            )}
          </h2>

          {loading ? (
            <div className="py-20 text-center">
              <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-6"></div>
              <h3 className="text-xl font-medium text-white mb-2">Reading the job posting...</h3>
              <p className="text-zinc-500">Extracting role, company, skills and deadline.</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-16 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl">
              <Briefcase className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-zinc-400 mb-2">
                {facets.total === 0 ? 'No offers yet' : filtersActive ? 'No offer matches these filters' : 'This folder is empty'}
              </h3>
              <p className="text-zinc-600">
                {facets.total === 0
                  ? 'Paste a job link above, or use “Add offer” to create one by hand.'
                  : filtersActive ? 'Change or clear the filters.' : 'Drag an offer card onto this folder in the sidebar.'}
              </p>
            </div>
          ) : layout === 'grid' ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {jobs.map((job) => <OfferCard key={job.id} job={job} />)}
            </div>
          ) : layout === 'table' ? (
            <div className="overflow-x-auto border border-zinc-800 rounded-xl">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wider text-zinc-500 bg-zinc-900">
                  <tr>
                    {['Offer', 'Location', 'Contract', 'Remote', 'Status', 'Deadline', 'Folder'].map((h) => (
                      <th key={h} scope="col" className="px-4 py-3 font-medium whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id} {...dragProps(job)} onClick={() => onJobSelect(job)} className="border-t border-zinc-800 hover:bg-zinc-900 cursor-pointer">
                      <td className="px-4 py-3">
                        <p className="font-medium text-white">{job.title}</p>
                        <p className="text-xs text-zinc-500">{job.company}</p>
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{job.location}</td>
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap">{job.type}</td>
                      <td className="px-4 py-3 text-zinc-400">{job.remotePolicy === 'unknown' ? '—' : label(job.remotePolicy)}</td>
                      <td className="px-4 py-3 text-zinc-300 whitespace-nowrap">{label(job.status)}</td>
                      <td className="px-4 py-3 text-zinc-400 tabular-nums whitespace-nowrap">{job.deadline || '—'}</td>
                      <td className="px-4 py-3 text-zinc-400">{folderName(job.folderId) || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overflow-x-auto pb-2">
              <div className="flex gap-3 min-w-max">
                {(options?.statuses || []).map((s) => {
                  const col = jobs.filter((j) => j.status === s);
                  return (
                    <section
                      key={s}
                      aria-label={`${label(s)} column`}
                      {...dropOn(`status:${s}`, (id) => patchApplication(id, { stage: s }))}
                      className={`w-60 shrink-0 rounded-xl p-2 flex flex-col gap-2 transition-colors ${
                        dropTarget === `status:${s}` ? 'bg-blue-600/10 ring-1 ring-blue-500' : 'bg-zinc-950 border border-zinc-900'
                      }`}
                    >
                      <h3 className="px-1 pt-1 flex items-center justify-between text-xs font-medium uppercase tracking-wider text-zinc-500">
                        {label(s)} <span className="tabular-nums">{col.length}</span>
                      </h3>
                      {col.map((job) => <OfferCard key={job.id} job={job} compact />)}
                    </section>
                  );
                })}
              </div>
            </div>
          )}
        </main>
      </div>

      {showAdd && (
        <AddOfferDialog
          folders={folders}
          defaultFolderId={scope !== 'all' && scope !== 'unfiled' ? scope : undefined}
          onClose={() => setShowAdd(false)}
          onCreated={async (offer) => {
            setShowAdd(false);
            await refresh();
            onJobSelect(toJob(offer));
          }}
        />
      )}
    </div>
  );
}
