---
description: Lessons learned from building and operating the Lluminate Network content pipeline
---

# Lessons Learned — Lluminate Network

## Architecture

### Agent-as-Composer (Critical)
- **DO NOT use AI API calls for content composition.** The agent (Claude Opus 4.6 in Antigravity) IS the AI. Content generation happens in conversation, not through API calls.
- The pipeline is: `prepare` (Python scripts gather sources) → Agent reads and composes → `verify` (Python scripts check quality) → publish.
- This saves money (no API costs), produces better content (full context window), and keeps the human in the loop.

### Config-Driven Everything
- All channel settings live in `config/channels/<slug>.yml` — never hardcode channel names, sources, or platforms.
- Global voice in `config/voice.yml`, stances in `config/stances.yml`, network settings in `config/network.yml`.
- When adding a channel, always use the `/add-channel` workflow.

### File Paths Convention
- Source briefs: `data/sources/<channel-slug>/<date>/brief.md`
- Source transcripts: `data/sources/<channel-slug>/<date>/source_N.md`
- Composed drafts: `data/output/<channel-slug>/<date>/draft.md`
- NotebookLM videos: `data/output/<channel-slug>/<date>/video.mp4`

## Content Creation

### Source Ingestion
- `yt-dlp` works reliably for YouTube transcripts — always use `--write-auto-sub --sub-lang en` and parse VTT.
- Substack RSS feeds work via `feedparser` — append `/feed` to any Substack URL.
- Breaking Points transcripts run 20-45K characters each — cap at 8K per source in briefs to stay within context.

### Composition Formula (4-Part)
1. **Report as Own (25%)** — Rephrase, expand, claim what you agree with
2. **Reference Source (10%)** — Lightly, not a book report
3. **Frame in Context (35%)** — History, disagreements, what's NOT being said
4. **Research and Quote (30%)** — External sources beyond provided material

### Quality Checks
- The `verify` command runs 10 checks: word count, title/subtitle, formula adherence, voice compliance (AI patterns), source reference density, external quotes (≥3), closing insight, Flesch-Kincaid readability (target grade 10-14), forbidden words, section structure.
- First piece scored 91% — the formula checker's keyword-matching for "frame in context" is conservative. Strong contextual framing that uses different vocabulary may score low on that metric but still be excellent.
- Track stats in `data/stats.jsonl` for trend analysis across channels.

### Forbidden Patterns (Voice Violations)
Never use: delve, unpack, impactful, synergy, game-changer, paradigm shift, robust, leverage, holistic, stakeholder, multiple exclamation marks. Also flag: "in conclusion", "it's worth noting", "let's dive in", "in today's world".

### NotebookLM Tips
- Paste the draft.md content as a source document.
- Use the "What should the AI hosts focus on?" field to steer the discussion toward the piece's strongest angles.
- Reference specific segments, data points, and the lingering question you want them to end on.
- Download the video and save to `data/output/<channel>/<date>/video.mp4`.

### NotebookLM Video Post-Processing (ALWAYS)
- **Crop bottom 10%** — removes NotebookLM watermark. ffmpeg: `crop=in_w:in_h*0.90:0:0`
- **Trim last 3 seconds** — removes NotebookLM outro. ffmpeg: `-t <duration-3>`
- **Re-scale to 1280×720** after crop. ffmpeg: `scale=1280:720`
- The `publish` CLI does all three automatically in a single ffmpeg pass.
- Do NOT crop sides or top — only bottom.

## DevOps

### Dependencies
- `python-substack` latest is `0.1.x`, NOT `1.0` — always pin to `>=0.1.0`.
- `google-generativeai` is DEPRECATED — use `google-genai` if needed for non-composition tasks.
- The old Gemini model `gemini-2.5-pro-preview-05-06` expired — always use `gemini-2.5-pro` (stable).
- Never rely on API keys for content generation. The agent handles it.

### YouTube Channel Setup
- Always check handle availability at `youtube.com/@handle-name` before choosing.
- Drop "The" from all channel names — cleaner branding.
- Handles use kebab-case: `@hindsight-politics`, `@noise-floor`.
- Store channel_id in the YAML config under `publish.channel_id`.

### Substack Setup
- Check subdomain availability at `subdomain.substack.com`.
- Subdomains are alloneword: `carbonandink`, `longerarc`, `rawprovocation`.
- Popular words like "provocation" are taken — prefix with a modifier ("raw").

### Git Workflow
- Commit after each major pipeline step, not at the end.
- Use descriptive commit messages: `feat:`, `refactor:`, `fix:`.
- Push after every commit for remote backup.

## Common Pitfalls

1. **Model names expire.** Always verify the model name before calling AI APIs. Preview models get removed.
2. **SourceDiscovery takes only config, not db.** Don't pass extra args.
3. **Composed content printed to stdout is LOST.** Always save to files.
4. **The user's conda env is `wdi`.** Install packages with `/Users/bedwards/miniconda3/envs/wdi/bin/pip install`.
5. **Browser checks work but `curl` is faster** for checking URL availability (YouTube handles, Substack subdomains).
6. **Don't use GOOGLE_API_KEY from .env for content generation.** The user has Google AI Ultra subscription — the agent (me) does the writing.
7. **`datetime.utcnow()` is deprecated in Python 3.12+.** Use `datetime.now(datetime.UTC)` instead.
8. **NotebookLM videos have a watermark + outro.** Always crop bottom 10% and trim last 3 seconds before uploading.
9. **YouTube custom thumbnails require phone verification.** Verify at youtube.com/verify before first upload.
10. **YouTube OAuth needs `youtube` scope (not just `youtube.upload`)** to set thumbnails.
11. **Always use Antigravity artifacts for ephemeral user instructions.** Setup steps, metadata to copy, action items — put them in an artifact so they appear in the Agent Manager right panel. Text in the chat stream gets lost.
12. **Graphyard database is on `studio` host (192.168.4.50).** Database: `graphyard`, user: `postgres`, password: `postgres`. 79 tables across schemas: `atrocity_economics`, `boomcession`, `costs_of_war`, `tax_burden`, `democide`, `ucdp`, `tbij`, `baseball`, `lahman`, `health`, `cow`, etc.
13. **Data stack is polars + altair + plotly**, not pandas + matplotlib. Check `pyproject.toml` in graphyard for exact deps.
14. **Every Substack article needs a Gemini-generated header image.** No exceptions.
15. **Each publication sticks to ONE post type** (text, audio, video, etc.). Assigned at channel config level. Currently all text, but designed for future type diversity.
