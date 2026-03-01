---
description: Daily content publishing workflow for all channels
---

# Daily Publishing Workflow

Run this workflow daily to publish to all channels. Target: 30-60 minutes.

## Prerequisites
- `.env` file configured with API keys
- `pip install -r requirements.txt` completed
- NotebookLM account logged in

## Steps

// turbo-all

1. Navigate to the project directory:
```bash
cd /Users/bedwards/influence/channels
```

2. Run the daily pipeline:
```bash
python -m src.cli daily
```

3. Review the generated task list output

4. For each NotebookLM task:
   - Open [notebooklm.google.com](https://notebooklm.google.com)
   - Create a new notebook
   - Upload the source document from the path shown
   - Generate the Audio/Video Overview
   - Download the result

5. For each publish task, run the command shown:
```bash
python -m src.cli publish <channel-slug> --video <path> 
# or
python -m src.cli publish <channel-slug> --audio <path>
```

6. Check pipeline status:
```bash
python -m src.cli status
```

7. Commit the day's tracking data:
```bash
git add -A && git commit -m "daily: $(date +%Y-%m-%d)" && git push
```
