import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .schemas.translation_schemas import (
    OCRResponse,
    TranslationRequest,
    TranslationResponse,
    TTSRequest,
    TTSResponse,
    PipelineResponse,
)
from .services.ocr_service import OCRService
from .services.translation_service import TranslationService
from .services.tts_service import TTSService

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("smart-signboard-translator")

# Initialize FastAPI App
app = FastAPI(
    title="AI-to-AI: Smart Signboard Translation and Voice Assistant",
    description="Multilingual pipeline for real-world signboard recognition, Indic translation, and natural voice synthesis.",
    version="2.0.0"
)

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev and student presentation
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI Service Singletons
ocr_service = OCRService()
translation_service = TranslationService()
tts_service = TTSService()


@app.get("/api/health", summary="System Health & Available AI Engines")
async def health_check():
    """
    Returns the operational status of the 3 AI stages and active model engines.
    """
    return {
        "status": "healthy",
        "service": "AI-to-AI Signboard Translator API",
        "engines": {
            "ai1_ocr": "Gemini 2.5 Flash Vision OCR" if settings.GEMINI_API_KEY else "EasyOCR (Local Offline)",
            "ai2_translation": "Gemini Contextual Translation" if settings.GEMINI_API_KEY else "Indic Deep-Translator",
            "ai3_tts": "Google Text-to-Speech (gTTS) Native MP3",
        },
        "gemini_api_configured": bool(settings.GEMINI_API_KEY),
        "supported_languages_count": len(settings.SUPPORTED_LANGUAGES),
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
    }


@app.get("/api/languages", summary="List Supported Indian Languages")
async def get_languages():
    """
    Returns supported source and target languages with English and native script names.
    """
    return {
        "languages": settings.SUPPORTED_LANGUAGES,
        "default_source": "auto",
        "default_target": "en"
    }


@app.post("/api/ocr", response_model=OCRResponse, summary="AI 1: Signboard Text Recognition")
async def process_ocr(
    image: UploadFile = File(...),
    source_lang: str = Form("auto")
):
    """
    Processes an uploaded signboard photograph:
    - Preprocesses image if noisy/dark
    - Extracts visible text using primary vision model or local OCR
    - Evaluates confidence and flags uncertain or blurry text for user review
    """
    # Validate file type
    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {image.content_type}. Please upload an image (JPEG, PNG, WebP)."
        )

    # Read image contents
    image_bytes = await image.read()
    if len(image_bytes) > settings.MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image size exceeds the maximum limit of 15 MB."
        )

    logger.info(f"Received OCR request: {image.filename} ({len(image_bytes)} bytes), hint: {source_lang}")
    ocr_result = await ocr_service.extract_text(image_bytes, source_lang)
    return ocr_result


@app.post("/api/translate", response_model=TranslationResponse, summary="AI 2: Context-Aware Translation")
async def process_translation(request: TranslationRequest):
    """
    Translates verified signboard text into the selected target language.
    Preserves proper nouns, route codes, and warnings.
    """
    logger.info(f"Received translation request from {request.source_language} to {request.target_language}")
    result = await translation_service.translate(
        text=request.text,
        source_language=request.source_language or "auto",
        target_language=request.target_language
    )
    return result


@app.post("/api/tts", response_model=TTSResponse, summary="AI 3: Text-to-Speech Synthesis")
async def process_tts(request: TTSRequest):
    """
    Synthesizes natural speech audio in the selected target language.
    """
    logger.info(f"Received TTS request for {len(request.text)} characters in {request.language}")
    try:
        result = await tts_service.generate_speech(
            text=request.text,
            language=request.language
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis error: {str(e)}"
        )


@app.post("/api/pipeline", response_model=PipelineResponse, summary="Full End-to-End AI Pipeline")
async def run_full_pipeline(
    image: UploadFile = File(...),
    target_lang: str = Form("en"),
    source_lang: str = Form("auto")
):
    """
    Runs the complete 3-stage AI pipeline:
    1. AI 1: Signboard OCR
    2. Check if human-in-the-loop review is needed:
       - If OCR is uncertain, stops and returns OCR result with needs_review=True
    3. AI 2: Translation
    4. AI 3: Voiceover generation
    """
    # Stage 1: OCR
    image_bytes = await image.read()
    ocr_res = await ocr_service.extract_text(image_bytes, source_lang)

    # If unreadable, stop immediately
    if ocr_res.is_unreadable or not ocr_res.raw_text.strip():
        return PipelineResponse(
            ocr=ocr_res,
            translation=None,
            tts=None,
            pipeline_status="unreadable"
        )

    # If confidence is below threshold, return OCR result so user can review in UI
    if ocr_res.needs_review:
        return PipelineResponse(
            ocr=ocr_res,
            translation=None,
            tts=None,
            pipeline_status="needs_review"
        )

    # Stage 2: Translation
    detected_source = ocr_res.detected_language if ocr_res.detected_language != "unknown" else "auto"
    trans_res = await translation_service.translate(
        text=ocr_res.raw_text,
        source_language=detected_source,
        target_language=target_lang
    )

    # Stage 3: TTS
    tts_res = None
    if trans_res.translated_text.strip():
        try:
            tts_res = await tts_service.generate_speech(
                text=trans_res.translated_text,
                language=target_lang
            )
        except Exception as e:
            logger.warning(f"Pipeline TTS failed: {e}")

    return PipelineResponse(
        ocr=ocr_res,
        translation=trans_res,
        tts=tts_res,
        pipeline_status="success"
    )


@app.get("/api/audio/{filename}", summary="Stream Generated Audio File")
async def get_audio_file(filename: str):
    """
    Streams an audio file from the temporary audio cache.
    """
    file_path = settings.TEMP_AUDIO_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found or expired."
        )

    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=filename
    )


@app.get("/api/sample/{filename}", summary="Get Sample Signboard Image")
async def get_sample_image(filename: str):
    """
    Serves a verified sample signboard image from backend/sample_images.
    """
    file_path = settings.SAMPLE_IMAGES_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample image not found."
        )

    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        filename=filename
    )
