import { useState, useEffect } from 'react';
import { Activity, Zap, Clock, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

interface AgentTrace {
    timestamp: string;
    agent: string;
    input: string;
    output: string;
    duration_ms: number;
    status: string;
}

interface AgentStats {
    total_executions: number;
    avg_duration_ms: number;
    success_rate: number;
    agent_breakdown: Record<string, number>;
}

export function AgentDashboard() {
    const [traces, setTraces] = useState<AgentTrace[]>([]);
    const [stats, setStats] = useState<AgentStats | null>(null);
    const [autoRefresh, setAutoRefresh] = useState(true);

    const fetchData = async () => {
        try {
            const [tracesRes, statsRes] = await Promise.all([
                fetch('http://localhost:8000/api/agent/traces'),
                fetch('http://localhost:8000/api/agent/stats')
            ]);
            const tracesData = await tracesRes.json();
            const statsData = await statsRes.json();
            setTraces(tracesData.traces || []);
            setStats(statsData);
        } catch (e) {
            console.error('Failed to fetch agent data', e);
        }
    };

    useEffect(() => {
        fetchData();
        if (autoRefresh) {
            const interval = setInterval(fetchData, 2000);
            return () => clearInterval(interval);
        }
    }, [autoRefresh]);

    const getAgentColor = (agent: string) => {
        const colors: Record<string, string> = {
            'Router': 'bg-purple-500/10 text-purple-400 border-purple-500/30',
            'Collector': 'bg-blue-500/10 text-blue-400 border-blue-500/30',
            'Analyzer': 'bg-green-500/10 text-green-400 border-green-500/30',
            'Matcher': 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
            'Writer': 'bg-pink-500/10 text-pink-400 border-pink-500/30',
            'RAG': 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
            'Parser': 'bg-orange-500/10 text-orange-400 border-orange-500/30'
        };
        return colors[agent] || 'bg-zinc-800 text-zinc-400 border-zinc-700';
    };

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
                        <Activity className="w-8 h-8 text-purple-400" />
                        Agent Workflow Dashboard
                    </h1>
                    <p className="text-zinc-400">Real-time visualization of agent execution</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`px-4 py-2 rounded-lg border transition-colors ${autoRefresh
                                ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                            }`}
                    >
                        {autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh OFF'}
                    </button>
                    <button
                        onClick={fetchData}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Refresh
                    </button>
                </div>
            </div>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                        <div className="flex items-center gap-3 mb-2">
                            <Zap className="w-5 h-5 text-yellow-400" />
                            <span className="text-sm text-zinc-500">Total Executions</span>
                        </div>
                        <p className="text-3xl font-bold">{stats.total_executions}</p>
                    </div>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                        <div className="flex items-center gap-3 mb-2">
                            <Clock className="w-5 h-5 text-blue-400" />
                            <span className="text-sm text-zinc-500">Avg Duration</span>
                        </div>
                        <p className="text-3xl font-bold">{stats.avg_duration_ms}ms</p>
                    </div>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                        <div className="flex items-center gap-3 mb-2">
                            <CheckCircle className="w-5 h-5 text-green-400" />
                            <span className="text-sm text-zinc-500">Success Rate</span>
                        </div>
                        <p className="text-3xl font-bold">{stats.success_rate}%</p>
                    </div>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                        <div className="flex items-center gap-3 mb-2">
                            <Activity className="w-5 h-5 text-purple-400" />
                            <span className="text-sm text-zinc-500">Active Agents</span>
                        </div>
                        <p className="text-3xl font-bold">{Object.keys(stats.agent_breakdown).length}</p>
                    </div>
                </div>
            )}

            {/* Agent Breakdown */}
            {stats && Object.keys(stats.agent_breakdown).length > 0 && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-8">
                    <h2 className="text-xl font-semibold mb-4">Agent Activity Breakdown</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {Object.entries(stats.agent_breakdown).map(([agent, count]) => (
                            <div key={agent} className={`px-4 py-3 rounded-lg border ${getAgentColor(agent)}`}>
                                <p className="text-sm font-medium">{agent}</p>
                                <p className="text-2xl font-bold">{count}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Trace Timeline */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
                <h2 className="text-xl font-semibold mb-4">Execution Timeline</h2>
                {traces.length === 0 ? (
                    <div className="text-center py-12">
                        <Activity className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
                        <p className="text-zinc-500">No agent executions yet</p>
                        <p className="text-sm text-zinc-600 mt-2">Trigger a job search or upload a CV to see agents in action</p>
                    </div>
                ) : (
                    <div className="space-y-3 max-h-[600px] overflow-y-auto">
                        {traces.slice().reverse().map((trace, idx) => (
                            <div key={idx} className="bg-black/30 border border-zinc-800 rounded-lg p-4 hover:border-zinc-600 transition-all">
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <span className={`px-3 py-1 rounded-lg border text-sm font-medium ${getAgentColor(trace.agent)}`}>
                                            {trace.agent}
                                        </span>
                                        <span className="text-xs text-zinc-600">
                                            {new Date(trace.timestamp).toLocaleTimeString()}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-zinc-500">{trace.duration_ms}ms</span>
                                        {trace.status === 'success' ? (
                                            <CheckCircle className="w-4 h-4 text-green-400" />
                                        ) : (
                                            <XCircle className="w-4 h-4 text-red-400" />
                                        )}
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <p className="text-zinc-600 mb-1">Input:</p>
                                        <p className="text-zinc-400 font-mono text-xs bg-black/50 p-2 rounded border border-zinc-800 truncate">
                                            {trace.input}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-zinc-600 mb-1">Output:</p>
                                        <p className="text-zinc-400 font-mono text-xs bg-black/50 p-2 rounded border border-zinc-800 truncate">
                                            {trace.output}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
