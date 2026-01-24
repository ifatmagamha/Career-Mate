import { useState, useEffect } from 'react';
import { User, Briefcase, MapPin, Mail, FileText, CheckCircle2, RefreshCw, TrendingUp, Clock } from 'lucide-react';

interface Application {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  matchScore: number;
  stage: 'saved' | 'applied' | 'interviewing' | 'offer' | 'rejected';
  appliedDate: string;
}

export function ProfileView() {
  const [loading, setLoading] = useState(false);
  const [activeProfile, setActiveProfile] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'profile' | 'applications'>('profile');

  const [applications, setApplications] = useState<Application[]>([]);

  useEffect(() => {
    fetchProfile();
    fetchApplications();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/profile/current');
      const data = await res.json();
      setActiveProfile(data);
    } catch (e) {
      console.error("Failed to fetch profile", e);
    }
  };

  const fetchApplications = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/applications');
      const data = await res.json();
      setApplications(data);
    } catch (e) {
      console.error("Failed to fetch applications", e);
    }
  };

  const handleProfileUpdate = (field: string, value: any) => {
    setActiveProfile({ ...activeProfile, [field]: value });
  };

  useEffect(() => {
    console.log("Active Profile Data:", activeProfile);
  }, [activeProfile]);

  if (!activeProfile) return <div className="p-8 text-center">Loading profile...</div>;

  const hasProfile = (activeProfile.name && activeProfile.name.length > 0) ||
    (activeProfile.email && activeProfile.email.length > 0) ||
    (activeProfile.skills && activeProfile.skills.length > 0);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">My Profile</h1>
        <p className="text-zinc-400">Manage your career profile, documents, and applications</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-zinc-800">
        <button
          onClick={() => setActiveTab('profile')}
          className={`pb-3 px-1 text-sm font-medium transition-colors relative ${activeTab === 'profile' ? 'text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}
        >
          Profile & Documents
          {activeTab === 'profile' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('applications')}
          className={`pb-3 px-1 text-sm font-medium transition-colors relative ${activeTab === 'applications' ? 'text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}
        >
          My Applications ({applications.length})
          {activeTab === 'applications' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500" />
          )}
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'profile' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* LEFT PANEL: Document Vault */}
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <FileText className="w-5 h-5 text-[#C4C4C4]" />
                Document Vault
              </h2>
            </div>

            {/* Upload Area */}
            <div className="space-y-4">
              <div className="relative">
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={async (e) => {
                    if (!e.target.files) return;
                    const file = e.target.files[0];
                    const formData = new FormData();
                    formData.append("file", file);

                    setLoading(true);
                    try {
                      await fetch("http://localhost:8000/api/upload_resume", {
                        method: "POST",
                        body: formData
                      });
                      await fetchProfile();
                      alert("Resume parsed successfully!");
                    } catch (err) {
                      alert("Upload failed.");
                      console.error(err);
                    } finally {
                      setLoading(false);
                    }
                  }}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                />
                <div className={`border-2 border-dashed border-zinc-700 bg-zinc-900/50 rounded-xl p-8 text-center hover:border-[#C4C4C4] transition-colors group ${loading ? 'opacity-50 pointer-events-none' : ''}`}>
                  <div className="w-12 h-12 bg-zinc-800 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform">
                    {loading ? <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" /> : <User className="w-6 h-6 text-[#C4C4C4]" />}
                  </div>
                  <h3 className="font-medium text-white mb-1">{loading ? "Analyzing..." : "Upload Your Resume"}</h3>
                  <p className="text-sm text-zinc-500 mb-4">PDF or DOCX format</p>
                  <div className="flex justify-center gap-2">
                    <span className="px-3 py-1.5 bg-zinc-800 rounded-lg text-xs border border-zinc-700">CV / Resume</span>
                  </div>
                </div>
              </div>

              <button
                onClick={async () => {
                  setLoading(true);
                  try {
                    const res = await fetch("http://localhost:8000/api/profile/sync", { method: "POST" });
                    const data = await res.json();
                    if (data.count > 0) {
                      await fetchProfile();
                      alert(`Successfully synced ${data.count} CV(s) from data/cvs`);
                    } else {
                      alert("No new CVs found in data/cvs folder.");
                    }
                  } catch (err) {
                    alert("Sync failed.");
                  } finally {
                    setLoading(false);
                  }
                }}
                className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded-lg border border-zinc-700 flex items-center justify-center gap-2 transition-colors"
                disabled={loading}
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Sync from data/cvs Folder
              </button>
            </div>

            {/* File List */}
            {hasProfile && (
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Uploaded Documents</h3>
                <div className="flex items-center gap-3 p-3 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-zinc-600 transition-all">
                  <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5 text-blue-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-sm text-white truncate">Resume.pdf</h4>
                    <p className="text-xs text-zinc-500">Processed & Indexed</p>
                  </div>
                  <button className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* RIGHT PANEL: Editable Profile Form */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 h-fit">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-[#C4C4C4]" />
                Profile Details
              </h2>
              <button
                onClick={async () => {
                  setLoading(true);
                  try {
                    const payload = {
                      full_name: activeProfile.name || "",
                      email: activeProfile.email || "",
                      location: activeProfile.location || "",
                      skills: activeProfile.skills || [],
                      experience: activeProfile.experience || [],
                      summary: activeProfile.summary || "",
                      cv_text: activeProfile.cv_text || ""
                    };

                    const res = await fetch('http://localhost:8000/api/profile/save', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(payload)
                    });

                    if (res.ok) {
                      alert('Profile saved successfully!');
                      await fetchProfile();
                    } else {
                      throw new Error('Failed to save');
                    }
                  } catch (e) {
                    console.error(e);
                    alert('Error saving profile');
                  } finally {
                    setLoading(false);
                  }
                }}
                className={`px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                disabled={loading}
              >
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>

            {!hasProfile ? (
              <div className="text-center py-12">
                <User className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
                <p className="text-zinc-500 mb-2">No profile data yet</p>
                <p className="text-sm text-zinc-600">Upload your resume to get started</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Identity Section */}
                <div className="space-y-3">
                  <label className="text-xs font-medium text-zinc-500 uppercase">Identity</label>
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      type="text"
                      value={activeProfile.name || ''}
                      onChange={(e) => handleProfileUpdate('name', e.target.value)}
                      className="bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
                      placeholder="Full Name"
                    />
                    <input
                      type="text"
                      value={activeProfile.title || ''}
                      onChange={(e) => handleProfileUpdate('title', e.target.value)}
                      className="bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
                      placeholder="Job Title"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      type="email"
                      value={activeProfile.email || ''}
                      onChange={(e) => handleProfileUpdate('email', e.target.value)}
                      className="bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
                      placeholder="Email"
                    />
                    <input
                      type="text"
                      value={activeProfile.location || ''}
                      onChange={(e) => handleProfileUpdate('location', e.target.value)}
                      className="bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
                      placeholder="Location"
                    />
                  </div>
                </div>

                <div className="h-px bg-zinc-800" />

                {/* Summary Section */}
                <div className="space-y-3">
                  <label className="text-xs font-medium text-zinc-500 uppercase">Summary</label>
                  <textarea
                    value={activeProfile.summary || ''}
                    onChange={(e) => handleProfileUpdate('summary', e.target.value)}
                    className="w-full h-24 bg-black/50 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none resize-none"
                    placeholder="Brief professional summary..."
                  />
                </div>

                <div className="h-px bg-zinc-800" />

                {/* Skills Section */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-medium text-zinc-500 uppercase">Skills</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Add skill..."
                        className="bg-zinc-800 border border-zinc-700 rounded px-2 py-0.5 text-xs text-white outline-none"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const val = e.currentTarget.value.trim();
                            if (val) {
                              const current = activeProfile.skills || [];
                              handleProfileUpdate('skills', [...current, val]);
                              e.currentTarget.value = '';
                            }
                          }
                        }}
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {activeProfile.skills && activeProfile.skills.length > 0 ? (
                      activeProfile.skills.map((skill: string, i: number) => (
                        <span key={i} className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-xs text-zinc-300 flex items-center gap-1 group cursor-pointer hover:bg-zinc-700">
                          {skill}
                          <span
                            onClick={() => {
                              const newList = activeProfile.skills.filter((_: any, idx: number) => idx !== i);
                              handleProfileUpdate('skills', newList);
                            }}
                            className="text-zinc-500 hover:text-red-400 font-bold px-1"
                          >
                            ×
                          </span>
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-zinc-500 italic">No skills listed.</span>
                    )}
                  </div>
                </div>

                <div className="h-px bg-zinc-800" />

                {/* Experience Section */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-medium text-zinc-500 uppercase">Experience</label>
                    <button
                      onClick={() => {
                        const emptyExp = { role: "New Role", company: "Company", duration: "Dates", description: "Responsibilities..." };
                        handleProfileUpdate('experience', [emptyExp, ...(activeProfile.experience || [])]);
                      }}
                      className="text-xs text-blue-400 hover:underline"
                    >
                      + Add Experience
                    </button>
                  </div>

                  {activeProfile.experience && activeProfile.experience.length > 0 ? (
                    activeProfile.experience.map((exp: any, i: number) => (
                      <div key={i} className="p-3 bg-black/30 border border-zinc-800 rounded-lg space-y-2 group relative">
                        <button
                          onClick={() => {
                            const newList = activeProfile.experience.filter((_: any, idx: number) => idx !== i);
                            handleProfileUpdate('experience', newList);
                          }}
                          className="absolute top-2 right-2 text-zinc-600 hover:text-red-500 hidden group-hover:block"
                        >
                          Delete
                        </button>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={exp.role}
                            onChange={(e) => {
                              const newList = [...activeProfile.experience];
                              newList[i].role = e.target.value;
                              handleProfileUpdate('experience', newList);
                            }}
                            className="flex-1 bg-transparent border-b border-transparent hover:border-zinc-700 focus:border-blue-500 outline-none text-sm font-medium text-white"
                          />
                          <input
                            type="text"
                            value={exp.duration || (exp.start_date ? `${exp.start_date} - ${exp.end_date || 'Present'}` : '')}
                            onChange={(e) => {
                              const newList = [...activeProfile.experience];
                              newList[i].duration = e.target.value;
                              handleProfileUpdate('experience', newList);
                            }}
                            className="w-24 bg-transparent border-b border-transparent hover:border-zinc-700 focus:border-blue-500 outline-none text-sm font-medium text-white"
                          />
                        </div>
                        <input
                          type="text"
                          value={exp.company}
                          onChange={(e) => {
                            const newList = [...activeProfile.experience];
                            newList[i].company = e.target.value;
                            handleProfileUpdate('experience', newList);
                          }}
                          className="w-full bg-transparent border-b border-transparent hover:border-zinc-700 focus:border-blue-500 outline-none text-xs text-zinc-400"
                        />
                        <textarea
                          value={exp.description}
                          onChange={(e) => {
                            const newList = [...activeProfile.experience];
                            newList[i].description = e.target.value;
                            handleProfileUpdate('experience', newList);
                          }}
                          className="w-full bg-transparent border border-transparent hover:border-zinc-800 focus:border-zinc-800 focus:bg-zinc-900/50 outline-none text-xs text-zinc-400 p-1 rounded min-h-[60px] resize-none"
                        />
                      </div>
                    ))
                  ) : (
                    <div className="p-3 bg-black/30 border border-zinc-800 rounded-lg">
                      <p className="text-sm text-zinc-500 italic">No experience added yet.</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Applications Tab */
        <div className="space-y-4">
          {applications.length === 0 ? (
            <div className="text-center py-12 bg-zinc-900 border border-zinc-800 rounded-xl">
              <Briefcase className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
              <p className="text-zinc-500 mb-2">No applications yet</p>
              <p className="text-sm text-zinc-600">Start exploring jobs to apply</p>
            </div>
          ) : (
            applications.map((app) => (
              <div key={app.id} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-600 transition-all">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg mb-1">{app.title}</h3>
                    <p className="text-sm text-zinc-400">{app.company}</p>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                    <TrendingUp className="w-4 h-4 text-blue-400" />
                    <span className="text-sm font-semibold text-blue-400">{app.matchScore}%</span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
                  <div className="flex items-center gap-2 text-zinc-500">
                    <MapPin className="w-4 h-4" />
                    <span>{app.location}</span>
                  </div>
                  <div className="flex items-center gap-2 text-zinc-500">
                    <Mail className="w-4 h-4" />
                    <span>{app.salary}</span>
                  </div>
                  <div className="flex items-center gap-2 text-zinc-500">
                    <Clock className="w-4 h-4" />
                    <span>{app.appliedDate}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-zinc-800">
                  <div className="flex items-center gap-3">
                    <select
                      value={app.stage}
                      onChange={async (e) => {
                        const newStage = e.target.value;
                        try {
                          await fetch(`http://localhost:8000/api/applications/${app.id}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ stage: newStage })
                          });
                          fetchApplications();
                        } catch (err) {
                          console.error(err);
                        }
                      }}
                      className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-300 outline-none focus:border-blue-500"
                    >
                      <option value="saved">Saved</option>
                      <option value="applied">Applied</option>
                      <option value="interviewing">Interviewing</option>
                      <option value="offer">Offer</option>
                      <option value="rejected">Rejected</option>
                    </select>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${app.stage === 'interviewing' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30' :
                      app.stage === 'applied' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30' :
                        app.stage === 'offer' ? 'bg-green-500/10 text-green-400 border border-green-500/30' :
                          'bg-zinc-800 text-zinc-400 border border-zinc-700'
                      }`}>
                      {app.stage.charAt(0).toUpperCase() + app.stage.slice(1)}
                    </span>
                  </div>
                  <button className="text-sm text-blue-400 hover:text-blue-300">View Details →</button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
