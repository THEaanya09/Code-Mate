import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


CODEMATE_DIR = Path.home() / ".codemate"
CONFIG_FILE = CODEMATE_DIR / ".env"

DEFAULT_MODEL = "openai/gpt-oss-20b"


def ensure_config_dir():
    CODEMATE_DIR.mkdir(parents=True, exist_ok=True)


def load_codemate_config():
    """
    Load CodeMate configuration.

    Priority:
    1. Existing process environment variables
    2. ~/.codemate/.env
    """

    ensure_config_dir()

    if CONFIG_FILE.exists():
        load_dotenv(CONFIG_FILE, override=False)

    return {
        "api_key": os.getenv("GROQ_API_KEY"),
        "model": os.getenv("GROQ_MODEL", DEFAULT_MODEL),
    }


def save_config(api_key, model=DEFAULT_MODEL):
    """
    Save CodeMate configuration to ~/.codemate/.env
    """

    ensure_config_dir()

    content = (
        "# CodeMate configuration\n"
        "# Do not share this file or commit it to Git.\n\n"
        f"GROQ_API_KEY={api_key}\n"
        f"GROQ_MODEL={model}\n"
    )

    CONFIG_FILE.write_text(
        content,
        encoding="utf-8"
    )

    return CONFIG_FILE


def get_api_key():
    config = load_codemate_config()
    return config["api_key"]


def get_model():
    config = load_codemate_config()
    return config["model"]