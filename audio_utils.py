"""
Shared audio utility for demo video generation.

generate_audio(text, out_path):
  - Splits text at sentence (.) and clause (,) boundaries
  - Generates TTS per chunk via gTTS
  - Inserts 400ms pause after full stops, 180ms after commas
  - Speeds up the entire result by SPEED_FACTOR (default 1.15x)
  - Saves final audio to out_path as MP3
  - Returns duration in seconds
"""

import re
import os
from gtts import gTTS
from pydub import AudioSegment

SPEED_FACTOR   = 1.15   # 1.15x faster — natural, not chipmunk
PAUSE_SENTENCE = 400    # ms after full stop
PAUSE_CLAUSE   = 180    # ms after comma


def _speed_up(audio, factor):
    """Speed up a pydub AudioSegment by `factor` without changing pitch."""
    return (audio
            ._spawn(audio.raw_data,
                    overrides={"frame_rate": int(audio.frame_rate * factor)})
            .set_frame_rate(audio.frame_rate))


def generate_audio(text, out_path):
    """
    Generate audio for `text` with pauses and speed-up.
    Saves to out_path. Returns duration in seconds.
    """
    # Split into chunks at sentence / clause boundaries
    # Keep the delimiter attached so we know what pause to add
    chunk_pattern = re.compile(r'([^.,!?]+[.,!?]?)')
    raw_chunks = chunk_pattern.findall(text)

    # Further split: separate trailing punctuation from chunk
    segments = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.endswith('.') or chunk.endswith('!') or chunk.endswith('?'):
            segments.append((chunk, 'sentence'))
        elif chunk.endswith(','):
            segments.append((chunk, 'clause'))
        else:
            segments.append((chunk, 'none'))

    combined = AudioSegment.empty()
    tmp_base = out_path + "_chunk"

    for idx, (chunk, pause_type) in enumerate(segments):
        if not chunk.strip():
            continue
        chunk_path = f"{tmp_base}_{idx}.mp3"
        tts = gTTS(text=chunk.strip(), lang="en", slow=False)
        tts.save(chunk_path)
        chunk_audio = AudioSegment.from_mp3(chunk_path)
        combined += chunk_audio

        if pause_type == 'sentence':
            combined += AudioSegment.silent(duration=PAUSE_SENTENCE)
        elif pause_type == 'clause':
            combined += AudioSegment.silent(duration=PAUSE_CLAUSE)

        os.remove(chunk_path)

    # Speed up
    combined = _speed_up(combined, SPEED_FACTOR)
    combined.export(out_path, format="mp3")

    return len(combined) / 1000.0
