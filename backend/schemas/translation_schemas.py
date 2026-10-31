from pydantic import BaseModel, Field
from typing import List, Optional, Any

class LineItem(BaseModel):
    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    box: Optional[Any] = None

class OCRResponse(BaseModel):
    raw_text: str
    detected_language: str = "auto"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    line_items: List[LineItem] = []
    is_low_confidence: bool = False
    needs_review: bool = False
    review_reason: Optional[str] = None
    engine_used: str = "Unknown"
    secondary_engine_text: Optional[str] = None
    discrepancy_detected: bool = False
    clarity_score: float = 1.0
    is_unreadable: bool = False
    status: str = "success"

class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Original text to translate")
    source_language: Optional[str] = Field(default="auto", description="ISO code of source language or 'auto'")
    target_language: str = Field(..., min_length=2, max_length=5, description="ISO code of target language (e.g. 'en', 'mr', 'hi')")

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    engine_used: str
    status: str = "success"

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize to audio")
    language: str = Field(..., min_length=2, max_length=5, description="Target language code (e.g. 'ta', 'mr', 'en')")

class TTSResponse(BaseModel):
    audio_url: str
    language: str
    duration_estimate_sec: float
    status: str = "success"

class PipelineResponse(BaseModel):
    ocr: OCRResponse
    translation: Optional[TranslationResponse] = None
    tts: Optional[TTSResponse] = None
    pipeline_status: str = "success"
