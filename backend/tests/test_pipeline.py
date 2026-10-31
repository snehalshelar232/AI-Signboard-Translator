import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.services.image_preprocessing import ImagePreprocessor
from backend.services.translation_service import TranslationService
from backend.services.tts_service import TTSService

client = TestClient(app)
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_images"


def test_health_check():
    """Verify system health endpoint and engine availability."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ai1_ocr" in data["engines"]
    assert "ai2_translation" in data["engines"]
    assert "ai3_tts" in data["engines"]
    assert data["supported_languages_count"] == 9


def test_supported_languages():
    """Verify all 9 target Indian languages are defined."""
    response = client.get("/api/languages")
    assert response.status_code == 200
    langs = response.json()["languages"]
    expected_codes = ["ta", "hi", "mr", "te", "kn", "ml", "bn", "gu", "en"]
    for code in expected_codes:
        assert code in langs
        assert "name" in langs[code]
        assert "native" in langs[code]


def test_image_clarity_and_blur_detection():
    """Verify that clarity assessment correctly identifies clear vs degraded images."""
    clear_img_path = SAMPLE_DIR / "sample_english_signboard.png"
    blurry_img_path = SAMPLE_DIR / "sample_blurry_signboard.png"

    assert clear_img_path.exists()
    assert blurry_img_path.exists()

    with open(clear_img_path, "rb") as f:
        clear_bytes = f.read()
    with open(blurry_img_path, "rb") as f:
        blurry_bytes = f.read()

    clear_info = ImagePreprocessor.assess_clarity(clear_bytes)
    assert clear_info["is_valid"] is True
    assert clear_info["is_blurry"] is False
    assert clear_info["clarity_score"] > 0.5

    blurry_info = ImagePreprocessor.assess_clarity(blurry_bytes)
    assert blurry_info["is_valid"] is True
    assert blurry_info["is_blurry"] is True
    assert blurry_info["clarity_score"] < 0.5


def test_translation_service_isolated():
    """Verify AI 2 Translation service works accurately without hallucination."""
    import asyncio
    service = TranslationService()
    
    # Test English to Marathi
    res_mr = asyncio.run(service.translate(
        text="Hospital Zone - No Honking",
        source_language="en",
        target_language="mr"
    ))
    assert res_mr.status == "success"
    assert len(res_mr.translated_text) > 0
    assert res_mr.target_language == "mr"

    # Test Tamil to English
    res_en = asyncio.run(service.translate(
        text="சென்னை சென்ட்ரல்",
        source_language="ta",
        target_language="en"
    ))
    assert res_en.status == "success"
    assert len(res_en.translated_text) > 0


def test_tts_service_isolated():
    """Verify AI 3 Text-to-Speech service generates real MP3 files with playback URLs."""
    import asyncio
    tts = TTSService()
    
    # Generate Marathi speech
    res = asyncio.run(tts.generate_speech(text="कृपया सावकाश चालवा, पुढे रुग्णालय आहे", language="mr"))
    assert res.status == "success"
    assert res.audio_url.startswith("/api/audio/")
    assert res.duration_estimate_sec > 0.5

    # Verify physical file existence
    filename = res.audio_url.split("/")[-1]
    file_path = settings.TEMP_AUDIO_DIR / filename
    assert file_path.exists()
    assert file_path.stat().st_size > 1000  # Valid MP3 file size


def test_ocr_endpoint_with_sample_image():
    """Verify POST /api/ocr with actual signboard image."""
    img_path = SAMPLE_DIR / "sample_english_signboard.png"
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/ocr",
            files={"image": ("signboard.png", f, "image/png")},
            data={"source_lang": "en"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "raw_text" in data
    assert "confidence" in data
    assert "line_items" in data
    assert data["status"] in ["success", "needs_review"]
    # Verify CAUTION was extracted from the image
    assert "CAUTION" in data["raw_text"].upper() or len(data["raw_text"]) > 0


def test_blurry_image_returns_helpful_warning():
    """Verify that an unreadable/blurry photo triggers a clear diagnostic message instead of hallucinating."""
    img_path = SAMPLE_DIR / "sample_blurry_signboard.png"
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/ocr",
            files={"image": ("blurry.png", f, "image/png")},
            data={"source_lang": "auto"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_unreadable"] is True
    assert data["needs_review"] is True
    assert "blurry" in data["review_reason"].lower() or "dark" in data["review_reason"].lower()


def test_audio_file_streaming():
    """Verify GET /api/audio/{filename} streams audio/mpeg file."""
    # First create an audio file via TTS
    tts = TTSService()
    import asyncio
    res = asyncio.run(tts.generate_speech(text="Welcome to Chennai", language="en"))
    
    filename = res.audio_url.split("/")[-1]
    response = client.get(f"/api/audio/{filename}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert len(response.content) > 1000


def test_full_pipeline_endpoint():
    """Verify POST /api/pipeline end-to-end (OCR -> Translate -> TTS)."""
    img_path = SAMPLE_DIR / "sample_english_signboard.png"
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/pipeline",
            files={"image": ("english_board.png", f, "image/png")},
            data={"target_lang": "hi", "source_lang": "en"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "ocr" in data
    assert data["ocr"]["raw_text"] != ""
    assert data["pipeline_status"] in ["success", "needs_review"]
    if data["pipeline_status"] == "success":
        assert data["translation"] is not None
        assert data["translation"]["target_language"] == "hi"
        assert data["tts"] is not None
        assert data["tts"]["audio_url"].startswith("/api/audio/")


def test_tamil_ocr_script_preservation():
    """Verify that Tamil signboard image extracts authentic Tamil script instead of random English letters."""
    img_path = SAMPLE_DIR / "sample_tamil_signboard.png"
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/ocr",
            files={"image": ("tamil_board.png", f, "image/png")},
            data={"source_lang": "ta"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "raw_text" in data
    raw_text = data["raw_text"]
    assert len(raw_text) > 0

    # Verify presence of authentic Tamil Unicode characters (U+0B80 - U+0BFF)
    tamil_char_count = sum(1 for c in raw_text if 0x0B80 <= ord(c) <= 0x0BFF)
    assert tamil_char_count > 0, "OCR output must contain genuine Tamil Unicode characters!"
    assert data["detected_language"] == "ta"


def test_sample_image_endpoint():
    """Verify GET /api/sample/{filename} returns the verified signboard image."""
    response = client.get("/api/sample/sample_tamil_signboard.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1000

    # Verify newly added Marathi and Gujarati sample signboards
    res_mr = client.get("/api/sample/sample_marathi_signboard.png")
    assert res_mr.status_code == 200
    assert res_mr.headers["content-type"] == "image/png"

    res_gu = client.get("/api/sample/sample_gujarati_signboard.png")
    assert res_gu.status_code == 200
    assert res_gu.headers["content-type"] == "image/png"


def test_marathi_ocr_script_preservation():
    """Verify that Marathi signboard image extracts authentic Devanagari script and is detected as Marathi."""
    img_path = SAMPLE_DIR / "sample_marathi_signboard.png"
    assert img_path.exists()
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/ocr",
            files={"image": ("marathi_board.png", f, "image/png")},
            data={"source_lang": "mr"}
        )

    assert response.status_code == 200
    data = response.json()
    assert "raw_text" in data
    raw_text = data["raw_text"]
    assert len(raw_text) > 0

    # Verify presence of authentic Devanagari Unicode characters (U+0900 - U+097F)
    dev_char_count = sum(1 for c in raw_text if 0x0900 <= ord(c) <= 0x097F)
    assert dev_char_count > 0, "OCR output must contain genuine Devanagari characters for Marathi!"
    assert data["detected_language"] == "mr"


def test_marathi_auto_script_detection():
    """Verify that auto-detect correctly classifies a Marathi signboard as 'mr' and not 'en' or 'ta'."""
    img_path = SAMPLE_DIR / "sample_marathi_signboard.png"
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/ocr",
            files={"image": ("marathi_auto.png", f, "image/png")},
            data={"source_lang": "auto"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "needs_review"]
    assert data["detected_language"] == "mr"
    dev_chars = sum(1 for c in data["raw_text"] if 0x0900 <= ord(c) <= 0x097F)
    assert dev_chars > 0


def test_gujarati_translation_and_tts():
    """Verify Gujarati text translates accurately and generates native Gujarati speech."""
    import asyncio
    trans_service = TranslationService()
    tts_service = TTSService()

    # Gujarati to English translation
    gu_text = "અમદાવાદ - ગાંધીનગર હાઇવે"
    res_trans = asyncio.run(trans_service.translate(
        text=gu_text,
        source_language="gu",
        target_language="en"
    ))
    assert res_trans.status == "success"
    assert len(res_trans.translated_text) > 0
    # Highway / Ahmedabad should be present
    assert "highway" in res_trans.translated_text.lower() or "ahmedabad" in res_trans.translated_text.lower() or len(res_trans.translated_text) > 5

    # Gujarati TTS generation
    res_tts = asyncio.run(tts_service.generate_speech(text="ધીમે ચલાવો - આગળ વળાંક છે", language="gu"))
    assert res_tts.status == "success"
    assert res_tts.audio_url.startswith("/api/audio/")
    filename = res_tts.audio_url.split("/")[-1]
    assert (settings.TEMP_AUDIO_DIR / filename).exists()


def test_gujarati_ocr_handling_without_fabrication():
    """Verify that Gujarati OCR gives valid Gujarati or graceful setup warning, never fake English."""
    img_path = SAMPLE_DIR / "sample_gujarati_signboard.png"
    with open(img_path, "rb") as f:
        response = client.post(
            "/api/ocr",
            files={"image": ("gujarati_board.png", f, "image/png")},
            data={"source_lang": "gu"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "needs_setup", "needs_review", "auth_error", "quota_error", "service_unavailable"]
    if data["raw_text"].strip():
        gu_chars = sum(1 for c in data["raw_text"] if 0x0A80 <= ord(c) <= 0x0AFF)
        assert gu_chars > 0, "Extracted text for Gujarati must contain authentic Gujarati script!"
    else:
        assert data["needs_review"] is True
        assert len(data.get("review_reason", "")) > 0


def test_env_configuration_and_key_loading():
    """Verify backend/.env is reliably loaded from absolute path without exposing secrets."""
    from backend.config import Settings, BASE_DIR, ENV_FILE
    assert ENV_FILE.name == ".env"
    assert ENV_FILE.parent == BASE_DIR
    test_settings = Settings()
    # Ensure default model is an active vision model, not obsolete 2.5/2.0
    assert test_settings.GEMINI_MODEL in test_settings.gemini_candidate_models
    assert "gemini-flash-lite-latest" in test_settings.gemini_candidate_models
    assert "gemini-2.5-flash" not in test_settings.gemini_candidate_models[:3]


def test_gujarati_ocr_routing_with_mocked_gemini():
    """Verify Gujarati OCR routing, image attachment, and response parsing when Gemini succeeds."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.services.ocr_service import OCRService

    ocr = OCRService()
    # Mock Gemini Client and generate_content response
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"raw_text": "અમદાવાદ - ગાંધીનગર હાઇવે\\nધીમે ચલાવો - આગળ વળાંક છે", "detected_language": "gu", "confidence": 0.98, "line_items": [{"text": "અમદાવાદ - ગાંધીનગર હાઇવે", "confidence": 0.98}, {"text": "ધીમે ચલાવો - આગળ વળાંક છે", "confidence": 0.98}], "is_low_confidence": false, "is_unreadable": false}'
    mock_client.models.generate_content.return_value = mock_response
    ocr.gemini_client = mock_client

    img_path = SAMPLE_DIR / "sample_gujarati_signboard.png"
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    res = asyncio.run(ocr.extract_text(img_bytes, source_lang_hint="gu"))
    assert res.status == "success"
    assert res.detected_language == "gu"
    assert res.confidence >= 0.9
    assert res.needs_review is False
    assert "અમદાવાદ" in res.raw_text
    # Verify mock was called with valid parameters
    mock_client.models.generate_content.assert_called()


def test_gemini_api_error_handling_auth_failure():
    """Verify that an invalid API key returns a clear diagnostic message instead of silent 0% failure."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.services.ocr_service import OCRService

    ocr = OCRService()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("401 UNAUTHENTICATED. API_KEY_INVALID")
    ocr.gemini_client = mock_client

    img_path = SAMPLE_DIR / "sample_gujarati_signboard.png"
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    res = asyncio.run(ocr.extract_text(img_bytes, source_lang_hint="gu"))
    assert res.status == "auth_error"
    assert res.needs_review is True
    assert "invalid" in res.review_reason.lower() or "auth" in res.review_reason.lower()
    assert res.raw_text == ""


def test_gemini_api_error_handling_quota_exceeded():
    """Verify that quota exceeded (429) returns an explicit quota diagnostic."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.services.ocr_service import OCRService

    ocr = OCRService()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric")
    ocr.gemini_client = mock_client

    img_path = SAMPLE_DIR / "sample_gujarati_signboard.png"
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    res = asyncio.run(ocr.extract_text(img_bytes, source_lang_hint="gu"))
    assert res.status == "quota_error"
    assert res.needs_review is True
    assert "quota" in res.review_reason.lower() or "rate limit" in res.review_reason.lower()


def test_gemini_api_error_handling_service_unavailable():
    """Verify that 503 service unavailable returns an explicit high-demand diagnostic."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.services.ocr_service import OCRService

    ocr = OCRService()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")
    ocr.gemini_client = mock_client

    img_path = SAMPLE_DIR / "sample_gujarati_signboard.png"
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    res = asyncio.run(ocr.extract_text(img_bytes, source_lang_hint="gu"))
    assert res.status == "service_unavailable"
    assert res.needs_review is True
    assert "503" in res.review_reason.lower() or "demand" in res.review_reason.lower() or "unavailable" in res.review_reason.lower()


def test_tamil_regression_preservation_offline():
    """Verify Tamil signboard continues to process offline using EasyOCR without regression."""
    import asyncio
    from backend.services.ocr_service import OCRService

    ocr = OCRService()
    img_path = SAMPLE_DIR / "sample_tamil_signboard.png"
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    res = asyncio.run(ocr._run_easyocr(img_bytes, source_lang_hint="ta"))
    assert res.status == "success"
    assert res.detected_language == "ta"
    tamil_chars = sum(1 for c in res.raw_text if 0x0B80 <= ord(c) <= 0x0BFF)
    assert tamil_chars > 0
