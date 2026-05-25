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

## v4: Batch mode + Creator-profile cache (the differentiator)

Process multiple videos in one run, and let the analyzer learn each creator's style across videos.

```bash
# Analyze 5 videos from one channel (free path, $0)
py youtube_video_analyzer.py URL1 URL2 URL3 URL4 URL5 --tier gemini

# Or from a file (one URL per line, # for comments)
py youtube_video_analyzer.py --urls-file my_creators.txt --tier gemini
```

After the 3rd video from the same channel, a creator-style profile auto-distills: hook patterns, pacing, visual style, common topics, creator_signature. Subsequent analyses get this profile injected as context, producing breakdowns that pick up creator-specific patterns. No other open-source tool does this.

**CLI additions:**
- `--urls-file <path>` — bulk-process URLs from a file
- `--parallel N` — opt-in concurrency (default sequential to avoid YouTube IP-blocks)
- `--refresh-creator-profile` — force re-distillation
- `--show-creator-profile <channel_id> --no-analyze` — inspect a profile
- `--no-creator-profile` — skip profile read/write
- `--no-analyze` — skip analysis pipeline (used with `--show-creator-profile`)

Creator profiles are stored as JSON in `.tmp/creator_profiles/{channel_id}.json`. Batch runs write a summary to `.tmp/video/_batch_{run_id}/summary.md`.

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
usage: youtube_video_analyzer.py [-h] [--urls-file PATH]
                                  [--tier {default,premium,gemini}]
                                  [--provider {openrouter,anthropic,gemini-direct,auto}]
                                  [--model MODEL] [--refresh-models]
                                  [--max-frames N] [--obsidian-vault PATH]
                                  [--dry-run] [--deep-dry-run]
                                  [--keep-source] [--refresh-transcript]
                                  [--parallel N] [--refresh-creator-profile]
                                  [--show-creator-profile CHANNEL_ID]
                                  [--no-creator-profile] [--no-analyze]
                                  [urls ...]

positional arguments:
  urls                  One or more YouTube video URLs

options:
  --urls-file PATH      File with one URL per line (# lines and blanks skipped)
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
  --parallel N          Process N URLs in parallel (default: 1 = sequential)
  --refresh-creator-profile  Force re-distillation of creator profile
  --show-creator-profile CHANNEL_ID  Print profile JSON; requires --no-analyze
  --no-creator-profile  Skip creator-profile read/write for this run
  --no-analyze          Skip analysis pipeline (used with --show-creator-profile)
```

---

## Testing

114 tests across 9 files:

| File | Tier | Description |
|------|------|-------------|
| `tests/test_unit.py` | Unit | URL parsing, slugify, provider detection, tool schema, registry fallback, mock-based allowlist |
| `tests/test_integration.py` | Integration | Live OR catalog, cache round-trip, transcript fetch, yt-dlp metadata, ffmpeg binary, PySceneDetect |
| `tests/test_e2e.py` | E2E | Full dry-run subprocess calls, provider routing, cache mtime updates |
| `tests/test_sanity.py` | Sanity | Import check, --help flags, dep importability, ffmpeg presence, tmp dirs, cache schema, secret leakage |
| `tests/test_performance.py` | Performance | Wall-clock threshold, frame/dedup/grid counts, token estimate bounds, concurrent dry-runs |
| `tests/test_monkey.py` | Monkey/Chaos | Empty URL, garbage URL, SSRF, XSS params, path traversal, invalid flags, tampered cache, empty API key |
| `tests/canary_check.py` | Canary | Structured JSON health check: secrets, deps, ffmpeg, OR endpoint, YouTube reachability, cache age, dry-run smoke |
| `tests/test_batch.py` | Batch (v4) | URL collection, --urls-file parsing, fail-fast validation, exit codes, batch summary file |
| `tests/test_creator_profile.py` | Creator-profile (v4) | Schema load/save, append, distillation (mocked LLM), context formatting, CLI flags |

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
