import { useState, useEffect } from 'react';
import { FileText, Mail, MessageSquare, Sparkles, Download, Copy, RotateCw } from 'lucide-react';

type GeneratorType = 'cover-letter' | 'cold-email' | 'interview';

interface GeneratorViewProps {
  initialDescription?: string;
}

export function GeneratorView({ initialDescription = '' }: GeneratorViewProps) {
  const [activeTab, setActiveTab] = useState<GeneratorType>('cover-letter');
  const [jobDescription, setJobDescription] = useState(initialDescription);
  const [tone, setTone] = useState('professional');
  const [difficulty, setDifficulty] = useState('medium');
  const [generated, setGenerated] = useState(false);
  const [generatedContent, setGeneratedContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (initialDescription) {
      setJobDescription(initialDescription);
      setGenerated(false);
    }
  }, [initialDescription]);

  const tabs = [
    { id: 'cover-letter' as GeneratorType, label: 'AI Cover Letter', icon: <FileText className="w-4 h-4" /> },
    { id: 'cold-email' as GeneratorType, label: 'AI Cold Email', icon: <Mail className="w-4 h-4" /> },
    { id: 'interview' as GeneratorType, label: 'AI Interview Prep', icon: <MessageSquare className="w-4 h-4" /> }
  ];

  const tones = [
    { id: 'professional', label: 'Professional' },
    { id: 'enthusiastic', label: 'Enthusiastic' },
    { id: 'creative', label: 'Creative' },
    { id: 'formal', label: 'Formal' }
  ];

  const difficulties = [
    { id: 'easy', label: 'Easy' },
    { id: 'medium', label: 'Medium' },
    { id: 'hard', label: 'Hard' }
  ];

  const handleGenerate = async () => {
    if (!jobDescription) return;
    setIsGenerating(true);
    try {
      const res = await fetch("http://localhost:8000/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: activeTab,
          job_description: jobDescription,
          extra: activeTab === 'interview' ? difficulty : tone
        })
      });
      const data = await res.json();
      if (data.status === "success") {
        setGeneratedContent(data.content);
        setGenerated(true);
      } else {
        alert(data.detail || "Generation failed.");
      }
    } catch (err) {
      alert("Error contacting the AI agent.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(generatedContent);
  };

  const getTitle = () => {
    switch (activeTab) {
      case 'cover-letter': return 'AI Cover Letter Generator';
      case 'cold-email': return 'AI Cold Email Generator';
      case 'interview': return 'AI Interview Questions';
    }
  };

  const getSubtitle = () => {
    switch (activeTab) {
      case 'cover-letter': return 'Craft the perfect job specific cover letter with the power of AI ✨';
      case 'cold-email': return 'Create compelling cold emails to hiring managers with AI ✨';
      case 'interview': return 'Prepare for your interview with AI-generated questions ✨';
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex gap-2 mb-8 border-b border-zinc-800 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              setGenerated(false);
            }}
            className={`flex items-center gap-2 px-6 py-3 rounded-t-lg transition-all whitespace-nowrap ${activeTab === tab.id ? 'bg-white text-black font-medium' : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
              }`}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {!generated ? (
        <>
          <div className="text-center mb-12">
            <h1 className="text-5xl font-bold mb-4">{getTitle()}</h1>
            <p className="text-lg text-zinc-400">{getSubtitle()}</p>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 space-y-6">
            <div>
              <label className="block text-white font-medium mb-3">1. What's the Job Description?</label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the job description here..."
                className="w-full h-48 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 resize-none"
              />
            </div>

            {activeTab === 'interview' ? (
              <div>
                <label className="block text-white font-medium mb-3">2. Select difficulty level.</label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-zinc-600"
                >
                  {difficulties.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
                </select>
              </div>
            ) : (
              <div>
                <label className="block text-white font-medium mb-3">2. Select your tone.</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-zinc-600"
                >
                  {tones.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={!jobDescription || isGenerating}
              className="w-full py-4 bg-white text-black rounded-xl font-semibold hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? <RotateCw className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
              <span>{isGenerating ? 'Generating...' : 'Generate'}</span>
            </button>
          </div>
        </>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">Generated Result</h2>
            <div className="flex gap-3">
              <button onClick={handleCopy} className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-2"><Copy className="w-4 h-4" />Copy</button>
              <button onClick={() => setGenerated(false)} className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-2"><RotateCw className="w-4 h-4" />Regenerate</button>
            </div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8">
            <div className="bg-white text-black rounded-lg p-8 font-sans overflow-auto max-h-[600px]">
              <pre className="whitespace-pre-wrap">{generatedContent}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
