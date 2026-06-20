"""reels-analyzer — Instagram reels competitor analysis with Whisper + Claude.

Public API surface for host applications:

    from reels_analyzer import (
        # profile / handles
        get_profile, upsert_profile, list_handles, set_handles,
        # reports
        list_reports, get_report, start_report_async, run_report,
        # html (Claude-design)
        setup_html, dashboard_html, report_html,
    )

Configuration is read from env vars (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME,
APIFY_API_TOKEN, ANTHROPIC_API_KEY). If a host app exposes a MySQL `config`
table with the same key names, those values take precedence — see core.cfg().
"""

__version__ = "0.2.1"

from .core import (
    # config
    cfg,
    # db helpers (rarely needed by hosts)
    db_read, db_write, db_insert,
    # scrape / transcribe / analyze primitives
    apify_scrape, transcribe_audio_url, call_claude,
    build_report_prompt, REPORT_SYSTEM, CLAUDE_MODEL,
    # website -> business-context summarization
    fetch_url_text, summarize_website, SUMMARIZE_SYSTEM,
    # storage
    upsert_reel, get_handle_reels, get_transcript, save_transcript,
    cache_fresh,
    # profile / handles
    get_profile, upsert_profile, list_handles, set_handles,
    # reports
    list_reports, get_report, start_report_async, run_report,
)
from .html import setup_html, dashboard_html, report_html

__all__ = [
    "__version__",
    "cfg",
    "db_read", "db_write", "db_insert",
    "apify_scrape", "transcribe_audio_url", "call_claude",
    "build_report_prompt", "REPORT_SYSTEM", "CLAUDE_MODEL",
    "fetch_url_text", "summarize_website", "SUMMARIZE_SYSTEM",
    "upsert_reel", "get_handle_reels", "get_transcript", "save_transcript",
    "cache_fresh",
    "get_profile", "upsert_profile", "list_handles", "set_handles",
    "list_reports", "get_report", "start_report_async", "run_report",
    "setup_html", "dashboard_html", "report_html",
]
