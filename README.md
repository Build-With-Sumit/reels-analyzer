# reels-analyzer

**Scrape competitors' Instagram reels, transcribe the audio verbatim, and use
Claude to return concrete reel scripts you should shoot next week.**

Open source under [AGPL-3.0](LICENSE). The managed version lives inside
[The Automation Founders community at buildwithsumit.com](https://buildwithsumit.com/community.html).

## What it does

You give it:
- your Instagram handle,
- **your website URL** (we read it for you — no need to write a business pitch),
- 1-5 competitor handles you want to study.

It runs a five-stage pipeline:

1. **Read your site** — fetches your homepage, strips the HTML, and asks
   **Claude** to write a one-paragraph business-context (what you sell, who
   the buyer is, your angle). Stored once per project.
2. **Scrape** — pulls the latest reels from each handle via [Apify's Instagram
   Reel Scraper actor](https://apify.com/apify/instagram-reel-scraper) (caption,
   view/like/comment counts, video & audio URLs).
3. **Transcribe** — downloads the audio of each top reel and runs
   [faster-whisper](https://github.com/SYSTRAN/faster-whisper) locally to get
   verbatim spoken text. Captions only tell you what was written; transcripts
   give you the *actual hook* the creator used in the first 3 seconds.
4. **Analyze** — feeds everything (your business context + your reels + each
   competitor's top reels with transcripts and view counts) to **Claude
   Sonnet** with a system prompt designed to be brutally specific.
5. **Output** — a one-page markdown report ending with **exactly 5 numbered
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

## Architecture

![Reels Analyzer architecture: Member sets up IG handle, competitors, and business context. A background pipeline runs Apify scrape → faster-whisper transcribe → Claude Sonnet analyze, writing to reels_cache, reels_transcripts, and reels_reports. The report viewer renders the markdown output.](docs/architecture.svg)

**The pipeline, end-to-end:**

| Step | Tool | What it does | Where it lands | Cache |
|------|------|--------------|----------------|-------|
| **Setup** | **Claude Sonnet** (via Anthropic API) | Reads your website (HTML-stripped) and writes a one-paragraph business context: what you sell, who the buyer is, your angle | `reels_profiles.business_context` | Per project |
| 1 | **Apify** ([instagram-reel-scraper](https://apify.com/apify/instagram-reel-scraper)) | Pulls latest reels per handle: caption, view/like/comment counts, video & audio URLs | `reels_cache` | 24h per handle |
| 2 | **faster-whisper** (base model, int8 CPU) | Downloads each top reel's audio, transcribes the spoken words verbatim | `reels_transcripts` | Permanent (keyed by shortcode) |
| 3 | **Claude Sonnet** (via Anthropic API) | Reads business context + member reels + competitor reels with transcripts, writes a one-page markdown report ending in 5 ready-to-shoot scripts | `reels_reports` | — |
| 4 | **Claude-aesthetic HTML** (built-in) | Optional: renders setup form, dashboard, and report viewer for host apps | — | — |

The pipeline runs as a **background thread** spawned by `start_report_async()`,
so the HTTP request that triggers it returns immediately. The report row
flips through `pending → running → done|failed`, with `status_detail`
updated at each phase ("scraping 2 handles via apify", "transcribing reels
via whisper", "asking claude to synthesize"). The Claude-aesthetic report
viewer auto-refreshes every 6 seconds while the run is in flight.

### Why each tool

**Why Apify (not [yt-dlp](https://github.com/yt-dlp/yt-dlp) / [instaloader](https://github.com/instaloader/instaloader)).**
Instagram aggressively blocks anonymous scraping in 2025+ — `403 Forbidden`
on the GraphQL endpoint, even for public profiles. Free tools require a
logged-in session cookie (your real account gets flagged) or a throwaway
account (bans within weeks). Apify maintains a hardened actor with rotating
residential proxies and absorbs the ban risk on their side. Pricing is
~$0.01-0.03 per profile scrape — negligible at a handful of handles per
member per week.

**Why faster-whisper (not the OpenAI Whisper API).**
Free, local, no API key, no audio data leaving the box. The `base` model is
~140MB, runs at int8 quantization on CPU, and processes ~3-5× realtime on
a 4-core machine — so a 60-second reel transcribes in ~15 seconds. Quality
is plenty for hook extraction (we're not transcribing legal depositions).
First call lazy-loads the model into memory (~1 GB resident); subsequent
runs in the same process reuse it.

**Why Claude Sonnet (not GPT-4 / smaller models).**
Quality matters more than cost on the analyze step — a mediocre report
makes the whole pipeline pointless. Sonnet follows complex system prompts
faithfully (the 5-script-with-HOOK/BODY/CTA structure), is honest about
ambiguity ("the data here is too thin to tell"), and won't slop out
generic creator advice. About $0.05-0.10 per report at typical sizes
(~15k input + 2k output tokens).

**Why MySQL (not SQLite / Postgres / a vector store).**
Boringly available everywhere; the host app probably already has one. No
vector search needed because Claude reads the full context per run — we're
not retrieving similar past reports, we're regenerating fresh each time.
The schema is five flat tables, in `migrations/001_init.sql`.

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

1. Create the schema in your MySQL database (apply each migration in order):

   ```bash
   mysql -u<user> -p<pw> <dbname> < migrations/001_init.sql
   mysql -u<user> -p<pw> <dbname> < migrations/002_website_url.sql
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

# 1) Auto-derive business context from the member's website (~10-15s)
business_context = ra.summarize_website("https://acme.com")

# 2) Save the project (profile + tracked handles)
ra.upsert_profile(
    email,
    ig_handle="acmefounder",
    business_context=business_context,
    website_url="https://acme.com",
)
ra.set_handles(email,
    self_handles=["acmefounder"],
    competitor_handles=["lukebuildsai", "gregisenberg", "wowxmanish"])

# 3) Kick off a background report run
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
