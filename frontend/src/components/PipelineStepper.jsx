import React from 'react';
import { Eye, Languages, Volume2, CheckCircle2, Loader2 } from 'lucide-react';

export default function PipelineStepper({ currentStep, error }) {
  // currentStep: 0 (idle), 1 (OCR), 2 (Translation), 3 (TTS), 4 (Complete)

  const steps = [
    {
      id: 1,
      title: 'AI 1: Vision OCR',
      desc: 'Signboard detection & Indic text recognition',
      icon: Eye,
    },
    {
      id: 2,
      title: 'AI 2: Translation',
      desc: 'Context-aware place & warning translation',
      icon: Languages,
    },
    {
      id: 3,
      title: 'AI 3: Voiceover',
      desc: 'Target-language native audio synthesis',
      icon: Volume2,
    },
  ];

  return (
    <div className="pipeline-stepper">
      {steps.map((step) => {
        const Icon = step.icon;
        const isActive = currentStep === step.id;
        const isCompleted = currentStep > step.id;

        let cardClass = 'step-card';
        if (isActive) cardClass += ' active';
        if (isCompleted) cardClass += ' completed';

        return (
          <div key={step.id} className={cardClass}>
            <div className="step-icon-wrap">
              {isActive ? (
                <Loader2 size={22} className="spin-icon" style={{ animation: 'spin 1s linear infinite' }} />
              ) : isCompleted ? (
                <CheckCircle2 size={22} />
              ) : (
                <Icon size={20} />
              )}
            </div>
            <div className="step-content">
              <h4>{step.title}</h4>
              <p>{step.desc}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
