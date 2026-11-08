"""
Application-wide constants and default values.
"""
from pathlib import Path

APP_NAME = "PromptBeast"
APP_DISPLAY_NAME = "PromptBeast — Story-to-Image Prompt & Timeline Studio"
APP_VERSION = "1.0.0"

# Root directories
APP_ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT_DIR = APP_ROOT_DIR.parent
CONFIG_DIR = PROJECT_ROOT_DIR / "config"
if not CONFIG_DIR.exists():
    if Path("/root/config").exists():
        CONFIG_DIR = Path("/root/config")
    elif Path("config").exists():
        CONFIG_DIR = Path("config").resolve()

SUBJECTS_DIR = CONFIG_DIR / "subjects"
STYLES_DIR = CONFIG_DIR / "visual_styles"
SYSTEM_PROMPTS_DIR = CONFIG_DIR / "system_prompts"
MODELS_FILE = CONFIG_DIR / "models.json"

# Defaults
DEFAULT_MODAL_API_URL = "https://joybenny3333--omnivoice-studio-fastapi-app.modal.run"
DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_MIN_DURATION = 3.0
DEFAULT_PREFERRED_DURATION = 4.5
DEFAULT_MAX_DURATION = 6.0
DEFAULT_BATCH_SIZE = 10
DEFAULT_TARGET_IMAGE_COUNT = 30
