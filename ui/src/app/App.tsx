import { useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '@/app/api';
import { Login } from '@/app/components/Login';
import { JobExplorer, toJob } from '@/app/components/JobExplorer';
import { JobDetail } from '@/app/components/JobDetail';
import { GeneratorView } from '@/app/components/GeneratorView';
import { ProfileView } from '@/app/components/ProfileView';
import {
  Briefcase,
  FileText,
  User,
  Sparkles,
  LogOut
} from 'lucide-react';

type View = 'jobs' | 'generator' | 'profile' | 'jobDetail';

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
  stage?: 'wishlist' | 'applied' | 'interviewing' | 'offer';
}

function App() {
  const [currentView, setCurrentView] = useState<View>('jobs');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [initialJobDescription, setInitialJobDescription] = useState<string>('');
  // undefined = still reading the stored session; null = signed out
  const [session, setSession] = useState<Session | null | undefined>(supabase ? undefined : null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  const handleJobSelect = (job: Job) => {
    setSelectedJob(job);
    setCurrentView('jobDetail');
  };

  const handleBackToJobs = () => {
    setCurrentView('jobs');
    setSelectedJob(null);
  };

  const handleGenerateFromJob = (desc: string) => {
    setInitialJobDescription(desc);
    setCurrentView('generator');
  };

  const renderView = () => {
    switch (currentView) {
      case 'jobs':
        return <JobExplorer onJobSelect={handleJobSelect} />;
      case 'jobDetail':
        return <JobDetail
          job={selectedJob}
          onBack={handleBackToJobs}
          onGenerateCoverLetter={handleGenerateFromJob}
          onUpdated={(offer) => setSelectedJob(toJob(offer) as any)}
        />;
      case 'generator':
        return <GeneratorView initialDescription={initialJobDescription} />;
      case 'profile':
        return <ProfileView />;
      default:
        return <JobExplorer onJobSelect={handleJobSelect} />;
    }
  };

  if (supabase && session === undefined) return <div className="min-h-screen bg-black" />;
  if (supabase && !session) return <Login />;

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Top Navigation */}
      <nav className="border-b border-zinc-800 bg-black/50 backdrop-blur-sm fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-semibold">Career Mate AI</span>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center gap-2">
              <NavButton
                icon={<Briefcase className="w-4 h-4" />}
                label="Job Explorer"
                active={currentView === 'jobs' || currentView === 'jobDetail'}
                onClick={() => setCurrentView('jobs')}
              />
              <NavButton
                icon={<FileText className="w-4 h-4" />}
                label="AI Generator"
                active={currentView === 'generator'}
                onClick={() => setCurrentView('generator')}
              />
              <NavButton
                icon={<User className="w-4 h-4" />}
                label="Profile"
                active={currentView === 'profile'}
                onClick={() => setCurrentView('profile')}
              />
              {supabase && session && (
                <button
                  onClick={() => supabase!.auth.signOut()}
                  title={`Sign out ${session.user.email ?? ''}`}
                  aria-label="Sign out"
                  className="ml-2 p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-900"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="pt-16">
        {renderView()}
      </main>
    </div>
  );
}

interface NavButtonProps {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}

function NavButton({ icon, label, active, onClick }: NavButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-4 py-2 rounded-lg transition-all
        ${active
          ? 'bg-white text-black'
          : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
        }
      `}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  );
}

export default App;
