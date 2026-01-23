from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class Application(BaseModel):
    id: str
    title: str
    company: str
    location: str
    salary: str = "$0"
    matchScore: int = 0
    stage: str = "saved"
    appliedDate: str = datetime.now().strftime("%b %d, %Y")

# In-memory storage for applications
MOCK_APPLICATIONS: Dict[str, Application] = {
    "1": Application(
        id="1",
        title="Senior Data Scientist",
        company="Google",
        location="Remote",
        salary="$120k - $160k",
        matchScore=92,
        stage="interviewing",
        appliedDate="Jan 20, 2026"
    ),
    "2": Application(
        id="2",
        title="ML Engineer",
        company="OpenAI",
        location="San Francisco",
        salary="$150k - $200k",
        matchScore=88,
        stage="applied",
        appliedDate="Jan 18, 2026"
    )
}
