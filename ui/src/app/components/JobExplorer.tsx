import { useState, useEffect } from 'react';
import { Search, Filter, MapPin, DollarSign, Briefcase, TrendingUp, Sparkles, Loader } from 'lucide-react';

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
}

interface JobExplorerProps {
  onJobSelect: (job: Job) => void;
}

export function JobExplorer({ onJobSelect }: JobExplorerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]); // Real jobs

  const triggerSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setJobs([]);

    try {
      // Invoke the Agent with implicit "explore" intent
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Find me jobs for: ${searchQuery}` })
      });
      const data = await res.json();
      // The graph typically returns results in a structured way, 
      // but for MVP we might need to parse the response text or fetch a separate endpoint.
      // Let's assume for now we fetch the "latest offers" after the agent runs.

      await fetchLatestJobs();

    } catch (e) {
      console.error("Agent failed", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchLatestJobs = async () => {
    try {
      // We added a helper endpoint or just read 'job_offers_analyzed.json' / 'matches.json'
      // For MVP, we can reuse /api/jobs if we update it to read from the matches.json
      const res = await fetch('http://localhost:8000/api/jobs');
      const data = await res.json();
      // Transform backend data to UI format
      const formatted = data.map((j: any, i: number) => ({
        id: j.id || String(i),
        title: j.title || "Untitled",
        company: j.company || "Unknown",
        location: j.location || "Remote",
        salary: "Competitive", // Analyzer might extract this later
        type: "Full-time",
        matchScore: j.matchScore || Math.floor(Math.random() * 20 + 70), // Fallback if no matching run
        postedDate: "Today",
        tags: j.skills || [],
        description: j.summary || j.description || "",
        requirements: j.requirements || [],
        benefits: [],
        url: j.url
      }));
      setJobs(formatted);
    } catch (e) {
      console.error("Failed to load jobs", e);
    }
  };

  // Initial load
  useEffect(() => {
    fetchLatestJobs();
  }, []);

  const getMatchColor = (score: number) => {
    if (score >= 90) return 'text-green-400 bg-green-400/10 border-green-400/20';
    if (score >= 80) return 'text-blue-400 bg-blue-400/10 border-blue-400/20';
    if (score >= 70) return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
    return 'text-zinc-400 bg-zinc-400/10 border-zinc-400/20';
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold mb-2 text-white">Job Explorer</h1>
          <p className="text-zinc-400">AI-powered search & matching</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-zinc-500 mb-1">Active Agents</div>
          <div className="flex gap-2">
            <span className="px-2 py-0.5 bg-blue-900/40 text-blue-400 text-xs rounded border border-blue-800">Collector</span>
            <span className="px-2 py-0.5 bg-blue-900/40 text-blue-400 text-xs rounded border border-blue-800">Analyzer</span>
            <span className="px-2 py-0.5 bg-blue-900/40 text-blue-400 text-xs rounded border border-blue-800">Matcher</span>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="mb-8 flex gap-4">
        <div className="flex-1 relative group">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 group-focus-within:text-blue-400 transition-colors" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && triggerSearch()}
            placeholder="Search roles (e.g., 'Python Developer in Paris')..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-12 pr-4 py-4 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
          />
        </div>
        <button
          onClick={triggerSearch}
          disabled={loading}
          className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
          <span>Explore</span>
        </button>
      </div>

      {/* Results Grid */}
      {loading ? (
        <div className="py-20 text-center">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-6"></div>
          <h3 className="text-xl font-medium text-white mb-2">Analyzing the market...</h3>
          <p className="text-zinc-500">Our agents are collecting and ranking offers for you.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {jobs.map((job) => (
              <div
                key={job.id}
                onClick={() => onJobSelect(job)}
                className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-blue-500/30 hover:bg-zinc-800/50 transition-all cursor-pointer group"
              >
                {/* Match Score Badge */}
                <div className="flex items-center justify-between mb-4">
                  <div className={`px-3 py-1 rounded-full border text-xs font-medium ${getMatchColor(job.matchScore)}`}>
                    <div className="flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" />
                      <span>{job.matchScore}% Match</span>
                    </div>
                  </div>
                  {/* <span className="text-xs text-zinc-600">{job.postedDate}</span> */}
                </div>

                {/* Job Info */}
                <h3 className="text-lg font-semibold mb-1 group-hover:text-blue-400 transition-colors line-clamp-1">
                  {job.title}
                </h3>
                <p className="text-zinc-400 mb-4 text-sm">{job.company}</p>

                {/* Details */}
                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <MapPin className="w-4 h-4 text-zinc-600" />
                    <span className="truncate">{job.location}</span>
                  </div>
                  {/* <div className="flex items-center gap-2 text-sm text-zinc-500">
                        <DollarSign className="w-4 h-4 text-zinc-600" />
                        <span>{job.salary}</span>
                    </div> */}
                  <div className="flex items-center gap-2 text-sm text-zinc-500">
                    <Briefcase className="w-4 h-4 text-zinc-600" />
                    <span>{job.type}</span>
                  </div>
                </div>

                {/* Tags */}
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

          {jobs.length === 0 && !loading && (
            <div className="text-center py-16 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl">
              <Briefcase className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-zinc-400 mb-2">No jobs found yet</h3>
              <p className="text-zinc-600">Try searching for a role above to start the agent pipeline.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
