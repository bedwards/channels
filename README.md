# Lluminate Network — Multi-Channel Content Pipeline

An autonomous content production system that ingests from diverse sources (YouTube, Substack, news sites), generates original analytical content with substantive value-add, produces it in multiple formats (NotebookLM Audio/Video Overviews, illustrated essays), and publishes to a network of channels.

## Channels

| Channel | Source(s) | Platform | Format |
|---------|-----------|----------|--------|
| **The Second Look** | @NateBJones | YouTube | Video Overview |
| **Carbon & Ink** | @NovaraMedia | Substack | Essay + charcoal art |
| **The Undertow** | Lluminate Substack | YouTube | Audio Overview |
| **Lone Star Dispatch** | Texas Tribune + @jamestalaricoTX | YouTube | Video Overview |
| **The Longer Arc** | @heathercoxrichardson + @DwarkeshPatel | Substack | Long-form essay |
| **Slow Frequencies** | Philosophize This + @closereadingpoetry | YouTube | Audio Overview |
| **The Provocation** | Kvetch + The Walrus + @samharrisorg | Substack | Contrarian essay |
| **Signal Drift** | @doomscrollpodcast + @aiexplained + @PBoyle | YouTube | Video Overview |
| **The Blackboard** | @3blue1brown + @anthropic-ai + @profjeffreykaplan | YouTube | Video Overview |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# List all channels
python -m src.cli channels

# Run daily pipeline
python -m src.cli daily

# Test ingestion from a source
python -m src.cli ingest youtube --url "https://www.youtube.com/@NateBJones" --show-content

# Check pipeline status
python -m src.cli status
```

## Daily Workflow (30-60 minutes)

```bash
# 1. Run the automated pipeline
python -m src.cli daily

# 2. Follow the generated task list:
#    - Upload source docs to NotebookLM
#    - Generate Audio/Video Overviews
#    - Download and publish

# 3. Commit the day's work
git add -A && git commit -m "daily: $(date +%Y-%m-%d)" && git push
```

## Architecture

```
config/              # YAML-driven configuration
├── network.yml      # Global settings
├── voice.yml        # Writing voice/style
├── stances.yml      # Source agreement levels
└── channels/        # One YAML per output channel

src/
├── core/            # Config, models, database, registry
├── ingest/          # YouTube, Substack, web ingesters
├── compose/         # AI content composer + researcher
├── format/          # NotebookLM, Substack essay, image gen
├── publish/         # YouTube Data API, Substack publisher
├── ops/             # Daily operations runner
└── cli.py           # CLI entry point
```

## Key Design Principles

- **YAML-driven config** — No hardcoded values. Every channel, source, and style is configurable.
- **Plugin architecture** — Add new ingesters, formats, and publishers without touching existing code.
- **Source dedup** — SQLite tracks every source used on every channel. No repeats.
- **4-part composition formula** — Report → Reference → Contextualize → Research
- **Stance-aware** — Each source has an agreement level (1-5) that shapes how we engage with it.
- **Human-in-the-loop** — Autonomous for 90% of the work, clear instructions for the 10% that needs human touch.

## Adding a New Channel

See the workflow: `.agents/workflows/add-channel.md`

## Environment Variables

See `.env.example` for all required variables.
