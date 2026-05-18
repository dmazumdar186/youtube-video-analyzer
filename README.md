# YouTube Video Analyzer — Frame-by-Frame Breakdowns with Claude / Gemini Vision

Go beyond plain transcripts. This tool extracts scene-change frames from any YouTube video, deduplicates them with perceptual hashing, tiles them into 3x3 grids, and sends the result to an AI vision model to produce a structured content breakdown: hook analysis, pacing cuts, visual storytelling patterns, transcript highlights, and content ideas.

One key. Three providers. The Gemini free path costs $0.00 per video.

---

## Demo

The output below was generated for free (Gemini free tier, `--tier gemini`) on the IBM Technology video "MCP vs ADK: How Modern AI Agents Connect and Work Together" (14:11):

**[View full breakdown](examples/mcp-vs-adk-breakdown.md)**

Excerpt:

> **Hook:** The video starts with a black screen and a pair of presenters standing in front of it, immediately addressing the confusion surrounding 'AI agents' and the protocols like 'MCP' and 'ADK' to grab the viewer's attention.
>
> **13:16** — "MCP solves this connectivity problem and ADK solves the orchestration problem. They're complementary and they're not competitors."

Generated for $0.00 via the Gemini free URL-native path.

---

## Quick Start

```bash
git clone https://github.com/dmazumdar186/youtube-video-analyzer.git
cd youtube-video-analyzer
pip install -r requirements.txt
cp .env.example .env  # add your OPENROUTER_API_KEY or GEMINI_API_KEY
```

**Free path (Gemini direct, $0.00 per video):**
```bash
py youtube_video_analyzer.py "https://youtu.be/BedAaB1RKgE" --tier gemini
```

**Default path (Claude Sonnet via OpenRouter, ~$0.032 per video):**
```bash
py youtube_video_analyzer.py "https://youtu.be/BedAaB1RKgE"
```

**Cost estimation without spending credits:**
```bash
py youtube_video_analyzer.py "https://youtu.be/BedAaB1RKgE" --dry-run
```

---

## The Three Tiers

| Tier | Key Required | Cost | Model | Path |
|------|-------------|------|-------|------|
| `default` | `OPENROUTER_API_KEY` | ~$0.032/video | Claude Sonnet (latest) | Frame-grid vision |
| `premium` | `OPENROUTER_API_KEY` | ~$0.16/video | Claude Opus (latest) | Frame-grid vision |
| `gemini` | `GEMINI_API_KEY` | **$0.00** | Gemini Flash (latest) | URL-native (no download) |

The gemini tier passes the YouTube URL directly to Gemini — no video download, no frame extraction, no token cost. If you set both `GEMINI_API_KEY` and `OPENROUTER_API_KEY`, the free path is always preferred for `--tier gemini`.

---

## Key Technical Features

- **Dynamic model registry:** tier->model-ID resolved at runtime via provider APIs, 7-day cache, ALLOWED_FAMILIES allowlist. Adopts new models (e.g. `gemini-2.5-flash`, `claude-sonnet-4-6`) without code changes. Falls back through cache -> LAST_KNOWN_GOOD, never crashes.

- **PySceneDetect + perceptual-hash dedup + 3x3 grid tiling:** scene-change detection identifies meaningful cut points; imagehash dhash removes near-identical frames; frames are composited into 3x3 grids (1152x648px each). Result: ~16x token reduction versus naive per-frame extraction.

- **One key, three providers:** `OPENROUTER_API_KEY` alone reaches Claude Sonnet, Claude Opus, GPT-4o, and Gemini via OpenRouter's unified API. Add `GEMINI_API_KEY` for the free URL-native Gemini path. Add `ANTHROPIC_API_KEY` for the legacy direct Anthropic path.

- **Tool-use structured output:** forces a reliable JSON schema via Anthropic / OpenAI function-calling (`submit_breakdown` tool). No regex parsing of free-text responses.

- **Two dry-run modes:** `--dry-run` (shallow, instant, no network calls) for canary monitoring and cost checks; `--deep-dry-run` (full pipeline, no AI call) for real frame/grid counts and accurate token estimates.

- **Prompt caching:** Anthropic beta `prompt-caching-2024-07-31` applied to tools block and system message. Cache-hit rate logged per run. Also passed through to OpenRouter for `anthropic/*` models.

- **Atomic cache writes:** model registry cache writes via `.tmp` rename to avoid partial-read corruption on crash.

---

## Architecture

```
YouTube URL
    |
    v
[SSRF guard] --> rejects non-YouTube hosts
    |
    +--[gemini-direct path]--+
    |   fetch metadata only  |
    |   Gemini URL-native    |
    |   $0.00, no download   |
    |                        |
    +--[Claude/OR path]------+
        fetch transcript
        download video (yt-dlp, low-res)
        PySceneDetect (scene timestamps)
        extract frames (ffmpeg, 384x216)
        dedup (imagehash dhash, hamming >= 6)
        overlay timestamps (PIL)
        tile 3x3 grids (PIL)
        send grids + transcript to AI
        (tool-use: submit_breakdown)
            |
            v
        structured JSON
            |
            v
        render_breakdown_markdown()
            |
            v
        .tmp/video/{id}/breakdown.md
        (+ Obsidian vault copy if OBSIDIAN_VAULT set)
```

---

## CLI Reference

```
usage: youtube_video_analyzer.py [-h] [--tier {default,premium,gemini}]
                                  [--provider {openrouter,anthropic,gemini-direct,auto}]
                                  [--model MODEL] [--refresh-models]
                                  [--max-frames N] [--obsidian-vault PATH]
                                  [--dry-run] [--deep-dry-run]
                                  [--keep-source] [--refresh-transcript]
                                  url

positional arguments:
  url                   YouTube video URL

options:
  --tier                Analysis tier: default (Sonnet), premium (Opus), gemini (free)
  --provider            openrouter | anthropic | gemini-direct | auto (default: auto)
  --model               Exact model ID escape hatch (bypasses registry)
  --refresh-models      Force registry re-fetch from provider APIs
  --max-frames N        Max frames before dedup (default 24, range 1-200)
  --obsidian-vault PATH Write breakdown into Obsidian vault (absolute path)
  --dry-run             Shallow: no network calls, prints config + would_* fields
  --deep-dry-run        Full pipeline without AI call; real frame/token counts
  --keep-source         Keep downloaded .mp4 after analysis
  --refresh-transcript  Force re-fetch transcript even if cached
```

---

## Testing

73 tests across 7 files:

| File | Tier | Description |
|------|------|-------------|
| `tests/test_unit.py` | Unit | URL parsing, slugify, provider detection, tool schema, registry fallback, mock-based allowlist |
| `tests/test_integration.py` | Integration | Live OR catalog, cache round-trip, transcript fetch, yt-dlp metadata, ffmpeg binary, PySceneDetect |
| `tests/test_e2e.py` | E2E | Full dry-run subprocess calls, provider routing, cache mtime updates |
| `tests/test_sanity.py` | Sanity | Import check, --help flags, dep importability, ffmpeg presence, tmp dirs, cache schema, secret leakage |
| `tests/test_performance.py` | Performance | Wall-clock threshold, frame/dedup/grid counts, token estimate bounds, concurrent dry-runs |
| `tests/test_monkey.py` | Monkey/Chaos | Empty URL, garbage URL, SSRF, XSS params, path traversal, invalid flags, tampered cache, empty API key |
| `tests/canary_check.py` | Canary | Structured JSON health check: secrets, deps, ffmpeg, OR endpoint, YouTube reachability, cache age, dry-run smoke |

Run fast tests (no download):
```bash
py tests/test_unit.py
py tests/canary_check.py
py -m pytest tests/test_sanity.py tests/test_monkey.py -v
```

Run all (some require network):
```bash
py -m pytest tests/ -v -s
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in at least one key:

```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...   # https://openrouter.ai/keys
GEMINI_API_KEY=AIza...             # https://aistudio.google.com/apikey
```

Outputs are written to `.tmp/video/{video_id}/breakdown.md`. Set `OBSIDIAN_VAULT` to an absolute vault path to also copy there automatically.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built with [Claude Code](https://claude.ai/claude-code)*
