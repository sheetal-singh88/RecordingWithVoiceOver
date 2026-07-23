# 🎬 Voiceover Generator

Generate perfectly synced AI-voiceover demo videos from **screenshots + a plain-text transcript** — no installation, no backend, no dependencies.

**[▶ Open the tool](https://sheetal-singh88.github.io/RecordingWithVoiceOver/voiceover_tool.html)**

---

## How it works

Everything runs **inside your browser** using standard Web APIs:

| API | Purpose |
|-----|---------|
| `SpeechSynthesis` | Speaks each narration segment using a built-in browser voice |
| `Canvas 2D` | Draws the matching screenshot while speech is playing |
| `canvas.captureStream()` | Turns the canvas into a live video stream |
| `MediaRecorder` | Records that stream to a WebM video blob |

The pipeline for each `[screenshot:N]` segment:

1. **Parse markers** — transcript is split at every `[screenshot:N]` tag  
2. **Draw screenshot** — the matching image is rendered to a hidden canvas  
3. **Speak** — browser speaks the narration; canvas recording runs simultaneously  
4. **Wait for speech end** — recording of that segment stops exactly when speech ends  
5. **Repeat** for the next segment  
6. **Download** — all chunks merged into a single WebM file

---

## Usage — two ways

### Option A — GitHub Pages (recommended, zero setup)

1. Fork this repository
2. Go to **Settings → Pages → Source: Deploy from branch → `main` → `/` (root)**
3. Visit `https://sheetal-singh88.github.io/RecordingWithVoiceOver/voiceover_tool.html`
4. Share that URL with anyone — it works in Chrome or Edge with no installation

### Option B — Local file

1. Clone or download this repository
2. Open `voiceover_tool.html` directly in Chrome or Edge
3. No server needed — it works as a local `file://` URL

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

## Output format

The tool generates **WebM** (VP8/VP9 + Opus audio).

- Plays natively in Chrome, Edge, Firefox, and VLC  
- To convert to MP4: drag the file into [cloudconvert.com/webm-to-mp4](https://cloudconvert.com/webm-to-mp4) (free, online)

---

## Browser compatibility

| Browser | Supported |
|---------|-----------|
| Chrome 74+ | ✅ Full support |
| Edge 79+ | ✅ Full support |
| Firefox | ✅ Works (fewer voices) |
| Safari | ❌ No `canvas.captureStream()` |

---

## Project structure

```
voiceover-tool/
├── voiceover_tool.html       # The entire tool — open this in Chrome/Edge
├── example_transcript.md     # Sample annotated transcript
└── README.md
```

The Python files (`generate_voiceover.py`, `audio_utils.py`, `requirements.txt`, `START_VOICEOVER_TOOL.bat`) are included for users who prefer a local Python backend that generates MP4 instead of WebM.

---

## License

MIT — free to use, modify, and distribute.
