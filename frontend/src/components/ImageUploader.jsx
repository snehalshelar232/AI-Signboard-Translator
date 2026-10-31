import React, { useRef, useState } from 'react';
import { UploadCloud, Image as ImageIcon, Trash2, Camera, Sparkles } from 'lucide-react';

export default function ImageUploader({ selectedImage, onImageSelected, onImageRemoved, isProcessing }) {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSelect(e.target.files[0]);
    }
  };

  const validateAndSelect = (file) => {
    if (!file.type.startsWith('image/')) {
      alert('Please upload a valid image file (JPEG, PNG, WebP).');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      alert('File size exceeds the 15 MB limit.');
      return;
    }
    onImageSelected(file);
  };

  // Helper to load sample image directly from backend sample images
  // Load authentic sample signboard image directly from the backend endpoint
  const loadSampleImage = async (filename, displayName) => {
    try {
      const response = await fetch(`/api/sample/${filename}`);
      if (response.ok) {
        const blob = await response.blob();
        const file = new File([blob], filename, { type: 'image/png' });
        onImageSelected(file);
        return;
      }
    } catch (err) {
      console.warn('Backend sample fetch fallback to canvas:', err);
    }
  };

  return (
    <div className="upload-card glass-panel">
      <div className="section-label">
        <span>Signboard Photograph</span>
        {selectedImage && (
          <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>
            Image Ready
          </span>
        )}
      </div>

      {!selectedImage ? (
        <div
          className={`dropzone ${isDragOver ? 'drag-active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadCloud className="dropzone-icon" />
          <div className="dropzone-title">
            Drag & drop your signboard photo here
          </div>
          <div className="dropzone-hint">
            Supports real roadside photos, camera uploads, or file browsing (JPG, PNG, WebP)
          </div>

          <button
            type="button"
            className="btn-browse"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            <Camera size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
            Browse / Take Photo
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </div>
      ) : (
        <div className="preview-container">
          <img
            src={URL.createObjectURL(selectedImage)}
            alt="Uploaded Signboard Preview"
            className="preview-img"
          />
          <button
            type="button"
            className="preview-overlay-btn"
            onClick={onImageRemoved}
            disabled={isProcessing}
            title="Remove Image"
          >
            <Trash2 size={13} />
            Replace
          </button>
        </div>
      )}

      {/* Quick Sample Selector for Live Demonstration */}
      <div className="samples-box">
        <div className="samples-title">
          <Sparkles size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
          Or Test with Real Sample Signboards:
        </div>
        <div className="samples-pills">
          <button
            type="button"
            className="sample-pill-btn"
            disabled={isProcessing}
            onClick={() => loadSampleImage('sample_tamil_signboard.png', 'Tamil Highway Sign')}
          >
            தமிழ் Tamil Signboard
          </button>
          <button
            type="button"
            className="sample-pill-btn"
            disabled={isProcessing}
            onClick={() => loadSampleImage('sample_marathi_signboard.png', 'Marathi Highway Sign')}
          >
            मराठी Marathi Highway
          </button>
          <button
            type="button"
            className="sample-pill-btn"
            disabled={isProcessing}
            onClick={() => loadSampleImage('sample_gujarati_signboard.png', 'Gujarati Highway Sign')}
          >
            ગુજરાતી Gujarati Highway
          </button>
          <button
            type="button"
            className="sample-pill-btn"
            disabled={isProcessing}
            onClick={() => loadSampleImage('sample_hindi_signboard.png', 'Hindi Hospital Sign')}
          >
            हिन्दी Hindi Hospital
          </button>
          <button
            type="button"
            className="sample-pill-btn"
            disabled={isProcessing}
            onClick={() => loadSampleImage('sample_english_signboard.png', 'English Caution Sign')}
          >
            English Traffic Sign
          </button>
        </div>
      </div>
    </div>
  );
}
