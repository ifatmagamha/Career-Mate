import { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, TrendingUp, Briefcase, FileEdit, BarChart3, ArrowRight, Loader2 } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agent?: string;
  offersCount?: number;
  isStreaming?: boolean;
}

interface ChatViewProps {
  onNavigateToJobs: () => void;
}

export function ChatView({ onNavigateToJobs }: ChatViewProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Hi! I'm your AI career assistant. I can help you with:\n\n📋 Job search & applications\n🎤 Interview preparation\n✍️ Resume & cover letters\n📊 Career market insights\n\nClick a suggestion below or type your question!",
      timestamp: new Date(),
      agent: 'RAG'
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const handleDeepAnalyze = (e: any) => {
      const { job } = e.detail;
      handleSendMessage(`Analyze this job for me: ${job.title} at ${job.company}. Is it a good match for my profile?`);
    };

    window.addEventListener('deep-analyze-job' as any, handleDeepAnalyze);
    return () => window.removeEventListener('deep-analyze-job' as any, handleDeepAnalyze);
  }, []);

  const suggestions = [
    { icon: <Briefcase className="w-4 h-4" />, text: "Find remote software dev jobs paying 80k+", agent: "Collector" },
    { icon: <TrendingUp className="w-4 h-4" />, text: "Help me prepare for Python interview", agent: "Analyzer" },
    { icon: <FileEdit className="w-4 h-4" />, text: "Review my resume", agent: "Matcher" },
    { icon: <BarChart3 className="w-4 h-4" />, text: "What are current tech job market trends?", agent: "Stats" }
  ];

  const handleSendMessage = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isTyping) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Placeholder for AI streaming
    const aiMsgId = (Date.now() + 1).toString();
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true
    };
    setMessages(prev => [...prev, aiMsg]);

    try {
      const response = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText })
      });

      if (!response.body) throw new Error("No body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let finished = false;

      let fullContent = "";

      while (!finished) {
        const { value, done } = await reader.read();
        finished = done;
        if (value) {
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n").filter(l => l.trim());

          for (const line of lines) {
            try {
              const parsed = JSON.parse(line);
              if (parsed.type === 'chunk') {
                fullContent += parsed.data;
                setMessages(prev => prev.map(m =>
                  m.id === aiMsgId ? { ...m, content: fullContent } : m
                ));
              } else if (parsed.type === 'status') {
                setMessages(prev => prev.map(m =>
                  m.id === aiMsgId ? { ...m, content: parsed.data } : m
                ));
                fullContent = ""; // Reset since it was just a status
              } else if (parsed.type === 'done') {
                setMessages(prev => prev.map(m =>
                  m.id === aiMsgId ? { ...m, agent: parsed.agent, offersCount: parsed.offers_count, isStreaming: false } : m
                ));
              }
            } catch (e) {
              console.error("JSON parse error on chunk", line);
            }
          }
        }
      }
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId ? { ...m, content: "Sorry, I encountered an error connecting to the AI agent.", isStreaming: false } : m
      ));
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 h-[calc(100vh-4rem)]">
      <div className="flex flex-col h-full">
        {/* Messages Area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto mb-6 space-y-6 pr-2 custom-scrollbar">
          {messages.map((message) => (
            <div key={message.id} className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {message.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
              )}

              <div className={`max-w-2xl ${message.role === 'user' ? 'order-first' : ''}`}>
                <div className={`rounded-2xl px-6 py-4 ${message.role === 'user' ? 'bg-white text-black' : 'bg-zinc-900 border border-zinc-800'}`}>
                  <p className="whitespace-pre-line leading-relaxed">
                    {message.content}
                    {message.isStreaming && message.content.length === 0 && <Loader2 className="w-4 h-4 animate-spin inline ml-2" />}
                  </p>
                </div>
                {message.agent && (
                  <p className="text-xs text-zinc-600 mt-2 ml-2">Agent: {message.agent}</p>
                )}

                {message.offersCount && message.offersCount > 0 && (
                  <button
                    onClick={onNavigateToJobs}
                    className="mt-3 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm transition-colors animate-in fade-in slide-in-from-bottom-2"
                  >
                    <span>View {message.offersCount} Found Jobs</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                )}
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-bold">YOU</span>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Persistent Suggestions */}
        <div className="mb-4">
          <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar no-scrollbar">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(s.text)}
                className="flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-all text-left group whitespace-nowrap"
              >
                <div className="w-6 h-6 rounded bg-zinc-800 flex items-center justify-center group-hover:bg-zinc-700 transition-colors">
                  {s.icon}
                </div>
                <span className="text-xs text-zinc-300 font-medium">{s.text}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Input Area */}
        <div className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask about jobs, interviews, resume help, or career advice..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl px-6 py-4 pr-14 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-700 transition-all"
            disabled={isTyping}
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!input.trim() || isTyping}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-xl bg-white text-black flex items-center justify-center hover:bg-zinc-200 transition-colors disabled:opacity-50"
          >
            {isTyping ? <Loader2 className="w-4 h-4 animate-spin text-black" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
