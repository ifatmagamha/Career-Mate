import { useState } from 'react';
import { ArrowLeft, MapPin, DollarSign, Briefcase, Calendar, Building2, CheckCircle2, ExternalLink } from 'lucide-react';

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
}

interface JobDetailProps {
  job: Job | null;
  onBack: () => void;
  onGenerateCoverLetter: (description: string) => void;
}

export function JobDetail({ job, onBack, onGenerateCoverLetter }: JobDetailProps) {
  const [status, setStatus] = useState(job?.status);

  // Captured offers are already in the tracker: only their stage changes
  const handleAction = async (stage: 'applied') => {
    if (!job?.applicationId) return;

    try {
      const res = await fetch(`http://localhost:8000/api/applications/${job.applicationId}`, {
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
            <div className="flex items-start justify-between mb-4">
              <div>
                <h1 className="text-3xl font-bold mb-2">{job.title}</h1>
                <div className="flex items-center gap-2 text-xl text-zinc-400">
                  <Building2 className="w-5 h-5" />
                  <span>{job.company}</span>
                </div>
              </div>
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
          </div>
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
                onClick={() => onGenerateCoverLetter(job.description)}
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
              <button
                onClick={() => {
                  // Redirect with a pre-filled query for deep analysis
                  window.dispatchEvent(new CustomEvent('deep-analyze-job', { detail: { job } }));
                }}
                className="w-full py-3 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700 transition-colors"
              >
                Analyze with AI
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
