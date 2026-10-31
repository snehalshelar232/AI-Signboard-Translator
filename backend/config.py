import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Base directory for the backend (absolute path)
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = (BASE_DIR / ".env").resolve()

# Load .env file reliably from absolute path, overriding any stale environment variables
if ENV_FILE.is_file():
    load_dotenv(dotenv_path=ENV_FILE, override=True)

class Settings:
    # Server settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # AI Model Keys & Options
    # Google Gemini API key: Free at https://aistudio.google.com
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip() or "gemini-flash-lite-latest"
    TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", "").strip()

    @property
    def gemini_candidate_models(self) -> List[str]:
        """
        Returns active multimodal vision models in priority order.
        Filters out obsolete models like gemini-2.5-flash and gemini-2.0-flash that return 404.
        """
        active_defaults = [
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-flash-latest",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
        ]
        models: List[str] = []
        user_model = self.GEMINI_MODEL.strip()
        if user_model and user_model not in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            models.append(user_model)
        for m in active_defaults:
            if m not in models:
                models.append(m)
        return models
    
    # OCR Confidence Thresholds (0.0 to 1.0)
    # Below this score, the user is prompted to verify and edit the extracted text
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
    
    # Secondary Engine Discrepancy Threshold (0.0 to 1.0)
    # If primary and secondary engines differ by more than this ratio, flag for human review
    DISCREPANCY_THRESHOLD: float = float(os.getenv("DISCREPANCY_THRESHOLD", "0.35"))

    # Storage paths
    TEMP_AUDIO_DIR: Path = BASE_DIR / "temp_audio"
    SAMPLE_IMAGES_DIR: Path = BASE_DIR / "sample_images"

    # Supported Languages with Display Names and Native Script
    SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
        "ta": {"name": "Tamil", "native": "தமிழ்", "script": "Tamil"},
        "hi": {"name": "Hindi", "native": "हिन्दी", "script": "Devanagari"},
        "mr": {"name": "Marathi", "native": "मराठी", "script": "Devanagari"},
        "te": {"name": "Telugu", "native": "తెలుగు", "script": "Telugu"},
        "kn": {"name": "Kannada", "native": "ಕನ್ನಡ", "script": "Kannada"},
        "ml": {"name": "Malayalam", "native": "മലയാളം", "script": "Malayalam"},
        "bn": {"name": "Bengali", "native": "বাংলা", "script": "Bengali"},
        "gu": {"name": "Gujarati", "native": "ગુજરાતી", "script": "Gujarati"},
        "en": {"name": "English", "native": "English", "script": "Latin"},
    }

    # EasyOCR language mapping (Only languages with verified local models)
    EASYOCR_SUPPORTED_LANGS: List[str] = ["en", "ta", "hi", "mr", "te", "kn", "bn"]

    # Maximum image upload size: 15 MB
    MAX_IMAGE_SIZE_BYTES: int = 15 * 1024 * 1024

settings = Settings()

# Ensure directories exist
settings.TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
settings.SAMPLE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
