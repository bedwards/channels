---
description: Daily content publishing workflow for all channels
---

# Daily Content Publishing

// turbo-all

## Prerequisites
- Conda env `wdi` activated
- Working directory: `/Users/bedwards/influence/channels`

## Pipeline Steps

### 1. Prepare sources for a channel
```bash
python -m src.cli prepare <channel-slug>
```
This gathers fresh sources and creates a composition brief at `data/sources/<channel>/<date>/brief.md`.

### 2. Agent composes content
The agent (Claude Opus 4.6 in Antigravity) reads the brief and source files, then writes the piece following the 4-part composition formula. Save to `data/output/<channel>/<date>/draft.md`.

Key composition rules:
- Follow the 4-part formula weights (25% own, 10% reference, 35% context, 30% research)
- Match the voice from `config/voice.yml` — skeptical, historically grounded, bipartisan accountability
- 1,500-3,000 words
- ≥3 external quotes
- End with a lingering insight
- No AI-sounding patterns (see `.agents/lessons-learned.md` for forbidden list)

### 3. Verify content quality
```bash
python -m src.cli verify data/output/<channel>/<date>/draft.md
```
Target: ≥80% score. Fix any errors flagged (forbidden words, missing title, etc.).

### 4. Create NotebookLM Video/Audio Overview (if YouTube channel)
1. Paste `draft.md` content into NotebookLM as source
2. Use the "What should the AI hosts focus on?" field — write a directive steering hosts to the piece's strongest angles, specific data points, and the closing question
3. Generate Video Overview (or Audio for Undertow/Slow Frequencies)
4. Download and save to `data/output/<channel>/<date>/video.mp4`

### 5. Generate thumbnail
Use the `generate_image` tool with the channel's image style:
```
A dramatic hand-drawn charcoal sketch of [subject related to piece],
banana motif subtly incorporated. Expressive charcoal strokes, rich tonal
range. Black and white only. No text, no words, no letters. Museum-quality
fine art still life.
```
Save to `data/output/<channel>/<date>/thumbnail.png`.

### 6. Publish
```bash
python -m src.cli publish <channel-slug> --video data/output/<channel>/<date>/video.mp4
```

### 7. Engage with comments (after 4-6 hours)
```bash
python -m src.cli engage --channel <channel-slug> --dry-run
```
Review the dry-run replies, then run without `--dry-run` to post.

### 8. Commit progress
```bash
git add -A && git commit -m "content: <channel> — <title>" && git push
```

## Channel Quick Reference

| Channel | Platform | Format | Sources |
|---------|----------|--------|---------|
| hindsight-politics | YouTube | Video Overview | Breaking Points, Majority Report |
| carbon-and-ink | Substack | Essay + charcoal | @NovaraMedia |
| undertow | YouTube | Audio Overview | Lluminate Substack |
| lone-star-dispatch | YouTube | Video Overview | TX Tribune, @jamestalaricoTX |
| longer-arc | Substack | Essay | @heathercoxrichardson, @DwarkeshPatel |
| slow-frequencies | YouTube | Audio Overview | Philosophize This, poetry |
| raw-provocation | Substack | Contrarian essay | Kvetch, Walrus, @samharrisorg |
| noise-floor | YouTube | Video Overview | @NateBJones, @doomscrollpodcast, @aiexplained |
| chalk-and-wire | YouTube | Video Overview | @3blue1brown, @anthropic-ai |
