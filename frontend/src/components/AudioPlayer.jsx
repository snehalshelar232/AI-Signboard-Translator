import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, RotateCcw, Download, Volume2 } from 'lucide-react';

export default function AudioPlayer({ audioUrl, targetLanguage, translatedText }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    if (audioRef.current) {
      audioRef.current.load();
    }
  }, [audioUrl]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch((err) => console.warn('Audio play error:', err));
    }
  };

  const handleReplay = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = 0;
    audioRef.current.play().catch((err) => console.warn('Audio replay error:', err));
    setIsPlaying(true);
  };

  const cycleSpeed = () => {
    const speeds = [1.0, 0.8, 1.25];
    const nextIndex = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    const nextSpeed = speeds[nextIndex];
    setPlaybackSpeed(nextSpeed);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextSpeed;
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="audio-player-panel">
      <div className="audio-header">
        <div className="audio-title">
          <Volume2 size={18} />
          <span>Spoken Voice Output ({targetLanguage.toUpperCase()})</span>
        </div>

        {isPlaying && (
          <div className="waveform-anim">
            <span className="wave-bar"></span>
            <span className="wave-bar"></span>
            <span className="wave-bar"></span>
            <span className="wave-bar"></span>
            <span className="wave-bar"></span>
          </div>
        )}
      </div>

      {/* Hidden Native Audio Element */}
      <audio
        ref={audioRef}
        src={audioUrl}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration || 0)}
      />

      {/* Playback Controls */}
      <div className="audio-controls">
        <button
          type="button"
          className="btn-audio btn-audio-primary"
          onClick={togglePlay}
          title={isPlaying ? 'Pause Speech' : 'Play Speech'}
        >
          {isPlaying ? <Pause size={16} /> : <Play size={16} fill="#ffffff" />}
          <span>{isPlaying ? 'Pause' : 'Play Speech'}</span>
        </button>

        <button
          type="button"
          className="btn-audio"
          onClick={handleReplay}
          title="Replay from start"
        >
          <RotateCcw size={15} />
          <span>Replay</span>
        </button>

        <button
          type="button"
          className="btn-audio"
          onClick={cycleSpeed}
          title="Change playback speed"
        >
          <span>{playbackSpeed}x Speed</span>
        </button>

        <a
          href={audioUrl}
          download="translated_signboard_voice.mp3"
          className="btn-audio"
          style={{ textDecoration: 'none' }}
          title="Download MP3 Audio File"
        >
          <Download size={15} />
          <span>Download MP3</span>
        </a>

        <div style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#94a3b8' }}>
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>
    </div>
  );
}
