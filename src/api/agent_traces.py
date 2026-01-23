from fastapi import APIRouter
from typing import List, Dict, Any
from datetime import datetime
import json
from pathlib import Path

router = APIRouter()

# In-memory trace storage (for demo - in production use Redis/DB)
agent_traces: List[Dict[str, Any]] = []

def log_agent_trace(agent_name: str, input_data: Any, output_data: Any, duration_ms: float, status: str = "success"):
    """Log an agent execution trace for visualization"""
    trace = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "input": str(input_data)[:200],  # Truncate for display
        "output": str(output_data)[:200],
        "duration_ms": duration_ms,
        "status": status
    }
    agent_traces.append(trace)
    # Keep only last 50 traces
    if len(agent_traces) > 50:
        agent_traces.pop(0)
    return trace

@router.get("/api/agent/traces")
def get_agent_traces():
    """Get recent agent execution traces"""
    return {"traces": agent_traces}

@router.get("/api/agent/stats")
def get_agent_stats():
    """Get aggregated agent statistics"""
    if not agent_traces:
        return {
            "total_executions": 0,
            "avg_duration_ms": 0,
            "success_rate": 0,
            "agent_breakdown": {}
        }
    
    total = len(agent_traces)
    successful = sum(1 for t in agent_traces if t["status"] == "success")
    avg_duration = sum(t["duration_ms"] for t in agent_traces) / total
    
    # Count by agent
    agent_counts = {}
    for trace in agent_traces:
        agent = trace["agent"]
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    
    return {
        "total_executions": total,
        "avg_duration_ms": round(avg_duration, 2),
        "success_rate": round((successful / total) * 100, 2),
        "agent_breakdown": agent_counts
    }

@router.delete("/api/agent/traces")
def clear_traces():
    """Clear all traces"""
    agent_traces.clear()
    return {"status": "cleared"}
