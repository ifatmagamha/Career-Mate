from pathlib import Path
from src.config.settings import settings

def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt file from src/prompts directory.
    prompt_name should include extension (e.g., 'analyzer.md')
    """
    prompt_name = prompt_name.strip()
    if not prompt_name.endswith(".md"):
        prompt_name += ".md"

    try:
        # Assuming run from root
        path = Path("src/prompts") / prompt_name
        if not path.exists():
            # Fallback for different CWD
            path = Path(settings.PROJECT_ROOT) / "src" / "prompts" / prompt_name
            
        return path.read_text(encoding="utf-8").strip()
    except Exception as e:
        raise RuntimeError(f"Could not load prompt {prompt_name}: {e}")
