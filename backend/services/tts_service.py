import os
import time
import uuid
import logging
from pathlib import Path
from gtts import gTTS

from ..config import settings
from ..schemas.translation_schemas import TTSResponse

logger = logging.getLogger(__name__)

class TTSService:
    """
    AI-3: Multilingual Text-to-Speech Engine.
    - Synthesizes clear native speech in the chosen target language script.
    - Verified support for: Tamil, Hindi, Marathi, Telugu, Kannada, Malayalam, Bengali, Gujarati, English.
    - Automatically manages and cleans up temporary audio files.
    """

    # Verified gTTS language mappings
    GTTS_LANG_MAP = {
        "ta": "ta",
        "hi": "hi",
        "mr": "mr",
        "te": "te",
        "kn": "kn",
        "ml": "ml",
        "bn": "bn",
        "gu": "gu",
        "en": "en",
    }

    def __init__(self):
        # Trigger an initial cleanup on startup
        self.cleanup_old_audio()

    async def generate_speech(self, text: str, language: str) -> TTSResponse:
        """
        Synthesizes speech from translated text and returns the streaming audio URL.
        """
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Cannot synthesize audio from empty text.")

        gtts_lang = self.GTTS_LANG_MAP.get(language, "en")
        
        # Clean up any markdown or bracketed notes before sending to TTS
        clean_for_speech = clean_text.replace("[?]", "").replace("*", "").strip()
        if not clean_for_speech:
            clean_for_speech = clean_text

        filename = f"{uuid.uuid4().hex}.mp3"
        file_path = settings.TEMP_AUDIO_DIR / filename

        try:
            # Generate speech using gTTS
            tts = gTTS(text=clean_for_speech, lang=gtts_lang, slow=False)
            tts.save(str(file_path))

            # Estimate duration based on word count (average speaking speed: ~2.2 words per second)
            words = len(clean_for_speech.split())
            estimated_duration = max(round(words / 2.2, 1), 1.0)

            audio_url = f"/api/audio/{filename}"

            logger.info(f"Synthesized {gtts_lang} audio: {filename} (~{estimated_duration}s)")
            return TTSResponse(
                audio_url=audio_url,
                language=language,
                duration_estimate_sec=estimated_duration,
                status="success"
            )

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise RuntimeError(f"Text-to-speech synthesis failed: {str(e)}")

    def cleanup_old_audio(self, max_age_seconds: int = 3600):
        """
        Deletes temporary MP3 files older than 1 hour to prevent disk leakage.
        """
        now = time.time()
        try:
            for item in settings.TEMP_AUDIO_DIR.glob("*.mp3"):
                if item.is_file():
                    file_age = now - item.stat().st_mtime
                    if file_age > max_age_seconds:
                        item.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Audio cleanup warning: {e}")
