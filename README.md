# reels-analyzer

**Scrape competitors' Instagram reels, transcribe the audio verbatim, and use
Claude to return concrete reel scripts you should shoot next week.**

Open source under [AGPL-3.0](LICENSE). The managed version lives inside
[The Automation Founders community at buildwithsumit.com](https://buildwithsumit.com/community.html).

## What it does

You give it:
- your Instagram handle,
- a one-paragraph description of your business and your buyer,
- 1-5 competitor handles you want to study.

It runs a four-stage pipeline:

1. **Scrape** — pulls the latest reels from each handle via [Apify's Instagram
   Reel Scraper actor](https://apify.com/apify/instagram-reel-scraper) (caption,
   view/like/comment counts, video & audio URLs).
2. **Transcribe** — downloads the audio of each top reel and runs
   [faster-whisper](https://github.com/SYSTRAN/faster-whisper) locally to get
   verbatim spoken text. Captions only tell you what was written; transcripts
   give you the *actual hook* the creator used in the first 3 seconds.
3. **Analyze** — feeds everything (your business context + your reels + each
   competitor's top reels with transcripts and view counts) to **Claude
   Sonnet** with a system prompt designed to be brutally specific.
4. **Output** — a one-page markdown report ending with **exactly 5 numbered
   reel scripts** you can shoot this week, each with a verbatim hook, 3-5
   sentence body, and a CTA in your voice.

## Why this exists

Most "AI content tools" stop at "write me a reel script about X." That
produces generic creator slop. This tool grounds Claude's output in *real
high-performing reels from people you already think of as competitors* —
with the actual spoken words, not just the captions — and forces Claude to
quote the evidence. The result reads like a research note from an analyst
who watched 30 reels and tells you *exactly* what the top performers do
differently.

## What it's not

- Not a generic IG analytics tool. It doesn't track follower growth or run
  daily reports — that's what Apify or HypeAuditor are for.
- Not an autoposting tool. It returns scripts; you shoot them.
- Not a competitor to ChatGPT/Claude-as-a-coach. It's a narrow, opinionated
  pipeline that gives one specific kind of output well.

## Stack

- **Python 3.10+**
- **MySQL 8+** (or compatible — MariaDB works) for the report + cache schema
- **ffmpeg** (required by faster-whisper for audio decode)
- **Apify** account + token (free tier covers ~$5/month of scraping — plenty
  for a handful of handles per week)
- **Anthropic API** key for Claude Sonnet (roughly $0.05-0.10 per report at
  the volumes this tool runs at)

## Install

```bash
pip install git+https://github.com/Build-With-Sumit/reels-analyzer.git
```

Or for local development:

```bash
git clone https://github.com/Build-With-Sumit/reels-analyzer.git
cd reels-analyzer
pip install -e .
```

You also need ffmpeg system-wide:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (via winget)
winget install Gyan.FFmpeg
```

## Setup

1. Create the schema in your MySQL database:

   ```bash
   mysql -u<user> -p<pw> <dbname> < migrations/001_init.sql
   ```

2. Set environment variables (or put them in a `config` MySQL table — same
   keys; DB values win over env):

   ```bash
   export DB_HOST=127.0.0.1
   export DB_PORT=3306
   export DB_USER=youruser
   export DB_PASSWORD=yourpassword
   export DB_NAME=yourdb
   export APIFY_API_TOKEN=apify_api_xxx       # from apify.com/account/integrations
   export ANTHROPIC_API_KEY=sk-ant-api03-xxx  # from console.anthropic.com
   ```

## Use it as a library

```python
import reels_analyzer as ra

email = "founder@acme.com"

# 1) Save the member's profile and tracked handles
ra.upsert_profile(
    email,
    ig_handle="acmefounder",
    business_context=(
        "We sell EmpMonitor — workforce monitoring software for SMBs "
        "(10-200 employees). Buyers are ops managers / IT leads who want "
        "to track productivity without micro-managing."
    ),
)
ra.set_handles(email,
    self_handles=["acmefounder"],
    competitor_handles=["lukebuildsai", "gregisenberg", "wowxmanish"])

# 2) Kick off a background report run
report_id = ra.start_report_async(email)

# 3) Poll until done
import time
while True:
    r = ra.get_report(report_id, email)
    print(r["status"], "—", r["status_detail"])
    if r["status"] in ("done", "failed"):
        break
    time.sleep(5)

# 4) Read the markdown report
print(r["body"])
```

First run takes 3-8 minutes (scrape + transcribe). Subsequent runs are
faster because both the scrape and the transcripts are cached for 24h.

## Embed the UI in your own server

The package ships **Claude-aesthetic HTML pages** you can drop straight into
any Python HTTP server (`http.server`, FastAPI, Flask, Django — anything).
They return full HTML documents, not fragments:

```python
import reels_analyzer as ra

profile = ra.get_profile(email)
handles = ra.list_handles(email)
reports = ra.list_reports(email)

html = ra.dashboard_html(email, profile, handles, reports,
    run_url="/app/reels/run",
    setup_url="/app/reels/setup",
    report_url="/app/reels/report",
    back_url="/")
# self._send_html(200, html)
```

Three pages: `setup_html()`, `dashboard_html()`, `report_html()`. Each takes
URL overrides so you can mount the feature anywhere.

## Cost per report

At the default settings (15 reels per handle, 10 transcribed):
- **Apify:** ~$0.01-0.03 per profile scraped
- **Whisper:** $0 (runs locally on CPU; ~3-5 min for 50 reels combined)
- **Claude Sonnet:** ~$0.05-0.10 per report (~15k input + 2k output tokens)

So a report covering 5 competitors costs roughly **$0.10 - $0.25** to run
once and is cached for 24h.

## Don't want to host it?

The managed version is inside
[The Automation Founders](https://buildwithsumit.com/community.html) —
$99/month, no infra, runs weekly automatically, plus other AI/automation
skills Sumit ships every week.

## License

[AGPL-3.0-or-later](LICENSE). You can run it for yourself or your own
business as much as you want, for free. If you run it as a network service
for other people, you must publish your modifications under AGPL too —
that's the part of the license that funds the open-source work.

Want to run a hosted version for your customers without that obligation?
Contact `sumit@globussoft.com` about a commercial license.

## Contributing

Issues and PRs welcome at
[github.com/Build-With-Sumit/reels-analyzer](https://github.com/Build-With-Sumit/reels-analyzer/issues).
