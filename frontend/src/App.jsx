import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import PipelineStepper from './components/PipelineStepper';
import ImageUploader from './components/ImageUploader';
import LanguageSelector from './components/LanguageSelector';
import ResultsCard from './components/ResultsCard';
import { fetchHealth, fetchLanguages, submitOCR, submitTranslation, submitTTS } from './api';
import { AlertCircle, RotateCcw, Cpu } from 'lucide-react';

const DEFAULT_LANGUAGES = {
  ta: { name: 'Tamil', native: 'தமிழ்' },
  hi: { name: 'Hindi', native: 'हिन्दी' },
  mr: { name: 'Marathi', native: 'मराठी' },
  te: { name: 'Telugu', native: 'తెలుగు' },
  kn: { name: 'Kannada', native: 'ಕನ್ನಡ' },
  ml: { name: 'Malayalam', native: 'മലയാളം' },
  bn: { name: 'Bengali', native: 'বাংলা' },
  gu: { name: 'Gujarati', native: 'ગુજરાતી' },
  en: { name: 'English', native: 'English' },
};

export default function App() {
  const [languages, setLanguages] = useState(DEFAULT_LANGUAGES);
  const [systemHealth, setSystemHealth] = useState(null);

  // User input states
  const [selectedImage, setSelectedImage] = useState(null);
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('en');

  // Pipeline execution states
  const [currentStep, setCurrentStep] = useState(0); // 0=idle, 1=OCR, 2=Trans, 3=TTS, 4=Complete
  const [isProcessing, setIsProcessing] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Pipeline output states
  const [ocrData, setOcrData] = useState(null);
  const [editableText, setEditableText] = useState('');
  const [translationData, setTranslationData] = useState(null);
  const [audioData, setAudioData] = useState(null);

  // Initialize and load supported languages + health status
  useEffect(() => {
    async function loadInitialData() {
      try {
        const health = await fetchHealth();
        setSystemHealth(health);
      } catch (e) {
        console.warn('Backend health check pending or offline:', e.message);
      }

      try {
        const langData = await fetchLanguages();
        if (langData?.languages) {
          setLanguages(langData.languages);
        }
      } catch (e) {
        console.warn('Using default language dictionary:', e.message);
      }
    }
    loadInitialData();
  }, []);

  // Main 3-stage pipeline execution
  const handleProcessPipeline = async () => {
    if (!selectedImage) return;

    setIsProcessing(true);
    setErrorMessage(null);
    setTranslationData(null);
    setAudioData(null);

    try {
      // ----------------------------------------------------
      // STAGE 1: OCR & Image Understanding
      // ----------------------------------------------------
      setCurrentStep(1);
      const ocrResult = await submitOCR(selectedImage, sourceLang);
      setOcrData(ocrResult);
      setEditableText(ocrResult.raw_text);

      if (ocrResult.is_unreadable || !ocrResult.raw_text.trim()) {
        setCurrentStep(0);
        setIsProcessing(false);
        setErrorMessage(
          ocrResult.review_reason || 'Could not read any text on the signboard. Please ensure the signboard is in focus and well lit.'
        );
        return;
      }

      // If confidence is low or needs human review, prompt user in UI
      // but still proceed to translate if text is non-empty
      const textToTranslate = ocrResult.raw_text.trim();
      const detectedSource = ocrResult.detected_language !== 'unknown' ? ocrResult.detected_language : 'auto';

      // ----------------------------------------------------
      // STAGE 2: Context-Aware Translation
      // ----------------------------------------------------
      setCurrentStep(2);
      const transResult = await submitTranslation(textToTranslate, detectedSource, targetLang);
      setTranslationData(transResult);

      // ----------------------------------------------------
      // STAGE 3: Text-to-Speech Voiceover
      // ----------------------------------------------------
      if (transResult.translated_text.trim()) {
        setCurrentStep(3);
        const ttsResult = await submitTTS(transResult.translated_text, targetLang);
        setAudioData(ttsResult);
      }

      setCurrentStep(4); // All complete
    } catch (err) {
      console.error('Pipeline error:', err);
      setErrorMessage(err.message || 'An error occurred during AI processing.');
      setCurrentStep(0);
    } finally {
      setIsProcessing(false);
    }
  };

  // Re-translate when user manually edits OCR text
  const handleReTranslate = async () => {
    if (!editableText.trim()) return;

    setIsTranslating(true);
    setErrorMessage(null);

    try {
      const detectedSource = ocrData?.detected_language || 'auto';
      const transResult = await submitTranslation(editableText.trim(), detectedSource, targetLang);
      setTranslationData(transResult);

      if (transResult.translated_text.trim()) {
        const ttsResult = await submitTTS(transResult.translated_text, targetLang);
        setAudioData(ttsResult);
      }
    } catch (err) {
      console.error('Re-translation error:', err);
      setErrorMessage(err.message || 'Failed to re-translate edited text.');
    } finally {
      setIsTranslating(false);
    }
  };

  // Reset entire workspace
  const handleReset = () => {
    setSelectedImage(null);
    setCurrentStep(0);
    setIsProcessing(false);
    setIsTranslating(false);
    setErrorMessage(null);
    setOcrData(null);
    setEditableText('');
    setTranslationData(null);
    setAudioData(null);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <Header />

      {/* Interactive AI Pipeline Stepper */}
      <PipelineStepper currentStep={currentStep} error={errorMessage} />

      {/* Global Error Banner */}
      {errorMessage && (
        <div className="error-banner" style={{ marginBottom: '1.75rem' }}>
          <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div style={{ flex: 1 }}>
            <strong>Processing Alert:</strong> {errorMessage}
          </div>
          <button
            type="button"
            className="btn-browse"
            onClick={() => setErrorMessage(null)}
            style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="workspace-grid">
        {/* Left Column: Image Upload & Language Select */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <ImageUploader
            selectedImage={selectedImage}
            onImageSelected={(file) => {
              setSelectedImage(file);
              setErrorMessage(null);
              setOcrData(null);
              setTranslationData(null);
              setAudioData(null);
            }}
            onImageRemoved={() => {
              setSelectedImage(null);
              setOcrData(null);
              setTranslationData(null);
              setAudioData(null);
            }}
            isProcessing={isProcessing}
          />

          <LanguageSelector
            languages={languages}
            sourceLang={sourceLang}
            setSourceLang={setSourceLang}
            targetLang={targetLang}
            setTargetLang={setTargetLang}
            onProcess={handleProcessPipeline}
            isProcessing={isProcessing}
            hasImage={Boolean(selectedImage)}
          />

          {selectedImage && (
            <button
              type="button"
              className="btn-audio"
              onClick={handleReset}
              disabled={isProcessing}
              style={{ alignSelf: 'flex-start' }}
            >
              <RotateCcw size={14} />
              Reset All
            </button>
          )}
        </div>

        {/* Right Column: Results, Editable Text, Audio Player */}
        <div>
          <ResultsCard
            ocrData={ocrData}
            editableText={editableText}
            setEditableText={setEditableText}
            translationData={translationData}
            audioData={audioData}
            onReTranslate={handleReTranslate}
            isTranslating={isTranslating}
            targetLanguage={targetLang}
          />
        </div>
      </div>

      {/* Footer / System Status */}
      <footer className="project-footer">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Cpu size={14} color="#6366f1" />
            Active OCR: <span className="footer-highlight">{systemHealth?.engines?.ai1_ocr || 'EasyOCR (Local Offline)'}</span>
          </span>
          <span>•</span>
          <span>
            Translation: <span className="footer-highlight">{systemHealth?.engines?.ai2_translation || 'Indic Deep-Translator'}</span>
          </span>
          <span>•</span>
          <span>
            Speech: <span className="footer-highlight">gTTS Native MP3</span>
          </span>
        </div>
        <p>AI-to-AI: Smart Signboard Translation and Voice Assistant • College Final Year Engineering Project</p>
      </footer>
    </div>
  );
}
