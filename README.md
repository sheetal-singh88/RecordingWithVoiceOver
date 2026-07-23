# 🎬 Voiceover Generator

Generate perfectly synced AI-voiceover demo videos from **screenshots + a plain-text transcript** — no timeline editing, no recording software, no manual timing.

Each screenshot stays on screen for **exactly as long as its narration takes to speak**, driven by `[screenshot:N]` markers you place in the transcript.

---

## How it works

```
Screenshots (PNG/JPG)  +  Annotated Transcript (.md / .txt)
                ↓
        Python backend (Flask + gTTS + moviepy)
                ↓
           Final MP4 video
```

The pipeline for each `[screenshot:N]` segment:

1. **Parse markers** — transcript is split at every `[screenshot:N]` tag into narration segments  
2. **TTS per segment** — gTTS generates a separate MP3; exact duration is measured with mutagen  
3. **Video per segment** — moviepy loops the referenced screenshot for exactly that audio duration  
4. **Concatenate** — all video clips are joined; all audio clips are joined  
5. **Mux** — silent video + combined audio → final MP4 (H.264 + AAC, web-compatible)

---

## Quick start

### Option A — One-click (Windows)

Double-click **`START_VOICEOVER_TOOL.bat`**.  
It will install all dependencies, start the server, and open the browser UI automatically.

### Option B — Manual

**1. Install dependencies**

```bash
pip install flask flask-cors gtts mutagen moviepy
```

> `moviepy` bundles its own FFmpeg binary via `imageio_ffmpeg` — no system FFmpeg installation required.

**2. Start the backend server**

```bash
python generate_voiceover.py --serve
# optional: --port 8080
```

**3. Open the frontend**

Open `voiceover_tool.html` in any modern browser (Chrome, Edge, Firefox).  
The status indicator at the bottom of the page will turn **green** when the backend is connected.

---

## Transcript format

Place `[screenshot:N]` markers in your transcript to control exactly when each screenshot appears.  
N is **1-based** and matches the order in which you upload the screenshots.

```markdown
[screenshot:1]
Welcome to the demo. In this video we will walk through
the variable reuse feature step by step.

[screenshot:2]
First, open the project and navigate to the Test Generation panel
on the left sidebar.

[screenshot:3]
Click Generate Tests. The tool analyses your existing variables
and suggests reuse opportunities automatically.
```

See [`example_transcript.md`](example_transcript.md) for a complete working example.

### Marker rules

| Rule | Detail |
|------|--------|
| Syntax | `[screenshot:N]` — N is 1-based, matches upload order |
| Placement | Start of paragraph, inline mid-sentence, or on its own line |
| Reuse | Reference the same screenshot multiple times |
| No markers | All text is narrated over screenshot 1 |
| Missing image | If `[screenshot:5]` is used but only 3 images were uploaded, generation fails with a clear error |
| Other brackets | `[pause]`, `[note: ...]` etc. are stripped from audio but do not affect screenshot switching |

---

## Project structure

```
voiceover-tool/
├── voiceover_tool.html          # Browser UI (drag-and-drop, live preview)
├── generate_voiceover.py        # Python backend — Flask API + pipeline
├── audio_utils.py               # Shared TTS / audio helper
├── requirements.txt             # Python dependencies
├── START_VOICEOVER_TOOL.bat     # Windows one-click launcher
└── example_transcript.md        # Sample annotated transcript
```

---

## Requirements

| Component | Version |
|-----------|---------|
| Python | 3.8 + |
| flask | ≥ 3.0 |
| flask-cors | ≥ 4.0 |
| gtts | ≥ 2.5 |
| mutagen | ≥ 1.47 |
| moviepy | ≥ 1.0.3 |

No system FFmpeg installation is needed — `moviepy` auto-downloads its own FFmpeg binary on first run.

---

## Supported TTS languages

English (default), English AU, English UK, English US, French, German, Spanish, Japanese  
(Any [gTTS-supported language code](https://gtts.readthedocs.io/en/latest/module.html#languages-gtts-lang) can be typed manually.)

---

## Standalone CLI mode

Run without a browser using files on disk:

```bash
# Put screenshots (sorted alphabetically = order 1, 2, 3…) in the same folder
# Put your annotated transcript in demo_transcript.md
python generate_voiceover.py
# Output: demo_AI_Voiceover.mp4
```

---

## License

MIT — free to use, modify, and distribute.
