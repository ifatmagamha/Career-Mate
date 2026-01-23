import { useState } from 'react';
import { FileText, Mail, MessageSquare, Sparkles, Download, Copy, RotateCw } from 'lucide-react';

type GeneratorType = 'cover-letter' | 'cold-email' | 'interview';

export function GeneratorView() {
  const [activeTab, setActiveTab] = useState<GeneratorType>('cover-letter');
  const [jobDescription, setJobDescription] = useState('');
  const [tone, setTone] = useState('professional');
  const [generated, setGenerated] = useState(false);
  const [generatedContent, setGeneratedContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const tabs = [
    { id: 'cover-letter' as GeneratorType, label: 'AI Cover Letter', icon: <FileText className="w-4 h-4" /> },
    { id: 'cold-email' as GeneratorType, label: 'AI Cold Email', icon: <Mail className="w-4 h-4" /> },
    { id: 'interview' as GeneratorType, label: 'AI Interview Questions', icon: <MessageSquare className="w-4 h-4" /> }
  ];

  const tones = [
    { id: 'professional', label: 'Professional' },
    { id: 'enthusiastic', label: 'Enthusiastic' },
    { id: 'creative', label: 'Creative' },
    { id: 'formal', label: 'Formal' }
  ];

  const handleGenerate = () => {
    setIsGenerating(true);
    
    setTimeout(() => {
      let content = '';
      
      if (activeTab === 'cover-letter') {
        content = `Dear Hiring Manager,

I am writing to express my strong interest in the Software Developer position at Microsoft. With over 5 years of experience in full-stack development and a proven track record of delivering high-quality solutions, I am confident that I would be a valuable addition to your team.

Throughout my career, I have developed expertise in Python, Django, and PostgreSQL - technologies that align perfectly with the requirements outlined in your job posting. At my current role, I led the development of a cloud-based application that improved system performance by 40% and reduced operational costs by $200K annually.

What particularly excites me about this opportunity is Microsoft's commitment to innovation and cloud technology. I am passionate about building scalable solutions that make a real impact, and I believe my experience with distributed systems and microservices architecture would enable me to contribute meaningfully to your projects from day one.

I am particularly drawn to your company culture that emphasizes continuous learning and collaboration. I thrive in environments where I can both contribute my expertise and learn from talented colleagues.

I would welcome the opportunity to discuss how my background, skills, and enthusiasm align with the needs of your team. Thank you for considering my application.

Best regards,
John Doe`;
      } else if (activeTab === 'cold-email') {
        content = `Subject: Experienced Software Developer Interested in Opportunities at Microsoft

Hi [Hiring Manager],

I hope this email finds you well. My name is John Doe, and I'm a Software Developer with 5+ years of experience specializing in Python, Django, and cloud technologies.

I've been following Microsoft's work in cloud computing and was impressed by your recent innovations in Azure services. I'm reaching out because I believe my background in building scalable distributed systems aligns well with the kind of challenges your team is solving.

Key highlights of my experience:
• Led development of a cloud platform serving 100K+ users
• Reduced system latency by 40% through architecture optimization
• Expertise in Python, Django, PostgreSQL, and AWS/Azure

I'd love to learn more about any upcoming opportunities on your team or discuss how I might be able to contribute to your projects. Would you be open to a brief call next week?

Thank you for your time and consideration.

Best regards,
John Doe
LinkedIn: linkedin.com/in/johndoe
Portfolio: johndoe.dev`;
      } else {
        content = `Based on the job description for Software Developer at Microsoft, here are likely interview questions you should prepare for:

**Technical Questions:**

1. "Explain the differences between Django's ORM and raw SQL. When would you use each?"
   - Focus on performance optimization, complex queries, and maintainability

2. "How would you design a scalable REST API for a high-traffic application?"
   - Discuss caching strategies, rate limiting, database optimization, and microservices

3. "Walk me through how you'd optimize a slow database query in PostgreSQL."
   - Cover EXPLAIN ANALYZE, indexing strategies, query rewriting, and connection pooling

4. "Describe your experience with cloud platforms (AWS/Azure). How have you used them?"
   - Discuss specific services, infrastructure as code, CI/CD pipelines

**Behavioral Questions:**

5. "Tell me about a time you had to debug a critical production issue. How did you approach it?"
   - Use STAR method: Situation, Task, Action, Result

6. "Describe a situation where you had to work with a difficult team member."
   - Emphasize communication, empathy, and problem-solving

7. "What's the most challenging technical problem you've solved?"
   - Highlight problem-solving skills, creativity, and impact

**System Design:**

8. "Design a URL shortening service like bit.ly"
   - Cover database schema, API design, scaling strategies, caching

**Preparation Tips:**
• Review Python best practices and Django advanced features
• Practice system design questions on a whiteboard
• Prepare specific examples from your experience
• Research Microsoft's technology stack and recent projects`;
      }
      
      setGeneratedContent(content);
      setGenerated(true);
      setIsGenerating(false);
    }, 2000);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(generatedContent);
  };

  const getTitle = () => {
    switch (activeTab) {
      case 'cover-letter':
        return 'AI Cover Letter Generator';
      case 'cold-email':
        return 'AI Cold Email Generator';
      case 'interview':
        return 'AI Interview Questions';
    }
  };

  const getSubtitle = () => {
    switch (activeTab) {
      case 'cover-letter':
        return 'Craft the perfect job specific cover letter with the power of AI ✨';
      case 'cold-email':
        return 'Create compelling cold emails to hiring managers with AI ✨';
      case 'interview':
        return 'Prepare for your interview with AI-generated questions ✨';
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Navigation Tabs */}
      <div className="flex gap-2 mb-8 border-b border-zinc-800 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              setGenerated(false);
              setJobDescription('');
            }}
            className={`
              flex items-center gap-2 px-6 py-3 rounded-t-lg transition-all whitespace-nowrap
              ${activeTab === tab.id
                ? 'bg-white text-black font-medium'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
              }
            `}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {!generated ? (
        <>
          {/* Header */}
          <div className="text-center mb-12">
            <p className="text-sm text-zinc-500 mb-4">{getSubtitle()}</p>
            <h1 className="text-5xl font-bold mb-4">{getTitle()}</h1>
            <p className="text-lg text-zinc-400">{getSubtitle()}</p>
          </div>

          {/* Input Form */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 space-y-6">
            {/* Job Description */}
            <div>
              <label className="block text-white font-medium mb-3">
                1. What's your Job Description?
              </label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Provide the job description for your email here..."
                className="w-full h-48 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 resize-none"
              />
            </div>

            {/* Tone Selection */}
            <div>
              <label className="block text-white font-medium mb-3">
                2. Select your tone.
              </label>
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-zinc-600"
              >
                {tones.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={!jobDescription || isGenerating}
              className="w-full py-4 bg-white text-black rounded-xl font-semibold hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isGenerating ? (
                <>
                  <RotateCw className="w-5 h-5 animate-spin" />
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>Generate</span>
                </>
              )}
            </button>

            <p className="text-xs text-zinc-600 text-center">
              Agent: Writer + Matcher | Uses your profile data and job requirements
            </p>
          </div>
        </>
      ) : (
        <>
          {/* Result Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold mb-1">Generated {getTitle().replace('AI ', '')}</h2>
              <p className="text-zinc-500">Review and customize as needed</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleCopy}
                className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-zinc-700 transition-colors flex items-center gap-2"
              >
                <Copy className="w-4 h-4" />
                <span>Copy</span>
              </button>
              <button
                onClick={() => setGenerated(false)}
                className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-zinc-700 transition-colors flex items-center gap-2"
              >
                <RotateCw className="w-4 h-4" />
                <span>Regenerate</span>
              </button>
              <button className="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors flex items-center gap-2">
                <Download className="w-4 h-4" />
                <span>Download</span>
              </button>
            </div>
          </div>

          {/* Generated Content */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8">
            <div className="bg-white text-black rounded-lg p-8 font-serif">
              <pre className="whitespace-pre-wrap font-sans">{generatedContent}</pre>
            </div>
          </div>

          {/* Quick Edit Tools */}
          <div className="mt-6 bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h3 className="font-semibold mb-4">Quick Adjustments</h3>
            <div className="flex flex-wrap gap-3">
              <button className="px-4 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">
                Make it shorter
              </button>
              <button className="px-4 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">
                Make it longer
              </button>
              <button className="px-4 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">
                More formal
              </button>
              <button className="px-4 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">
                More enthusiastic
              </button>
              <button className="px-4 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 transition-colors text-sm">
                Add specific examples
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
