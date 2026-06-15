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
import whisper

from backend.core.config import settings

# Load Whisper once at startup — not per request
_whisper_model = whisper.load_model(settings.WHISPER_MODEL)

# Filler words to detect
FILLER_WORDS = [
    "umm", "um", "uh", "uhh", "hmm", "like", "you know",
    "basically", "actually", "literally", "i mean", "sort of",
    "kind of", "right", "okay so", "so yeah", "aaa", "err"
]


# ─── Transcription ────────────────────────────────────────────────────────────

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes audio using Whisper.
    Keeps natural speech fillers (umm, uh, like etc.) for hesitation analysis.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    result = _whisper_model.transcribe(
        file_path,
        fp16=False,
        language="en",
        temperature=0.0,
        condition_on_previous_text=False,
        initial_prompt=(
            "Transcribe exactly as spoken. Keep all fillers: "
            "umm, uh, aaa, hmm, like, you know, basically, i mean. "
            "Do not clean or correct speech."
        ),
    )
    return result["text"].strip()


# ─── Audio Analysis ───────────────────────────────────────────────────────────

def analyze_audio(file_path: str, transcript: str = "") -> dict:
    """
    Full audio confidence analysis.
    Returns structured metrics used by the Confidence Analysis agent.
    """
    y, sr = librosa.load(file_path, sr=16000)
    duration = librosa.get_duration(y=y, sr=sr)

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

    # ── Pitch Variance (nervousness indicator) ────────────────────────────────
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7")
        )
        voiced_f0 = f0[voiced_flag] if f0 is not None else np.array([])
        pitch_variance = float(np.var(voiced_f0)) if len(voiced_f0) > 1 else 0.0
        # Normalize: high variance = unstable pitch = nervous
        pitch_variance_norm = min(1.0, pitch_variance / 5000.0)
    except Exception:
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
