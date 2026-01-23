from typing import Dict
from src.schemas.candidate import CandidateProfile

# Start with an empty profile store.
# Profiles will be added upon upload.
MOCK_PROFILES: Dict[str, CandidateProfile] = {}
