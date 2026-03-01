---
description: Add a new channel to the network
---

# Add Channel Workflow

## Steps

1. Create a new YAML config in `config/channels/<slug>.yml`:
```yaml
name: "Channel Name"
platform: youtube  # or substack
schedule: daily
description: "Channel description"

sources:
  primary:
    - id: source-slug
      type: youtube  # or substack or web
      url: "https://..."
      stance: 3  # 1-5 agreement scale
  backup:
    - id: backup-source
      type: youtube
      url: "https://..."
      stance: 3

format:
  plugin: notebooklm_video  # or notebooklm_audio or substack_essay
  style: deep_dive

publish:
  plugin: youtube  # or substack
  channel_id: ""

discovery_keywords:
  - "relevant keyword"
```

2. Add source stance entries in `config/stances.yml` if needed

3. Test the channel:
```bash
python -m src.cli compose <slug> --dry-run
```

4. Verify with a dry run:
```bash
python -m src.cli daily --dry-run
```

5. Commit:
```bash
git add config/channels/<slug>.yml
git commit -m "feat: add channel <name>"
git push
```
