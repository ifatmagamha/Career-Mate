from typing import Dict, Any, Optional
from src.config.logging import logger
from src.llm.port import llm, extract_json, prompt_version
from src.schemas.candidate import CandidateProfile

PARSER_SYSTEM_PROMPT = """
You are a professional CV segmentation and classification model. 
Your task is to extract information from the provided resume text and generate a valid JSON object following this EXACT schema:

{
    "Profile": {
        "full_name": "...",
        "email": "...",
        "phone": "...",
        "location": "...",
        "social_links": ["url1", "url2"]
    },
    "Summary": "Brief profile description or presentation",
    "Education": [
        {"degree": "...", "school": "...", "location": "...", "start_date": "...", "graduation_date": "..."}
    ],
    "Skills": ["skill1", "skill2"],
    "SoftSkills": ["soft_skill1", "language_level"],
    "WorkExperience": [
        {"company": "...", "role": "...", "start_date": "...", "end_date": "...", "description": "..."}
    ],
    "Projects": [
        {"name": "...", "date": "...", "description": "..."}
    ],
    "Certifications": [
        {"name": "...", "date": "...", "issuer": "..."}
    ],
    "VolunteerExperience": [
        {"organization": "...", "role": "...", "description": "..."}
    ]
}

RULES:
1. Store all relevant details: emails, social contacts, locations, URLs, and dates.
2. The Profile section MUST contain all personal contact info and social URLs.
3. The Summary MUST contain the profile description.
4. Skills are hard skills. SoftSkills include management skills and language levels.
5. Projects include academic or professional projects.
6. WorkExperience includes internships and professional roles.
7. STAY CONFORM: preserve information as written. Do not delete or elaborate.
8. Return ONLY the JSON object.
"""

def parse_resume_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Segments and classifies resume text into structured JSON.
    """
    try:
        content = llm.complete(
            [{"role": "system", "content": PARSER_SYSTEM_PROMPT},
             {"role": "user", "content": f"Resume Text:\n{text}"}],
            role="extract", prompt_version=prompt_version(PARSER_SYSTEM_PROMPT),
        )
        return extract_json(content)
    except Exception as e:
        logger.error(f"[parser] Error parsing resume: {e}")
        return None

def map_parsed_to_profile(parsed_data: Dict[str, Any], raw_text: str) -> CandidateProfile:
    """
    Maps the LLM output to the CandidateProfile Pydantic model.
    """
    profile = parsed_data.get("Profile", {})
    
    return CandidateProfile(
        full_name=profile.get("full_name"),
        email=profile.get("email"),
        phone=profile.get("phone"),
        location=profile.get("location"),
        cv_text=raw_text,
        summary=parsed_data.get("Summary"),
        skills=parsed_data.get("Skills", []),
        soft_skills=parsed_data.get("SoftSkills", []),
        experience=parsed_data.get("WorkExperience", []),
        education=parsed_data.get("Education", []),
        projects=parsed_data.get("Projects", []),
        certifications=parsed_data.get("Certifications", []),
        volunteer_experience=parsed_data.get("VolunteerExperience", [])
    )
