import io
import os
import re
import json
import logging
import difflib
import shutil
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image

from ..config import settings
from ..schemas.translation_schemas import OCRResponse, LineItem
from .image_preprocessing import ImagePreprocessor

logger = logging.getLogger(__name__)

class OCRService:
    """
    AI-1: Signboard Image Understanding & Multilingual OCR.
    Uses an accuracy-first architecture:
    - Primary Engine: Gemini Vision OCR (when GEMINI_API_KEY is configured in .env)
    - Offline Local Engine: EasyOCR with patched Tamil dictionary and Devanagari (Marathi/Hindi) support
    - Optional Local Engine: Tesseract OCR (when installed with Gujarati 'guj' or Indic packs)
    - Multilingual script validation (Marathi, Gujarati, Tamil, Hindi, English)
    - Discrepancy detector & Human-in-the-loop review flag
    """

    def __init__(self):
        self.easyocr_readers: Dict[str, Any] = {}
        self.gemini_client = None
        self.tesseract_cmd = self._find_tesseract()
        self.tesseract_langs: List[str] = []
        self._init_tesseract()
        self._patch_easyocr_tamil()
        self._init_gemini_client()

    def _find_tesseract(self) -> Optional[str]:
        """Detects if Tesseract OCR binary is installed on the local system."""
        candidates = [
            settings.TESSERACT_PATH,
            os.environ.get("TESSERACT_CMD", ""),
            shutil.which("tesseract"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None

    def _init_tesseract(self):
        """Initializes pytesseract if binary is available."""
        if self.tesseract_cmd:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
                self.tesseract_langs = pytesseract.get_languages()
                logger.info(f"Tesseract OCR detected at {self.tesseract_cmd} with languages: {self.tesseract_langs}")
            except Exception as e:
                logger.warning(f"Tesseract initialization notice: {e}")
                self.tesseract_langs = []

    def _patch_easyocr_tamil(self):
        """
        Dynamically patches EasyOCR's generation 1 Tamil configuration dictionary.
        Upstream EasyOCR 1.7.2 has a bug where `config.py` omits 16 vowel signs and pulli
        from `tamil_g1['characters']`, causing a PyTorch layer shape mismatch (143 vs 127).
        This patch synchronizes the config with `ta_char.txt` (142 characters + 1 blank = 143),
        enabling native offline recognition of Tamil script.
        """
        try:
            import easyocr
            import easyocr.config as cfg
            base_path = os.path.dirname(os.path.abspath(easyocr.easyocr.__file__))
            char_file = os.path.join(base_path, 'character', 'ta_char.txt')
            if os.path.exists(char_file):
                with open(char_file, 'r', encoding='utf-8-sig') as f:
                    ta_chars = set(f.read().splitlines())
                config_chars = set(cfg.recognition_models['gen1']['tamil_g1']['characters'])
                all_ta_chars = ''.join(sorted(list(config_chars.union(ta_chars))))
                cfg.recognition_models['gen1']['tamil_g1']['characters'] = all_ta_chars
                logger.info("Successfully patched EasyOCR Tamil dictionary to 142 characters.")
        except Exception as e:
            logger.warning(f"Could not apply EasyOCR Tamil patch: {e}")

    def _init_gemini_client(self):
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini Vision Client successfully initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")
                self.gemini_client = None

    def _get_easyocr_reader(self, lang_code: str = "en") -> Any:
        """
        Loads EasyOCR readers with paired language sets and verbose=False.
        Supports:
        - Tamil: ['ta', 'en']
        - Marathi / Hindi: ['mr', 'hi', 'en'] (Devanagari script + English speed codes/numbers)
        - Telugu: ['te', 'en']
        - Kannada: ['kn', 'en']
        - Bengali: ['bn', 'en']
        - English: ['en']
        """
        if lang_code == "ta":
            lang_group = ["ta", "en"]
        elif lang_code in ["hi", "mr"]:
            # Including 'en' allows recognizing highway codes (e.g. NH-48) alongside Devanagari text
            lang_group = ["mr", "hi", "en"]
        elif lang_code == "te":
            lang_group = ["te", "en"]
        elif lang_code == "kn":
            lang_group = ["kn", "en"]
        elif lang_code == "bn":
            lang_group = ["bn", "en"]
        else:
            lang_group = ["en"]

        cache_key = "_".join(sorted(lang_group))
        if cache_key not in self.easyocr_readers:
            import easyocr
            logger.info(f"Loading EasyOCR reader for language group: {lang_group}")
            try:
                self.easyocr_readers[cache_key] = easyocr.Reader(lang_group, gpu=False, verbose=False)
            except Exception as e:
                logger.warning(f"EasyOCR reader init failed for {lang_group}: {e}. Falling back to English reader.")
                if "en" not in self.easyocr_readers:
                    self.easyocr_readers["en"] = easyocr.Reader(["en"], gpu=False, verbose=False)
                return self.easyocr_readers["en"]

        return self.easyocr_readers[cache_key]

    async def extract_text(self, image_bytes: bytes, source_lang_hint: str = "auto") -> OCRResponse:
        """
        Main OCR pipeline method:
        1. Evaluates image clarity (sharpness, lighting).
        2. Applies contrast-preserving preprocessing, resizing, and border trimming.
        3. Calls primary vision engine (Gemini if configured, or offline local OCR).
        4. Validates script fidelity (confirms authentic Marathi, Gujarati, Tamil characters).
        5. Triggers second-pass or human verification if confidence is low.
        """
        # Step 1: Image Clarity Assessment
        clarity_info = ImagePreprocessor.assess_clarity(image_bytes)
        if not clarity_info["is_valid"]:
            return OCRResponse(
                raw_text="",
                detected_language="unknown",
                confidence=0.0,
                is_low_confidence=True,
                needs_review=True,
                is_unreadable=True,
                review_reason="Uploaded file is not a valid image.",
                status="unreadable"
            )

        # Severely degraded or blurry image check
        if clarity_info["blur_score"] < 35.0 or (clarity_info["is_blurry"] and clarity_info["is_dark"]):
            return OCRResponse(
                raw_text="",
                detected_language="unknown",
                confidence=0.1,
                is_low_confidence=True,
                needs_review=True,
                is_unreadable=True,
                clarity_score=clarity_info["clarity_score"],
                review_reason="The signboard image is too blurry or low-contrast to extract text reliably. Please upload a clearer photograph.",
                status="unreadable"
            )

        # Step 2: Adaptive Preprocessing (upscaling small crops, CLAHE contrast, unsharp mask)
        clean_bytes, was_preprocessed = ImagePreprocessor.preprocess_if_needed(image_bytes)

        # Step 3: Run Primary OCR Engine
        if self.gemini_client:
            primary_result = await self._run_gemini_vision_ocr(clean_bytes, source_lang_hint)
        else:
            primary_result = await self._run_easyocr(clean_bytes, source_lang_hint)

        primary_result.clarity_score = clarity_info["clarity_score"]

        # Step 4: Script Validation (Ensures extracted text contains authentic script characters)
        is_valid_script, script_notes = self.validate_script(primary_result.raw_text, source_lang_hint, primary_result.detected_language)
        if not is_valid_script:
            primary_result.is_low_confidence = True
            primary_result.needs_review = True
            primary_result.review_reason = script_notes

            # If local OCR failed script validation and Gemini client is available, run second pass
            if self.gemini_client and not primary_result.engine_used.startswith("Gemini"):
                logger.info("Local OCR failed script validation. Triggering Gemini Vision second pass...")
                gemini_res = await self._run_gemini_vision_ocr(clean_bytes, source_lang_hint)
                if gemini_res.confidence > primary_result.confidence:
                    primary_result = gemini_res

        # Step 5: Secondary Engine Cross-Verification (when confidence is low or uncertain)
        if (
            self.gemini_client
            and (primary_result.confidence < settings.CONFIDENCE_THRESHOLD or primary_result.is_low_confidence)
            and primary_result.detected_language in settings.EASYOCR_SUPPORTED_LANGS
        ):
            try:
                secondary_result = await self._run_easyocr(clean_bytes, primary_result.detected_language)
                secondary_text = secondary_result.raw_text.strip()
                primary_result.secondary_engine_text = secondary_text

                similarity = difflib.SequenceMatcher(None, primary_result.raw_text.lower(), secondary_text.lower()).ratio()
                if similarity < (1.0 - settings.DISCREPANCY_THRESHOLD):
                    primary_result.discrepancy_detected = True
                    primary_result.needs_review = True
                    primary_result.review_reason = (
                        f"Primary and secondary recognition models differ (match score: {int(similarity*100)}%). "
                        "Please verify the text in the edit box before proceeding."
                    )
            except Exception as e:
                logger.warning(f"Secondary OCR check skipped: {e}")

        # Set human-in-the-loop review flag if confidence is below threshold
        if primary_result.confidence < settings.CONFIDENCE_THRESHOLD:
            primary_result.is_low_confidence = True
            primary_result.needs_review = True
            if not primary_result.review_reason:
                primary_result.review_reason = f"OCR confidence ({int(primary_result.confidence*100)}%) is below optimal threshold. Please confirm or edit the text."

        return primary_result

    def validate_script(self, text: str, source_lang_hint: str, detected_lang: str) -> Tuple[bool, Optional[str]]:
        """
        Validates that extracted text contains genuine Unicode characters of the target language script
        and is not random English garbage or misclassified noise.
        """
        clean_text = text.strip()
        if not clean_text:
            return True, None

        target_check = source_lang_hint if source_lang_hint != "auto" else detected_lang
        alpha_chars = sum(1 for c in clean_text if c.isalpha())

        if target_check == "ta":
            # Check for Tamil Unicode Block (U+0B80 - U+0BFF)
            tamil_chars = sum(1 for c in clean_text if 0x0B80 <= ord(c) <= 0x0BFF)
            if alpha_chars > 0 and tamil_chars == 0:
                return False, "Warning: The extracted text does not contain valid Tamil characters. The signboard text may be distorted or in an unsupported font. Please verify or edit text manually."

        elif target_check in ["hi", "mr"]:
            # Check for Devanagari Unicode Block (U+0900 - U+097F)
            dev_chars = sum(1 for c in clean_text if 0x0900 <= ord(c) <= 0x097F)
            if alpha_chars > 0 and dev_chars == 0:
                return False, f"Warning: The extracted text does not contain valid Devanagari characters for {settings.SUPPORTED_LANGUAGES.get(target_check, {}).get('name', 'selected language')}. Please verify or edit text manually."

        elif target_check == "gu":
            # Check for Gujarati Unicode Block (U+0A80 - U+0AFF)
            gu_chars = sum(1 for c in clean_text if 0x0A80 <= ord(c) <= 0x0AFF)
            if alpha_chars > 0 and gu_chars == 0:
                return False, "Warning: The extracted text does not contain valid Gujarati characters. Please verify or edit text manually."

        return True, None

    async def _run_gemini_vision_ocr(self, image_bytes: bytes, source_lang_hint: str) -> OCRResponse:
        """
        Uses Google Gemini Vision as high-precision multimodal vision OCR.
        Explicit prompt grounds recognition strictly to physically visible text
        in Marathi (Devanagari), Gujarati, Tamil, Hindi, or English.
        """
        try:
            from google.genai import types

            prompt = """
You are an expert Optical Character Recognition (OCR) engine for Indian road signboards and public signs.
Analyze this signboard photograph and extract the exact visible text.

STRICT INSTRUCTIONS:
1. Extract ONLY text physically visible in the image.
2. DO NOT correct spelling, guess cut-off letters, or invent missing words.
3. DO NOT translate the text. Return it in its exact original script:
   - Marathi in Devanagari script (मराठी)
   - Gujarati in Gujarati script (ગુજરાતી)
   - Tamil in Tamil script (தமிழ்)
   - Hindi in Devanagari script (हिन्दी)
   - English in Latin script
4. Preserve numbers, highway codes (e.g. NH-48, NE-1, SH-15), distances (km), arrows, and punctuation.
5. If some characters are partially obscured or unreadable, mark them with [?].
6. Accurately identify the source language code:
   - "mr" for Marathi (Devanagari script with Marathi vocabulary like सावकाश, शाळा, आहे, चौक, महामार्ग, or letter ळ)
   - "gu" for Gujarati (Gujarati script)
   - "ta" for Tamil (Tamil script)
   - "hi" for Hindi (Devanagari script with Hindi vocabulary)
   - "en" for English (Latin script)
   - or "te", "kn", "ml", "bn" for other Indic languages.
   CRITICAL: If the text is in Gujarati script, detected_language MUST be "gu".
   If the text is in Devanagari with Marathi words or character ळ, detected_language MUST be "mr".
   Do NOT classify Devanagari or Gujarati text as "en".
7. If the image contains zero readable text, return "is_unreadable": true.
8. Return a valid JSON object matching this schema:
{
  "raw_text": "all recognized text preserved with original line breaks",
  "detected_language": "mr, gu, ta, hi, en, te, kn, ml, or bn",
  "confidence": 0.95,
  "line_items": [
    {"text": "Line 1 text", "confidence": 0.95},
    {"text": "Line 2 text", "confidence": 0.90}
  ],
  "is_low_confidence": false,
  "is_unreadable": false
}
"""
            # Attach image with verified MIME type
            if image_bytes.startswith(b"\x89PNG"):
                mime_type = "image/png"
            elif image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

            # Use active multimodal vision models from settings
            models_to_try = settings.gemini_candidate_models

            response = None
            last_err = None
            used_model = "Gemini Vision OCR"

            for model_name in models_to_try:
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=[image_part, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0  # Zero temperature for deterministic grounding
                        )
                    )
                    if response and response.text:
                        used_model = f"Gemini ({model_name}) Vision OCR"
                        break
                except Exception as err:
                    last_err = err
                    logger.warning(f"Gemini model {model_name} failed: {err}. Trying next candidate...")

            if not response or not response.text:
                raise last_err or RuntimeError("Gemini API returned empty response across all candidate models.")

            # Clean JSON string (remove possible markdown backticks)
            clean_json_str = response.text.strip()
            if clean_json_str.startswith("```"):
                clean_json_str = re.sub(r"^```(?:json)?\s*", "", clean_json_str)
                clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

            try:
                result_json = json.loads(clean_json_str)
            except Exception:
                result_json = {
                    "raw_text": clean_json_str,
                    "detected_language": source_lang_hint if source_lang_hint != "auto" else "gu",
                    "confidence": 0.85,
                    "line_items": [{"text": l, "confidence": 0.85} for l in clean_json_str.split("\n") if l.strip()]
                }

            raw_text = result_json.get("raw_text", "").strip()
            detected_lang = result_json.get("detected_language", "en").strip().lower()

            # Script ground-truth validation for detected language code
            if detected_lang in ["auto", "unknown", "devanagari", "en"]:
                detected_lang = self._detect_script(raw_text, source_lang_hint)

            line_items = [
                LineItem(text=item.get("text", ""), confidence=float(item.get("confidence", 1.0)))
                for item in result_json.get("line_items", [])
            ]

            conf = float(result_json.get("confidence", 0.95))
            is_low_conf = bool(result_json.get("is_low_confidence", False)) or conf < settings.CONFIDENCE_THRESHOLD

            return OCRResponse(
                raw_text=raw_text,
                detected_language=detected_lang,
                confidence=conf,
                line_items=line_items,
                is_low_confidence=is_low_conf,
                needs_review=is_low_conf,
                engine_used=used_model,
                is_unreadable=bool(result_json.get("is_unreadable", False)),
                status="success" if not result_json.get("is_unreadable", False) else "unreadable"
            )
        except Exception as e:
            err_str = str(e)
            logger.error(f"Gemini OCR error: {err_str}")

            # Diagnose specific API failure cause
            if "401" in err_str or "403" in err_str or "API_KEY_INVALID" in err_str or ("key" in err_str.lower() and "invalid" in err_str.lower()):
                diagnostic_reason = "Gemini API key is invalid or unauthorized. Please verify GEMINI_API_KEY in backend/.env."
                api_status = "auth_error"
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                diagnostic_reason = "Gemini API rate limit or quota exceeded. Please wait a moment before retrying."
                api_status = "quota_error"
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                diagnostic_reason = "Gemini Vision service is temporarily experiencing high demand (503). Please retry in a few moments."
                api_status = "service_unavailable"
            elif "404" in err_str or "NOT_FOUND" in err_str:
                diagnostic_reason = "The requested Gemini model is not supported for this API key tier."
                api_status = "model_not_found"
            elif "connect" in err_str.lower() or "timeout" in err_str.lower() or "network" in err_str.lower():
                diagnostic_reason = "Network connection to Gemini API failed. Please check your internet connection."
                api_status = "network_error"
            else:
                diagnostic_reason = f"Gemini Vision API error: {err_str[:160]}"
                api_status = "api_error"

            # If Gujarati image, do NOT silently fall back to EasyOCR (which lacks Gujarati models)
            if source_lang_hint == "gu":
                if self.tesseract_cmd and "guj" in self.tesseract_langs:
                    logger.info("Falling back to local Tesseract OCR for Gujarati...")
                    return await self._run_tesseract(image_bytes, "guj", "gu")
                return OCRResponse(
                    raw_text="",
                    detected_language="gu",
                    confidence=0.0,
                    is_low_confidence=True,
                    needs_review=True,
                    engine_used="Gemini Vision OCR (API Error)",
                    status=api_status,
                    review_reason=f"{diagnostic_reason} You can type or correct the Gujarati text manually in the box below."
                )

            # For other languages (Tamil, Marathi, English) or auto, attempt local EasyOCR fallback
            fallback_res = await self._run_easyocr(image_bytes, source_lang_hint)
            if fallback_res.is_low_confidence or fallback_res.is_unreadable or not fallback_res.raw_text.strip():
                fallback_res.review_reason = f"{diagnostic_reason} Local OCR fallback could not read the text clearly. Please verify or edit manually."
            return fallback_res

    async def _run_easyocr(self, image_bytes: bytes, source_lang_hint: str) -> OCRResponse:
        """
        Runs local offline OCR:
        - Accurately supports Marathi (Devanagari), Tamil, Hindi, and English.
        - When source_lang_hint is 'auto', intelligently detects whether the signboard
          is in Devanagari (Marathi/Hindi), Tamil, or English, instead of hardcoding to Tamil.
        - If Gujarati is requested offline without Tesseract, provides a helpful setup guide.
        """
        try:
            # Check for Gujarati offline handling
            if source_lang_hint == "gu":
                if self.tesseract_cmd and "guj" in self.tesseract_langs:
                    return await self._run_tesseract(image_bytes, "guj", "gu")
                else:
                    return OCRResponse(
                        raw_text="",
                        detected_language="gu",
                        confidence=0.0,
                        is_low_confidence=True,
                        needs_review=True,
                        engine_used="Local OCR Engine Notice",
                        status="needs_setup",
                        review_reason=(
                            "Gujarati script recognition requires Gemini Vision API (add GEMINI_API_KEY to backend/.env) "
                            "or local Tesseract OCR with 'guj' language pack. You can also manually type or correct "
                            "the signboard text in the edit box to proceed."
                        )
                    )

            image = Image.open(io.BytesIO(image_bytes))
            import numpy as np
            image_np = np.array(image.convert("RGB"))

            # Determine candidate readers to execute
            if source_lang_hint in ["mr", "hi"]:
                readers_to_try = [("mr", self._get_easyocr_reader("mr"))]
            elif source_lang_hint == "ta":
                readers_to_try = [("ta", self._get_easyocr_reader("ta"))]
            elif source_lang_hint == "en":
                readers_to_try = [("en", self._get_easyocr_reader("en"))]
            elif source_lang_hint == "auto":
                # Multi-script auto-detection: try Devanagari first, then Tamil
                readers_to_try = [
                    ("mr", self._get_easyocr_reader("mr")),
                    ("ta", self._get_easyocr_reader("ta")),
                ]
            else:
                readers_to_try = [(source_lang_hint, self._get_easyocr_reader(source_lang_hint))]

            best_response = None
            highest_indic_count = -1

            for lang_tag, reader in readers_to_try:
                results = reader.readtext(image_np)
                if not results:
                    continue

                extracted_lines = []
                line_items = []
                confidences = []

                for (bbox, text, conf) in results:
                    clean_text = text.strip()
                    if clean_text:
                        extracted_lines.append(clean_text)
                        conf_float = round(float(conf), 2)
                        confidences.append(conf_float)
                        box_coords = [[int(pt[0]), int(pt[1])] for pt in bbox]
                        line_items.append(LineItem(text=clean_text, confidence=conf_float, box=box_coords))

                full_text = "\n".join(extracted_lines)
                avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

                # Detect script and language from extracted text
                detected_lang = self._detect_script(full_text, source_lang_hint if source_lang_hint != "auto" else lang_tag)
                is_low_conf = avg_confidence < settings.CONFIDENCE_THRESHOLD

                # Count authentic Indic characters to evaluate reader quality
                if lang_tag in ["mr", "hi"]:
                    indic_count = sum(1 for c in full_text if 0x0900 <= ord(c) <= 0x097F)
                elif lang_tag == "ta":
                    indic_count = sum(1 for c in full_text if 0x0B80 <= ord(c) <= 0x0BFF)
                else:
                    indic_count = 0

                resp = OCRResponse(
                    raw_text=full_text,
                    detected_language=detected_lang,
                    confidence=avg_confidence,
                    line_items=line_items,
                    is_low_confidence=is_low_conf,
                    needs_review=is_low_conf,
                    engine_used="EasyOCR (Local Offline)",
                    status="success"
                )

                # If this reader recognized genuine Indic characters of its target script, select it
                if indic_count > 0 and indic_count > highest_indic_count:
                    best_response = resp
                    highest_indic_count = indic_count
                    # Found genuine script characters matching target language
                    break
                elif best_response is None or avg_confidence > best_response.confidence:
                    best_response = resp

            if best_response and best_response.raw_text.strip():
                return best_response

            # If Tesseract is available and has Gujarati, check as fallback
            if self.tesseract_cmd and "guj" in self.tesseract_langs and source_lang_hint in ["auto", "gu"]:
                tess_res = await self._run_tesseract(image_bytes, "guj", "gu")
                if tess_res.raw_text.strip():
                    return tess_res

            return OCRResponse(
                raw_text="",
                detected_language=source_lang_hint if source_lang_hint != "auto" else "unknown",
                confidence=0.0,
                is_low_confidence=True,
                needs_review=True,
                engine_used="EasyOCR (Local Offline)",
                status="unreadable",
                review_reason="No readable text detected on the signboard. Please ensure good lighting and clear focus."
            )

        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return OCRResponse(
                raw_text="",
                detected_language="unknown",
                confidence=0.0,
                is_low_confidence=True,
                needs_review=True,
                engine_used="EasyOCR (Local Offline)",
                status="error",
                review_reason=f"OCR execution failed: {str(e)}"
            )

    async def _run_tesseract(self, image_bytes: bytes, tess_lang: str, output_lang_code: str) -> OCRResponse:
        """Runs Tesseract OCR when installed on the system."""
        try:
            import pytesseract
            image = Image.open(io.BytesIO(image_bytes))
            data = pytesseract.image_to_data(image, lang=tess_lang, output_type=pytesseract.Output.DICT)
            lines = []
            confidences = []
            line_items = []
            current_line = []
            current_conf = []

            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                conf = float(data['conf'][i])
                if word:
                    current_line.append(word)
                    if conf > 0:
                        current_conf.append(conf / 100.0)
                if data['word_num'][i] == 0 and current_line:
                    line_str = " ".join(current_line)
                    lines.append(line_str)
                    avg_c = round(sum(current_conf) / len(current_conf), 2) if current_conf else 0.7
                    confidences.append(avg_c)
                    line_items.append(LineItem(text=line_str, confidence=avg_c))
                    current_line = []
                    current_conf = []

            if current_line:
                line_str = " ".join(current_line)
                lines.append(line_str)
                avg_c = round(sum(current_conf) / len(current_conf), 2) if current_conf else 0.7
                confidences.append(avg_c)
                line_items.append(LineItem(text=line_str, confidence=avg_c))

            full_text = "\n".join(lines).strip()
            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.75
            is_low_conf = avg_conf < settings.CONFIDENCE_THRESHOLD

            return OCRResponse(
                raw_text=full_text,
                detected_language=output_lang_code,
                confidence=avg_conf,
                line_items=line_items,
                is_low_confidence=is_low_conf,
                needs_review=is_low_conf,
                engine_used=f"Tesseract OCR ({tess_lang})",
                status="success" if full_text else "unreadable"
            )
        except Exception as e:
            logger.warning(f"Tesseract OCR execution error: {e}")
            return OCRResponse(
                raw_text="",
                detected_language=output_lang_code,
                confidence=0.0,
                is_low_confidence=True,
                needs_review=True,
                engine_used="Tesseract OCR",
                status="error",
                review_reason=f"Tesseract execution error: {str(e)}"
            )

    def _detect_script(self, text: str, hint: str = "auto") -> str:
        """
        Determines the dominant Unicode script block and language in recognized text.
        Accurately differentiates Marathi (Devanagari) vs Hindi (Devanagari),
        Gujarati (Gujarati script), Tamil (Tamil script), and English.
        """
        counts = {
            'ta': 0,
            'dev': 0,
            'gu': 0,
            'te': 0,
            'kn': 0,
            'ml': 0,
            'bn': 0,
            'en': 0,
        }

        for char in text:
            cp = ord(char)
            if 0x0B80 <= cp <= 0x0BFF:
                counts['ta'] += 1
            elif 0x0900 <= cp <= 0x097F:
                counts['dev'] += 1
            elif 0x0A80 <= cp <= 0x0AFF:
                counts['gu'] += 1
            elif 0x0C00 <= cp <= 0x0C7F:
                counts['te'] += 1
            elif 0x0C80 <= cp <= 0x0CFF:
                counts['kn'] += 1
            elif 0x0D00 <= cp <= 0x0D7F:
                counts['ml'] += 1
            elif 0x0980 <= cp <= 0x09FF:
                counts['bn'] += 1
            elif char.isascii() and char.isalpha():
                counts['en'] += 1

        # Check for Indic scripts first
        indic_counts = {k: v for k, v in counts.items() if k != 'en' and v > 0}
        if not indic_counts:
            if counts['en'] > 0:
                return "en"
            return "en" if hint == "auto" else hint

        dominant_script = max(indic_counts.items(), key=lambda item: item[1])[0]

        # For Devanagari script: Differentiate Marathi vs Hindi
        if dominant_script == 'dev':
            if hint in ["mr", "hi"]:
                return hint

            # Letter 'ळ' (U+0933 Retroflex L) is uniquely Marathi (e.g. शाळा, वेळ, काळजी)
            if 'ळ' in text or '\u0933' in text:
                return "mr"

            # Check for distinctive Marathi road and signboard vocabulary
            mr_markers = {
                'आहे', 'आहेत', 'नाही', 'नाहीत', 'आणि', 'करा', 'करावे', 'सावकाश',
                'मार्ग', 'रस्ता', 'चौक', 'महानगरपालिका', 'पालिका', 'प्रवेश',
                'मनाई', 'थांबा', 'पुढील', 'पुढे', 'मागे', 'येथे', 'वाहन', 'वाहने',
                'चालवा', 'रुग्णालय', 'शाळा', 'चा', 'ची', 'चे', 'च्या', 'राखा',
                'वेगमर्यादा', 'द्रुतगती'
            }
            hi_markers = {
                'है', 'हैं', 'नहीं', 'और', 'करें', 'कीजिए', 'करना', 'आगे',
                'पीछे', 'यहाँ', 'अस्पताल', 'धीरे', 'चलें', 'का', 'की', 'के',
                'में', 'से', 'को', 'गति'
            }

            words = set(re.findall(r'[\u0900-\u097F]+', text))
            mr_matches = len(words.intersection(mr_markers))
            hi_matches = len(words.intersection(hi_markers))

            if mr_matches > hi_matches:
                return "mr"
            elif hi_matches > mr_matches:
                return "hi"

            # Default to Marathi if hint was mr, otherwise mr as primary Devanagari regional upgrade
            return "mr" if hint == "mr" else ("hi" if hint == "hi" else "mr")

        return dominant_script
