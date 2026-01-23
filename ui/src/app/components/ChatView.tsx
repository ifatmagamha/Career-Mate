import { useState } from 'react';
import { Send, Sparkles, TrendingUp, Briefcase, FileEdit, BarChart3, ArrowRight } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agent?: string;
  offersCount?: number;
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

  const suggestions = [
    {
      icon: <Briefcase className="w-4 h-4" />,
      text: "Find remote software dev jobs paying 80k+",
      agent: "Collector"
    },
    {
      icon: <TrendingUp className="w-4 h-4" />,
      text: "Help me prepare for Python interview",
      agent: "Analyzer"
    },
    {
      icon: <FileEdit className="w-4 h-4" />,
      text: "Review my resume",
      agent: "Matcher"
    },
    {
      icon: <BarChart3 className="w-4 h-4" />,
      text: "What are current tech job market trends?",
      agent: "Stats"
    }
  ];

  const handleSendMessage = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText })
      });

      if (!res.ok) throw new Error("API Error");

      const data = await res.json();

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        agent: data.agent || "RecruitAI",
        offersCount: data.offers_count
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (e) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "Sorry, I couldn't connect to the backend server. Make sure `src/api/server.py` is running.",
        timestamp: new Date(),
        agent: "System"
      };
      setMessages(prev => [...prev, errorMsg]);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 h-[calc(100vh-4rem)]">
      <div className="flex flex-col h-full">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto mb-6 space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {message.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
              )}

              <div className={`max-w-2xl ${message.role === 'user' ? 'order-first' : ''}`}>
                <div
                  className={`rounded-2xl px-6 py-4 ${message.role === 'user'
                    ? 'bg-white text-black'
                    : 'bg-zinc-900 border border-zinc-800'
                    }`}
                >
                  <p className="whitespace-pre-line leading-relaxed">{message.content}</p>
                </div>
                {message.agent && (
                  <p className="text-xs text-zinc-600 mt-2 ml-2">
                    Agent: {message.agent}
                  </p>
                )}

                {/* Action Button for Jobs */}
                {message.offersCount && message.offersCount > 0 && (
                  <button
                    onClick={onNavigateToJobs}
                    className="mt-3 flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                  >
                    <span>View {message.offersCount} Found Jobs</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                )}
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0">
                  <span className="text-sm">You</span>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Suggestions (only show at start) */}
        {messages.length <= 1 && (
          <div className="mb-6">
            <p className="text-sm text-zinc-500 mb-3">Quick actions:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {suggestions.map((suggestion, index) => (
                <button
                  key={index}
                  onClick={() => handleSendMessage(suggestion.text)}
                  className="flex items-center gap-3 p-4 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-all text-left group"
                >
                  <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center group-hover:bg-zinc-700 transition-colors">
                    {suggestion.icon}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm text-white">{suggestion.text}</p>
                    <p className="text-xs text-zinc-600 mt-1">Agent: {suggestion.agent}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask about jobs, interviews, resume help, or career advice..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl px-6 py-4 pr-14 text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!input.trim()}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 rounded-xl bg-white text-black flex items-center justify-center hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
