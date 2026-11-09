"""
Single source of truth for loading system prompts across pipeline stages.
Always resolves absolute paths to config/system_prompts.
Fails loudly if a prompt file is missing or empty.
"""
from pathlib import Path
from app.config.constants import SYSTEM_PROMPTS_DIR


def get_system_prompt_path(filename: str) -> Path:
    """
    Resolves the absolute path to a system prompt file.
    Raises FileNotFoundError if the file does not exist.
    """
    if SYSTEM_PROMPTS_DIR.exists():
        prompt_path = SYSTEM_PROMPTS_DIR / filename
        if prompt_path.exists():
            return prompt_path

    # Fallback to resolving relative to this module
    base_dir = Path(__file__).resolve().parent.parent.parent
    prompt_path = base_dir / "config" / "system_prompts" / filename
    if prompt_path.exists():
        return prompt_path

    raise FileNotFoundError(
        f"Required system prompt file not found: '{filename}'. "
        f"Looked in: {SYSTEM_PROMPTS_DIR} and {base_dir / 'config' / 'system_prompts'}"
    )


def load_system_prompt(filename: str) -> str:
    """
    Loads and returns the text content of a system prompt file.
    Raises FileNotFoundError if missing, or ValueError if empty.
    """
    path = get_system_prompt_path(filename)
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"System prompt file is empty: {path}")
    return content
