import { useState, useEffect } from 'react';
import { Link2, MapPin, Briefcase, Calendar, Sparkles, Loader, ClipboardPaste } from 'lucide-react';

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
}

interface JobExplorerProps {
  onJobSelect: (job: Job) => void;
}

const CONTRACT_LABELS: Record<string, string> = {
  permanent: 'Permanent (CDI)',
  fixed_term: 'Fixed-term (CDD)',
  internship: 'Internship',
  apprenticeship: 'Apprenticeship',
  freelance: 'Freelance',
  part_time: 'Part-time',
  unknown: 'Not specified',
};

// Backend offer row -> UI job
const toJob = (o: any): Job => ({
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
});

export function JobExplorer({ onJobSelect }: JobExplorerProps) {
  const [url, setUrl] = useState('');
  const [pastedText, setPastedText] = useState('');
  const [pasteMode, setPasteMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);

  const fetchOffers = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/offers');
      setJobs((await res.json()).map(toJob));
    } catch (e) {
      console.error('Failed to load offers', e);
    }
  };

  const capture = async () => {
    const text = pasteMode ? pastedText.trim() : '';
    if (!url.trim() && !text) return;
    setLoading(true);
    setError('');

    try {
      const res = await fetch('http://localhost:8000/api/offers/capture', {
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
      await fetchOffers();
      onJobSelect(toJob(data.offer));
    } catch (e) {
      console.error('Capture failed', e);
      setError('Error connecting to server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOffers();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 border-b border-zinc-800 pb-6">
        <h1 className="text-3xl font-bold mb-2 text-white">Job Explorer</h1>
        <p className="text-zinc-400">Paste a job link: the AI builds the job sheet</p>
      </div>

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

      {/* Offers Grid */}
      {loading ? (
        <div className="py-20 text-center">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-6"></div>
          <h3 className="text-xl font-medium text-white mb-2">Reading the job posting...</h3>
          <p className="text-zinc-500">Extracting role, company, skills and deadline.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-4">
            {jobs.map((job) => (
              <div
                key={job.id}
                onClick={() => onJobSelect(job)}
                className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-blue-500/30 hover:bg-zinc-800/50 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="px-3 py-1 rounded-full border border-zinc-700 text-xs text-zinc-400 capitalize">
                    {job.status}
                  </span>
                  <span className="text-xs text-zinc-600">{job.postedDate}</span>
                </div>

                <h3 className="text-lg font-semibold mb-1 group-hover:text-blue-400 transition-colors line-clamp-1">
                  {job.title}
                </h3>
                <p className="text-zinc-400 mb-4 text-sm">{job.company}</p>

                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <MapPin className="w-4 h-4 text-zinc-600" />
                    <span className="truncate">{job.location}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <Briefcase className="w-4 h-4 text-zinc-600" />
                    <span>{job.type}</span>
                  </div>
                  {job.deadline && (
                    <div className="flex items-center gap-2 text-sm text-zinc-500">
                      <Calendar className="w-4 h-4 text-zinc-600" />
                      <span>Apply by {job.deadline}</span>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  {job.tags.slice(0, 3).map((tag, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 bg-black/40 border border-zinc-800 rounded text-xs text-zinc-400"
                    >
                      {tag}
                    </span>
                  ))}
                  {job.tags.length > 3 && (
                    <span className="px-2 py-1 text-xs text-zinc-500">+{job.tags.length - 3}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {jobs.length === 0 && (
            <div className="text-center py-16 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl">
              <Briefcase className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-zinc-400 mb-2">No offers captured yet</h3>
              <p className="text-zinc-600">Paste a job link above to create your first job sheet.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
