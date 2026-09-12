# backend/services/tts_service.py
import os
import subprocess
import threading
from backend.core.config import settings

_generation_lock = threading.Lock()

def generate_tts_for_question(session_id: str, question_id: str, text: str, voice: str = "en-US-JennyNeural") -> str:
    """
    Generate speech audio (.mp3) for the question text using edge-tts.
    Caches the audio file to avoid synthesizing the same question multiple times.
    Returns the absolute file path to the generated MP3 file.
    """
    tts_dir = os.path.join(settings.BASE_DATA_DIR, "tts_audio")
    os.makedirs(tts_dir, exist_ok=True)
    
    # Generate unique filename for caching
    safe_filename = f"question_{session_id}_{question_id}.mp3"
    output_path = os.path.join(tts_dir, safe_filename).replace("\\", "/")
    
    with _generation_lock:
        if os.path.exists(output_path):
            print(f"Using cached TTS audio: {output_path}")
            return output_path
            
        try:
            print(f"Generating TTS audio using edge-tts: {safe_filename}")
            import sys
            subprocess.run([
                sys.executable,
                "-m", "edge_tts",
                "--text", text,
                "--write-media", output_path,
                "--voice", voice,
                "--rate", "+10%"
            ], check=True)
            
            print(f"Successfully generated TTS audio: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error generating TTS audio: {e}")
            # Return empty or fallback if failed
            return ""
