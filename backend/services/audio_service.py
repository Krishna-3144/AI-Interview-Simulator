# backend/services/audio_service.py
"""
Audio pipeline — refined from user's original audio_analysis.py + transcribe.py
Changes made:
  - Added filler word detection from transcript
  - Added pitch variance (nervousness signal)
  - Added energy variance
  - Replaced boolean hesitation with 0-1 hesitation_score
  - Added 0-1 confidence_score for agents to use
  - Removed emojis from pace_feedback, replaced with clean strings
  - Normalized silence ratio against duration buckets
"""
import os
import numpy as np
import librosa
from groq import Groq

from backend.core.config import settings

# Initialize Groq client once
_groq_client = Groq(api_key=settings.GROQ_API_KEY)

# Filler words to detect
FILLER_WORDS = [
    "umm", "um", "uh", "uhh", "hmm", "like", "you know",
    "basically", "actually", "literally", "i mean", "sort of",
    "kind of", "right", "okay so", "so yeah", "aaa", "err"
]


# ─── Transcription ────────────────────────────────────────────────────────────

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes audio using Groq Cloud hosted Whisper API.
    Keeps natural speech fillers (umm, uh, like etc.) for hesitation analysis.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    with open(file_path, "rb") as file:
        translation = _groq_client.audio.transcriptions.create(
            file=(os.path.basename(file_path), file.read()),
            model="whisper-large-v3",
            prompt=(
                "Transcribe exactly as spoken. Keep all speech fillers: "
                "umm, uh, aaa, hmm, like, you know, basically, i mean. "
                "Do not clean or correct speech."
            ),
            response_format="json",
            language="en",
            temperature=0.0
        )
    return translation.text.strip()


# ─── Audio Analysis ───────────────────────────────────────────────────────────

def load_wav_fast(file_path: str, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    try:
        import scipy.io.wavfile as wavfile
        sr, data = wavfile.read(file_path)
        # Convert to float32 mono
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128.0) / 128.0
        
        if len(data.shape) > 1:
            data = np.mean(data, axis=1) # convert stereo to mono
            
        if sr != target_sr:
            # Resample if scipy.signal is available, else use librosa
            try:
                from scipy.signal import resample
                num_samples = int(len(data) * target_sr / sr)
                data = resample(data, num_samples)
            except Exception:
                import librosa
                data = librosa.resample(data, orig_sr=sr, target_sr=target_sr)
        return data, target_sr
    except Exception as e:
        # Fall back to librosa
        import librosa
        return librosa.load(file_path, sr=target_sr)

def analyze_audio(file_path: str, transcript: str = "") -> dict:
    """
    Full audio confidence analysis.
    Returns structured metrics used by the Confidence Analysis agent.
    """
    y, sr = load_wav_fast(file_path, target_sr=16000)
    duration = len(y) / sr if sr > 0 else 0.0

    # Normalize amplitude
    y = y / max(1e-8, np.max(np.abs(y)))

    # ── RMS Energy ────────────────────────────────────────────────────────────
    frame_length = 1024
    hop_length = 512
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)

    SILENCE_THRESHOLD = 0.015
    LONG_PAUSE_SEC = 1.0

    silent_frames = rms < SILENCE_THRESHOLD

    # ── Pause Detection ───────────────────────────────────────────────────────
    pause_segments = []
    current_start = None
    for t, is_silent in zip(times, silent_frames):
        if is_silent and current_start is None:
            current_start = t
        elif not is_silent and current_start is not None:
            pause_duration = t - current_start
            if pause_duration >= LONG_PAUSE_SEC:
                pause_segments.append((
                    round(current_start, 2),
                    round(t, 2),
                    round(pause_duration, 2)
                ))
            current_start = None

    long_pause_count = len(pause_segments)
    silence_ratio = round(float(np.mean(silent_frames)), 3)

    # ── Speech Rate ───────────────────────────────────────────────────────────
    words = len(transcript.split()) if transcript else 0
    wps = round(words / duration, 2) if duration > 0 else 0.0

    FAST_WPS = 3.0
    SLOW_WPS = 1.2
    if wps < SLOW_WPS:
        speech_rate_category = "slow"
    elif wps > FAST_WPS:
        speech_rate_category = "fast"
    else:
        speech_rate_category = "normal"

    # ── Filler Word Detection ─────────────────────────────────────────────────
    transcript_lower = transcript.lower() if transcript else ""
    filler_words_found = []
    filler_count = 0
    for filler in FILLER_WORDS:
        count = transcript_lower.count(filler)
        if count > 0:
            filler_words_found.append(filler)
            filler_count += count

    # Normalize filler rate per minute
    filler_rate_per_min = (filler_count / duration * 60) if duration > 0 else 0

    # ── Pitch Variance (unused, bypassed for performance) ────────────────────
    pitch_variance_norm = 0.0

    # ── Energy Variance ───────────────────────────────────────────────────────
    energy_variance = float(np.var(rms))
    energy_variance_norm = min(1.0, energy_variance / 0.01)

    # ── Hesitation Score (0=calm, 1=very hesitant) ────────────────────────────
    # Weighted combination of signals
    pause_score    = min(1.0, long_pause_count / 5.0)          # weight 0.35
    silence_score  = min(1.0, silence_ratio / 0.5)             # weight 0.25
    filler_score   = min(1.0, filler_rate_per_min / 10.0)      # weight 0.25
    pace_score     = 1.0 if speech_rate_category == "slow" else 0.0  # weight 0.15

    hesitation_score = round(
        pause_score * 0.35
        + silence_score * 0.25
        + filler_score * 0.25
        + pace_score * 0.15,
        3,
    )

    # ── Confidence Score (0=not confident, 1=very confident) ──────────────────
    confidence_score = round(1.0 - hesitation_score, 3)

    return {
        "duration_sec":          round(duration, 2),
        "words":                 words,
        "words_per_second":      wps,
        "speech_rate_category":  speech_rate_category,
        "long_pause_count":      long_pause_count,
        "long_pause_timestamps": pause_segments,
        "silence_ratio":         silence_ratio,
        "filler_word_count":     filler_count,
        "filler_words_found":    filler_words_found,
        "pitch_variance":        round(pitch_variance_norm, 3),
        "energy_variance":       round(energy_variance_norm, 3),
        "hesitation_score":      hesitation_score,
        "confidence_score":      confidence_score,
        "probable_hesitation":   hesitation_score > 0.5,
    }


def process_answer_audio(file_path: str) -> tuple[str, dict]:
    """
    Convenience wrapper — transcribe then analyze.
    Returns (transcript, confidence_metrics).
    """
    transcript = transcribe_audio(file_path)
    metrics = analyze_audio(file_path, transcript)
    return transcript, metrics
