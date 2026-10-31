/**
 * API Service for AI-to-AI Signboard Translator.
 * Connects frontend to the FastAPI backend endpoints.
 */

const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return await res.json();
}

export async function fetchLanguages() {
  const res = await fetch(`${API_BASE}/languages`);
  if (!res.ok) throw new Error(`Failed to fetch languages (${res.status})`);
  return await res.json();
}

export async function submitOCR(imageFile, sourceLang = 'auto') {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('source_lang', sourceLang);

  const res = await fetch(`${API_BASE}/ocr`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `OCR failed with status ${res.status}`);
  }

  return await res.json();
}

export async function submitTranslation(text, sourceLang, targetLang) {
  const res = await fetch(`${API_BASE}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      source_language: sourceLang || 'auto',
      target_language: targetLang,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Translation failed with status ${res.status}`);
  }

  return await res.json();
}

export async function submitTTS(text, language) {
  const res = await fetch(`${API_BASE}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      language,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Speech synthesis failed with status ${res.status}`);
  }

  return await res.json();
}

export async function submitFullPipeline(imageFile, targetLang = 'en', sourceLang = 'auto') {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('target_lang', targetLang);
  formData.append('source_lang', sourceLang);

  const res = await fetch(`${API_BASE}/pipeline`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Pipeline execution failed with status ${res.status}`);
  }

  return await res.json();
}
