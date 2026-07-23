"""
Generate AI voiceover from a marker-annotated transcript and screenshots,
then produce a perfectly synced MP4 where each screenshot appears exactly
when its narration is spoken.

NO system dependencies required — uses only pip-installable packages:
  - gtts       : Google Text-to-Speech (free, no API key)
  - pydub      : audio duration measurement + MP3 concatenation
  - moviepy    : image → video + final mux  (auto-downloads its own FFmpeg)

Transcript marker syntax
------------------------
Place  [screenshot:N]  anywhere in the text to indicate that screenshot N
(1-based, matching the upload order) should appear at that point.

Example transcript:

    [screenshot:1]
    Welcome to the demo. In this video we will walk through
    the feature step by step.

    [screenshot:2]
    First, open the project settings and navigate to the panel.

    [screenshot:3]
    Click Generate. The tool will analyse your inputs automatically.

Rules
-----
- If there is no marker before the first text, screenshot 1 is used.
- Markers may appear on their own line or inline mid-sentence.
- The same screenshot number may be referenced more than once.
- Any [bracket] that is NOT a screenshot marker is stripped before TTS.

Pipeline
--------
  1. Parse transcript → list of (screenshot_index, narration_text) segments
  2. Generate one TTS MP3 per segment → measure exact audio duration
  3. For each segment create an ImageClip for that exact duration
  4. Concatenate all ImageClips → combined silent video
  5. Concatenate all MP3 audio → combined audio (via pydub)
  6. Attach combined audio to video → export final MP4

Usage (standalone CLI):
    python generate_voiceover.py

Usage (web server):
    python generate_voiceover.py --serve [--port 5050]
"""

import os
import re
import sys
import uuid
import shutil
import tempfile

# ── Patch ffmpeg path BEFORE importing moviepy so it finds the binary ────────
def _get_ffmpeg_binary_early():
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["FFMPEG_BINARY"] = exe
        os.environ["PATH"] = os.path.dirname(exe) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass
_get_ffmpeg_binary_early()

from gtts import gTTS

# ── Default paths (standalone / CLI mode) ────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPT = os.path.join(SCRIPT_DIR, "demo_transcript.md")
VIDEO_OUT  = os.path.join(SCRIPT_DIR, "demo_AI_Voiceover.mp4")


# ─────────────────────────────────────────────────────────────────────────────
# Transcript parsing
# ─────────────────────────────────────────────────────────────────────────────

MARKER_RE = re.compile(r'\[screenshot\s*:\s*(\d+)\]', re.IGNORECASE)


def parse_segments(raw: str) -> list:
    """
    Split raw transcript into segments by [screenshot:N] markers.

    Returns a list of dicts:
        [{"index": 1, "text": "narration for screenshot 1 ..."},
         {"index": 2, "text": "narration for screenshot 2 ..."},
         ...]

    The "index" is 1-based and matches the upload order of screenshots.
    If the transcript contains no markers at all, the whole text is returned
    as a single segment with index=1.
    """
    parts = MARKER_RE.split(raw)
    # MARKER_RE has one capture group so split gives:
    #   [pre_text, idx1, text1, idx2, text2, ...]
    # parts[0] is any text before the first marker (usually empty or a heading)

    segments = []

    if len(parts) == 1:
        # No markers found — treat everything as screenshot 1
        cleaned = _clean_text(parts[0])
        if cleaned:
            segments.append({"index": 1, "text": cleaned})
        return segments

    # Any leading text (before first marker) goes onto screenshot 1 implicitly
    leading = _clean_text(parts[0])

    i = 1
    while i < len(parts) - 1:
        idx  = int(parts[i])
        text = _clean_text(parts[i + 1])
        if i == 1 and leading:
            text = leading + " " + text
            leading = ""
        if text:
            segments.append({"index": idx, "text": text})
        i += 2

    return segments


def _clean_text(raw: str) -> str:
    """Strip Markdown formatting so gTTS receives plain prose."""
    text = re.sub(r'\[screenshot\s*:\s*\d+\]', '', raw, flags=re.IGNORECASE)
    text = re.sub(r'#+\s.*\n',        '',    text)   # headings
    text = re.sub(r'\*\*(.*?)\*\*',   r'\1', text)   # bold
    text = re.sub(r'\*(.*?)\*',       r'\1', text)   # italic
    text = re.sub(r'\[(?!screenshot)[^\]]*\]', '', text)  # other [brackets]
    text = re.sub(r'["\u201c\u201d]', '"',    text)  # curly quotes
    text = re.sub(r'\n{2,}',          ' ',    text)  # blank lines → space
    text = re.sub(r'\s{2,}',          ' ',    text)  # collapse whitespace
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# moviepy helpers  (no system FFmpeg needed — uses imageio_ffmpeg's binary)
# ─────────────────────────────────────────────────────────────────────────────

def _get_ffmpeg_binary() -> str:
    """
    Return the path to the FFmpeg binary bundled with imageio_ffmpeg.
    moviepy 1.x does not auto-discover this, so we wire it up explicitly.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError(
            "imageio_ffmpeg is not installed.\n"
            "Run:  pip install moviepy   (it installs imageio_ffmpeg automatically)"
        )


def _patch_moviepy_ffmpeg():
    """
    Point moviepy AND pydub at the imageio_ffmpeg bundled binary so neither
    ever looks for a system-installed ffmpeg.  Call once before any work.
    """
    ffmpeg_exe = _get_ffmpeg_binary()

    # ── moviepy 1.x ──────────────────────────────────────────────────────────
    try:
        import moviepy.config as mpy_cfg
        mpy_cfg.FFMPEG_BINARY = ffmpeg_exe
    except Exception:
        pass

    # ── pydub ─────────────────────────────────────────────────────────────────
    try:
        from pydub import AudioSegment as _AS
        _AS.converter = ffmpeg_exe
        _AS.ffmpeg    = ffmpeg_exe
        _AS.ffprobe   = ffmpeg_exe   # pydub uses ffprobe for metadata
    except Exception:
        pass

    # ── env vars as universal fallback ───────────────────────────────────────
    os.environ["FFMPEG_BINARY"] = ffmpeg_exe
    os.environ["PATH"] = os.path.dirname(ffmpeg_exe) + os.pathsep + os.environ.get("PATH", "")

    return ffmpeg_exe


def build_video_from_segments(
    image_paths_for_segments: list,   # image path per segment (may repeat)
    durations: list,                   # matching duration in seconds per segment
    audio_path: str,                   # single combined MP3
    dest: str,
    log=print,
):
    """
    Build the final MP4 entirely in-process using moviepy:
      - Create one ImageClip per segment at the exact audio duration
      - Concatenate all clips → silent composite
      - Attach the combined audio track
      - Write to dest
    No system FFmpeg installation required.
    """
    ffmpeg_exe = _patch_moviepy_ffmpeg()
    log(f"Using FFmpeg: {os.path.basename(ffmpeg_exe)}")

    try:
        import moviepy.editor as mpy
    except ImportError:
        raise RuntimeError("moviepy is not installed.\nRun:  pip install moviepy")

    log("Building video clips from screenshots...")
    clips = []
    for i, (img_path, dur) in enumerate(zip(image_paths_for_segments, durations)):
        log(f"  Clip {i+1}: {os.path.basename(img_path)}  {dur:.2f}s")
        clip = mpy.ImageClip(img_path).set_duration(dur)
        clips.append(clip)

    log("Concatenating clips...")
    video = mpy.concatenate_videoclips(clips, method="compose")

    log("Attaching audio track...")
    audio = mpy.AudioFileClip(audio_path)
    final = video.set_audio(audio)

    log(f"Writing MP4 -> {dest}")
    final.write_videofile(
        dest,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=[
            "-vf",     "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # ensure even dimensions
            "-pix_fmt","yuv420p",        # required for WMP / QuickTime compatibility
            "-profile:v","baseline",     # H.264 Baseline — widest player support
            "-level",  "3.0",            # level 3.0 covers up to 720p30
            "-movflags","+faststart",    # move moov atom to front for instant playback
            "-loglevel","error",
        ],
        logger=None,
    )

    # Release file handles so temp dir can be deleted on Windows
    final.close()
    video.close()
    audio.close()
    for c in clips:
        c.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    transcript_text: str,
    image_paths: list,      # ordered list of saved screenshot file paths (1-based by position)
    video_out: str,
    lang: str = "en",
    work_dir: str = None,
    log=print,
):
    """
    Marker-driven pipeline: each [screenshot:N] marker in the transcript
    determines exactly how long screenshot N stays on screen.

    Parameters
    ----------
    transcript_text : raw Markdown/plain text with [screenshot:N] markers
    image_paths     : ordered list of screenshot paths; image_paths[0] = screenshot 1
    video_out       : absolute path for the output MP4
    lang            : gTTS language code (e.g. "en", "fr")
    work_dir        : temp directory; auto-created and cleaned if None
    log             : callable for status messages
    """
    own_work_dir = work_dir is None
    if own_work_dir:
        work_dir = tempfile.mkdtemp(prefix="voiceover_")

    try:
        uid = uuid.uuid4().hex[:8]

        # ── Step 1: Parse transcript into segments ────────────────────────────
        log("Parsing transcript markers...")
        segments = parse_segments(transcript_text)

        if not segments:
            raise ValueError("No narration text found in transcript.")

        log(f"  {len(segments)} segment(s) found:")
        for s in segments:
            preview = s["text"][:60].replace("\n", " ")
            log(f"    [screenshot:{s['index']}]  \"{preview}...\"  ({len(s['text'])} chars)")

        # Validate that every referenced screenshot index has been uploaded
        max_ref = max(s["index"] for s in segments)
        if max_ref > len(image_paths):
            raise ValueError(
                f"Transcript references [screenshot:{max_ref}] but only "
                f"{len(image_paths)} screenshot(s) were uploaded."
            )

        # ── Step 2: Generate one TTS MP3 per segment ─────────────────────────
        log(f"\nGenerating TTS audio for {len(segments)} segment(s) (lang={lang})...")
        seg_audio_paths = []
        seg_durations   = []

        for i, seg in enumerate(segments):
            mp3_path = os.path.join(work_dir, f"seg_audio_{uid}_{i:03d}.mp3")
            tts = gTTS(text=seg["text"], lang=lang, slow=False)
            tts.save(mp3_path)
            # mutagen reads duration from MP3 headers — pure Python, no ffprobe needed
            from mutagen.mp3 import MP3 as _MP3
            dur = _MP3(mp3_path).info.length
            seg_audio_paths.append(mp3_path)
            seg_durations.append(dur)
            log(f"  Segment {i+1}: {dur:.2f}s  ->  screenshot {seg['index']}")

        total_audio = sum(seg_durations)
        log(f"  Total audio duration: {total_audio:.2f}s")

        # ── Step 3: Concatenate audio segments (raw bytes — no ffmpeg needed) ─
        # MP3 files are self-framing; concatenating raw bytes produces valid audio
        log("\nConcatenating audio segments...")
        combined_audio = os.path.join(work_dir, f"combined_audio_{uid}.mp3")
        with open(combined_audio, "wb") as out_f:
            for p in seg_audio_paths:
                with open(p, "rb") as in_f:
                    out_f.write(in_f.read())

        # ── Step 4+5+6: Build video + attach audio in one moviepy pass ────────
        seg_images = [image_paths[seg["index"] - 1] for seg in segments]
        build_video_from_segments(
            image_paths_for_segments=seg_images,
            durations=seg_durations,
            audio_path=combined_audio,
            dest=video_out,
            log=log,
        )

        log(f"\nDone!  Output -> {video_out}")
        log(f"  Segments : {len(segments)}  |  Total duration : {total_audio:.2f}s")

    finally:
        if own_work_dir and os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Flask web server  (python generate_voiceover.py --serve)
# ─────────────────────────────────────────────────────────────────────────────

def start_server(port: int = 5050):
    try:
        from flask import Flask, request, send_file, jsonify, after_this_request
        from flask_cors import CORS
    except ImportError:
        print("ERROR: Flask not installed.  Run:  pip install flask flask-cors")
        sys.exit(1)

    app = Flask(__name__)
    CORS(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/generate", methods=["POST"])
    def generate():
        work_dir = tempfile.mkdtemp(prefix="voiceover_web_")
        try:
            # ── Save uploaded screenshots in upload order ─────────────────────
            screenshots = request.files.getlist("screenshots")
            if not screenshots:
                return jsonify({"error": "No screenshots uploaded."}), 400

            img_paths = []
            for idx, f in enumerate(screenshots):
                ext  = os.path.splitext(f.filename)[1] or ".png"
                path = os.path.join(work_dir, f"img_{idx:04d}{ext}")
                f.save(path)
                img_paths.append(path)

            # ── Transcript ────────────────────────────────────────────────────
            transcript_text = request.form.get("transcript", "").strip()
            if not transcript_text:
                return jsonify({"error": "Transcript is empty."}), 400

            # ── Settings ──────────────────────────────────────────────────────
            lang        = request.form.get("lang", "en")
            output_name = request.form.get("output_name", "demo_voiceover.mp4")
            if not output_name.endswith(".mp4"):
                output_name += ".mp4"

            video_out = os.path.join(work_dir, output_name)

            # ── Run pipeline ──────────────────────────────────────────────────
            run_pipeline(
                transcript_text=transcript_text,
                image_paths=img_paths,
                video_out=video_out,
                lang=lang,
                work_dir=work_dir,
                log=lambda msg: print(msg),
            )

            # ── Stream MP4 back; clean up after streaming ─────────────────────
            @after_this_request
            def _cleanup(response):
                shutil.rmtree(work_dir, ignore_errors=True)
                return response

            return send_file(
                video_out,
                mimetype="video/mp4",
                as_attachment=True,
                download_name=output_name,
            )

        except Exception as exc:
            shutil.rmtree(work_dir, ignore_errors=True)
            return jsonify({"error": str(exc)}), 500

    print(f"Voiceover Generator server running on http://localhost:{port}")
    print("Open voiceover_tool.html in your browser.")
    print("Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=port, debug=False)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--serve" in sys.argv:
        port = 5050
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        start_server(port)

    else:
        # Standalone: read transcript from file, screenshots from a subfolder
        # or pass image paths directly via a simple convention.
        print("Reading transcript...")
        with open(TRANSCRIPT, "r", encoding="utf-8") as fh:
            raw = fh.read()

        # Collect screenshots from the same directory, sorted by name
        exts = {".png", ".jpg", ".jpeg", ".webp"}
        imgs = sorted([
            os.path.join(SCRIPT_DIR, fn)
            for fn in os.listdir(SCRIPT_DIR)
            if os.path.splitext(fn)[1].lower() in exts
        ])

        if not imgs:
            print("ERROR: No screenshot images found in", SCRIPT_DIR)
            sys.exit(1)

        print(f"Found {len(imgs)} screenshot(s): {[os.path.basename(p) for p in imgs]}")

        run_pipeline(
            transcript_text=raw,
            image_paths=imgs,
            video_out=VIDEO_OUT,
            lang="en",
        )
