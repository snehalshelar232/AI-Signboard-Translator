import React from 'react';
import { ArrowRight, Play, Loader2 } from 'lucide-react';

export default function LanguageSelector({
  languages,
  sourceLang,
  setSourceLang,
  targetLang,
  setTargetLang,
  onProcess,
  isProcessing,
  hasImage,
}) {
  return (
    <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="section-label">
        <span>Language Configuration</span>
      </div>

      <div className="controls-row">
        {/* Source Language */}
        <div className="form-group">
          <label className="form-label" htmlFor="source-lang-select">
            Source Signboard Script
          </label>
          <select
            id="source-lang-select"
            className="select-input"
            value={sourceLang}
            onChange={(e) => setSourceLang(e.target.value)}
            disabled={isProcessing}
          >
            <option value="auto">✨ Auto Detect Script</option>
            {Object.entries(languages).map(([code, info]) => (
              <option key={code} value={code}>
                {info.name} ({info.native})
              </option>
            ))}
          </select>
        </div>

        {/* Target Language */}
        <div className="form-group">
          <label className="form-label" htmlFor="target-lang-select">
            Destination Speech Language
          </label>
          <select
            id="target-lang-select"
            className="select-input"
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
            disabled={isProcessing}
          >
            {Object.entries(languages).map(([code, info]) => (
              <option key={code} value={code}>
                {info.name} ({info.native})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Primary Action Button */}
      <button
        type="button"
        id="btn-translate-signboard"
        className="btn-primary"
        onClick={onProcess}
        disabled={isProcessing || !hasImage}
      >
        {isProcessing ? (
          <>
            <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
            Processing AI Pipeline...
          </>
        ) : (
          <>
            <Play size={18} fill="#ffffff" />
            Translate & Synthesize Voice
          </>
        )}
      </button>
    </div>
  );
}
