import React from 'react';
import { Sparkles, Languages, Volume2, ShieldCheck } from 'lucide-react';

export default function Header() {
  return (
    <header className="header-section">
      <div className="badge-row">
        <span className="badge badge-ai">
          <Sparkles size={13} /> Multi-AI Sequential Pipeline
        </span>
        <span className="badge badge-indic">
          <Languages size={13} /> 9 Indian Languages
        </span>
        <span className="badge badge-accuracy">
          <ShieldCheck size={13} /> Human-in-the-Loop Verification
        </span>
      </div>

      <h1 className="app-title">
        AI-to-AI: Smart Signboard Translation
      </h1>
      <p className="app-subtitle">
        <span className="tagline-accent">Capture. Translate. Listen.</span> Helping travelers navigate unfamiliar states with high-accuracy signboard OCR, contextual translation, and natural voice output.
      </p>
    </header>
  );
}
