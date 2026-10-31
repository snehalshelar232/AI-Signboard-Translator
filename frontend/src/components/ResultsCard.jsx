import React from 'react';
import { AlertTriangle, CheckCircle, Edit3, ArrowRight, RefreshCw, Sparkles, Volume2 } from 'lucide-react';
import AudioPlayer from './AudioPlayer';

const SCRIPT_LABELS = {
  mr: 'Marathi (मराठी)',
  gu: 'Gujarati (ગુજરાતી)',
  ta: 'Tamil (தமிழ்)',
  hi: 'Hindi (हिन्दी)',
  en: 'English (Latin)',
  te: 'Telugu (తెలుగు)',
  kn: 'Kannada (ಕನ್ನಡ)',
  ml: 'Malayalam (മലയാളം)',
  bn: 'Bengali (বাংলা)',
};

export default function ResultsCard({
  ocrData,
  editableText,
  setEditableText,
  translationData,
  audioData,
  onReTranslate,
  isTranslating,
  targetLanguage,
}) {
  if (!ocrData) {
    return (
      <div className="results-card glass-panel" style={{ justifyContent: 'center', alignItems: 'center', textAlign: 'center', minHeight: '380px', color: '#64748b' }}>
        <Sparkles size={40} style={{ opacity: 0.3, marginBottom: '0.75rem' }} />
        <h3 style={{ color: '#94a3b8', fontSize: '1.1rem', marginBottom: '0.25rem' }}>
          No Signboard Processed Yet
        </h3>
        <p style={{ fontSize: '0.85rem', maxWidth: '320px' }}>
          Upload or drag an Indian signboard photo on the left and click "Translate & Synthesize Voice".
        </p>
      </div>
    );
  }

  const confidencePct = Math.round((ocrData.confidence || 0) * 100);
  const isHighConf = confidencePct >= 70 && !ocrData.needs_review;

  return (
    <div className="results-card glass-panel">
      <div className="section-label">
        <span>AI Extraction & Translation Results</span>
        <span className={`confidence-chip ${isHighConf ? 'chip-high' : 'chip-warning'}`}>
          {isHighConf ? <CheckCircle size={12} style={{ display: 'inline', marginRight: '4px' }} /> : <AlertTriangle size={12} style={{ display: 'inline', marginRight: '4px' }} />}
          OCR Confidence: {confidencePct}%
        </span>
      </div>

      {/* Uncertainty or Review Warning Banner */}
      {ocrData.needs_review && (
        <div className="warning-banner">
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong>Human Verification Recommended:</strong>{' '}
            {ocrData.review_reason || 'Uncertain characters detected. Please verify or correct the extracted text below before translating.'}
          </div>
        </div>
      )}

      {/* Secondary Recognition Cross-Check Note */}
      {ocrData.secondary_engine_text && (
        <div style={{ fontSize: '0.8rem', color: '#94a3b8', background: 'rgba(255, 255, 255, 0.04)', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
          <strong>Secondary Engine Reading:</strong> <em>{ocrData.secondary_engine_text}</em>
        </div>
      )}

      {/* Section 1: Original Extracted Text (Editable) */}
      <div className="form-group editable-box">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Edit3 size={13} />
            Original Text Extracted from Signboard (Editable)
          </label>
          <span style={{ fontSize: '0.75rem', color: '#38bdf8', fontWeight: 600 }}>
            Script: {SCRIPT_LABELS[ocrData.detected_language] || ocrData.detected_language?.toUpperCase() || 'AUTO'}
          </span>
        </div>

        <textarea
          className="textarea-field"
          value={editableText}
          onChange={(e) => setEditableText(e.target.value)}
          placeholder="Extracted text will appear here. You can manually edit any unclear words."
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.4rem' }}>
          <button
            type="button"
            className="btn-audio"
            onClick={onReTranslate}
            disabled={isTranslating || !editableText.trim()}
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
          >
            <RefreshCw size={13} className={isTranslating ? 'spin-icon' : ''} style={{ animation: isTranslating ? 'spin 1s linear infinite' : 'none' }} />
            Update & Re-Translate
          </button>
        </div>
      </div>

      {/* Section 2: Translated Output */}
      {translationData && (
        <div className="form-group">
          <label className="form-label">
            Translated Signboard Text ({targetLanguage?.toUpperCase() || 'EN'})
          </label>
          <div className="translation-display">
            {translationData.translated_text || 'Translation in progress...'}
          </div>
        </div>
      )}

      {/* Section 3: Audio Voiceover Player */}
      {audioData && (
        <AudioPlayer
          audioUrl={audioData.audio_url}
          targetLanguage={targetLanguage}
          translatedText={translationData?.translated_text}
        />
      )}
    </div>
  );
}
