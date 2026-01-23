import { ArrowLeft, MapPin, DollarSign, Briefcase, Calendar, TrendingUp, Building2, CheckCircle2, Sparkles } from 'lucide-react';

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
}

interface JobDetailProps {
  job: Job | null;
  onBack: () => void;
}

export function JobDetail({ job, onBack }: JobDetailProps) {
  const handleAction = async (stage: 'applied' | 'saved') => {
    if (!job) return;

    try {
      const res = await fetch('http://localhost:8000/api/applications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: job.title,
          company: job.company,
          location: job.location,
          salary: job.salary,
          matchScore: job.matchScore,
          stage: stage
        })
      });

      if (res.ok) {
        alert(stage === 'applied' ? 'Applied successfully!' : 'Saved to tracker!');
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

  const matchInsights = [
    { label: 'Skills Match', score: 95, detail: 'Python, Django, PostgreSQL' },
    { label: 'Experience Level', score: 88, detail: '5+ years requirement met' },
    { label: 'Location Preference', score: 100, detail: 'Remote work available' },
    { label: 'Salary Alignment', score: 92, detail: 'Within your target range' }
  ];

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
              <div className={`px-4 py-2 rounded-xl bg-gradient-to-r ${getMatchColor(job.matchScore)} text-white font-semibold`}>
                {job.matchScore}% Match
              </div>
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
                  <p className="text-xs text-zinc-600">Posted</p>
                  <p className="text-white">{job.postedDate}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Description */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4">Job Description</h2>
            <p className="text-zinc-400 leading-relaxed">{job.description}</p>
          </div>

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

          {/* Benefits */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-4">Benefits</h2>
            <div className="flex flex-wrap gap-3">
              {job.benefits.map((benefit, idx) => (
                <span
                  key={idx}
                  className="px-4 py-2 bg-zinc-800 rounded-lg text-zinc-300"
                >
                  {benefit}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Match Analysis */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-semibold">AI Match Analysis</h2>
            </div>
            <p className="text-sm text-zinc-500 mb-4">
              Agent: Matcher + Analyzer
            </p>
            <div className="space-y-4">
              {matchInsights.map((insight, idx) => (
                <div key={idx}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-zinc-400">{insight.label}</span>
                    <span className="text-sm font-semibold">{insight.score}%</span>
                  </div>
                  <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full bg-gradient-to-r ${getMatchColor(insight.score)}`}
                      style={{ width: `${insight.score}%` }}
                    />
                  </div>
                  <p className="text-xs text-zinc-600 mt-1">{insight.detail}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
            <div className="space-y-3">
              <button
                onClick={() => handleAction('applied')}
                className="w-full py-3 bg-white text-black rounded-lg font-medium hover:bg-zinc-200 transition-colors"
              >
                Apply Now
              </button>
              <button className="w-full py-3 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700 transition-colors">
                Generate Cover Letter
              </button>
              <button
                onClick={() => handleAction('saved')}
                className="w-full py-3 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700 transition-colors"
              >
                Save to Tracker
              </button>
              <button className="w-full py-3 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700 transition-colors">
                Analyze with AI
              </button>
            </div>
          </div>

          {/* Company Insights */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Company Insights</h2>
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-zinc-600 mb-1">Industry</p>
                <p className="text-white">Technology</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-1">Size</p>
                <p className="text-white">10,000+ employees</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-1">Founded</p>
                <p className="text-white">1975</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-1">Glassdoor Rating</p>
                <p className="text-white">4.2/5.0 ⭐</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
