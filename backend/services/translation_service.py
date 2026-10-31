import logging
from typing import Optional
from deep_translator import MyMemoryTranslator, GoogleTranslator

from ..config import settings
from ..schemas.translation_schemas import TranslationResponse

logger = logging.getLogger(__name__)

class TranslationService:
    """
    AI-2: Context-Aware Signboard Translation Engine.
    - Preserves place names, road numbers, warnings, and directions.
    - Uses Gemini 2.5 Flash when configured (best contextual preservation).
    - Falls back to MyMemory / Google Indic Translation when offline or keyless.
    """

    # Language code mapping for MyMemory
    MYMEMORY_LOCALE_MAP = {
        "en": "en-GB",
        "ta": "ta-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
        "te": "te-IN",
        "kn": "kn-IN",
        "ml": "ml-IN",
        "bn": "bn-IN",
        "gu": "gu-IN",
    }

    def __init__(self):
        self.gemini_client = None
        self._init_gemini_client()

    def _init_gemini_client(self):
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"Translation Gemini client failed: {e}")
                self.gemini_client = None

    async def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "en"
    ) -> TranslationResponse:
        """
        Translates extracted signboard text into target language.
        """
        clean_text = text.strip()
        if not clean_text:
            return TranslationResponse(
                original_text="",
                translated_text="",
                source_language=source_language,
                target_language=target_language,
                engine_used="None",
                status="error"
            )

        # Validate target language
        if target_language not in settings.SUPPORTED_LANGUAGES:
            target_language = "en"

        # If source and target are the same, return as is
        if source_language != "auto" and source_language == target_language:
            return TranslationResponse(
                original_text=clean_text,
                translated_text=clean_text,
                source_language=source_language,
                target_language=target_language,
                engine_used="Identity (No translation needed)",
                status="success"
            )

        # Strategy 1: Gemini Context-Aware Translation (when API key is present)
        if self.gemini_client:
            try:
                translated = await self._translate_with_gemini(clean_text, source_language, target_language)
                return TranslationResponse(
                    original_text=clean_text,
                    translated_text=translated,
                    source_language=source_language,
                    target_language=target_language,
                    engine_used="Gemini 2.5 Flash Translation",
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Gemini translation failed: {e}. Falling back to Indic translator.")

        # Strategy 2: Deep-Translator (MyMemory / GoogleTranslator)
        try:
            translated = await self._translate_with_indic_engine(clean_text, source_language, target_language)
            return TranslationResponse(
                original_text=clean_text,
                translated_text=translated,
                source_language=source_language,
                target_language=target_language,
                engine_used="Indic Deep-Translator",
                status="success"
            )
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return TranslationResponse(
                original_text=clean_text,
                translated_text=clean_text,
                source_language=source_language,
                target_language=target_language,
                engine_used="Fallback Raw",
                status="error"
            )

    async def _translate_with_gemini(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translates text with explicit instruction to preserve Indian road navigation context.
        Supports model fallback across Gemini 2.5 Flash, 2.0 Flash, and 1.5 Flash.
        """
        target_name = settings.SUPPORTED_LANGUAGES.get(target_lang, {}).get("name", target_lang)
        source_name = settings.SUPPORTED_LANGUAGES.get(source_lang, {}).get("name", "the original language")

        prompt = f"""
You are a professional signboard and road navigation translator.
Translate the following signboard text from {source_name} to {target_name}.

CRITICAL RULES:
1. Translate meaning accurately for a traveler reading a real road signboard or shop sign.
2. PRESERVE proper place names (e.g., Mumbai, Pune, Nagpur, Ahmedabad, Surat, Vadodara, Rajkot, Chennai, Madurai, Bengaluru).
3. PRESERVE highway numbers (e.g., NH-48, NE-1, SH-15), building names, and room/floor numbers.
4. PRESERVE road instructions and warnings accurately (e.g. "Slow Down", "One Way", "No Parking", "Hospital Ahead", "School Ahead").
5. Return ONLY the translated text in {target_name}. Do NOT add explanations, notes, or quotes.

Signboard Text to Translate:
{text}
"""
        models_to_try = settings.gemini_candidate_models

        last_err = None
        for model_name in models_to_try:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_err = e
                logger.warning(f"Translation model {model_name} failed: {e}")

        raise last_err or RuntimeError("Gemini translation returned empty response.")

    async def _translate_with_indic_engine(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translates using MyMemory or Google Translator with line-by-line fallback and locale resolution.
        """
        import re

        # If source is auto, detect script to provide concrete locale (e.g. mr-IN, gu-IN, ta-IN)
        src_code = source_lang
        if src_code in ["auto", "autodetect", "unknown"]:
            src_code = self._detect_text_lang(text)

        lines = text.split("\n")
        translated_lines = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                translated_lines.append("")
                continue

            # First attempt: MyMemory (very reliable for short phrases without IP rate-limiting)
            line_translated = None
            try:
                src_locale = self.MYMEMORY_LOCALE_MAP.get(src_code, "auto")
                tgt_locale = self.MYMEMORY_LOCALE_MAP.get(target_lang, "en-GB")
                raw_translation = MyMemoryTranslator(source=src_locale, target=tgt_locale).translate(line_str)
                if raw_translation and not raw_translation.startswith("MYMEMORY WARNING"):
                    # Strip any translation memory 'Tag:' prefixes
                    cleaned = re.sub(r'^(?:tag|Tag|TAG):\s*', '', raw_translation).strip()
                    if cleaned:
                        line_translated = cleaned
            except Exception:
                pass

            # Second attempt: GoogleTranslator
            if not line_translated:
                try:
                    gt_src = "auto" if src_code in ["auto", "autodetect"] else src_code
                    gt_res = GoogleTranslator(source=gt_src, target=target_lang).translate(line_str)
                    if gt_res:
                        line_translated = gt_res.strip()
                except Exception:
                    line_translated = line_str  # Preserve original line if translation fails

            translated_lines.append(line_translated or line_str)

        return "\n".join(translated_lines)

    def _detect_text_lang(self, text: str) -> str:
        """Helper to identify source language code for translation locale mapping."""
        for c in text:
            cp = ord(c)
            if 0x0A80 <= cp <= 0x0AFF:
                return "gu"
            elif 0x0B80 <= cp <= 0x0BFF:
                return "ta"
            elif 0x0900 <= cp <= 0x097F:
                if 'ळ' in text or '\u0933' in text:
                    return "mr"
                # Check Marathi markers
                mr_markers = {'आहे', 'सावकाश', 'शाळा', 'मार्ग', 'चौक', 'पुढील', 'चालवा', 'द्रुतगती'}
                words = set(text.split())
                if words.intersection(mr_markers):
                    return "mr"
                return "mr"  # Default Devanagari to Marathi
            elif 0x0C00 <= cp <= 0x0C7F:
                return "te"
            elif 0x0C80 <= cp <= 0x0CFF:
                return "kn"
            elif 0x0D00 <= cp <= 0x0D7F:
                return "ml"
            elif 0x0980 <= cp <= 0x09FF:
                return "bn"
        return "en"
