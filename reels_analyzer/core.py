"""Reels Analyzer — pipeline + storage core.

Apify scrape -> faster-whisper transcribe -> Claude analyze.
Configuration via env vars (or DB `config` table if running embedded in a host
app that exposes one).
"""

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pymysql
import pymysql.cursors

# ---------- DB / config ----------

DB_CFG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "bws"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "buildwithsumit"),
}


def _db():
    return pymysql.connect(charset="utf8mb4", autocommit=True, connect_timeout=5,
                           cursorclass=pymysql.cursors.DictCursor, **DB_CFG)


def db_read(sql, params=()):
    try:
        conn = _db()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()
    except Exception:
        return None


def db_write(sql, params=()):
    try:
        conn = _db()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            return True
        finally:
            conn.close()
    except Exception:
        return False


def db_insert(sql, params=()):
    try:
        conn = _db()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.lastrowid
        finally:
            conn.close()
    except Exception:
        return None


_CFG = None


def cfg(key, default=""):
    """Return a config value. Looks in the MySQL `config` table first (if the
    host app uses one), then falls back to env vars. Cached on first call."""
    global _CFG
    if _CFG is None:
        rows = db_read("SELECT name, value FROM config")
        _CFG = {r["name"]: r["value"] for r in rows} if rows else {}
    v = _CFG.get(key) or os.environ.get(key, default)
    return v if v is not None else default


# ---------- Apify scraping ----------

APIFY_ACTOR = "apify~instagram-reel-scraper"


def apify_scrape(handles, results_limit=15, timeout_sec=420):
    """Run the Apify Instagram Reel Scraper for one or more handles."""
    token = cfg("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("APIFY_API_TOKEN not configured")

    def _api(method, path, body=None):
        url = "https://api.apify.com/v2" + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            ct = r.headers.get("Content-Type", "")
            return json.loads(raw.decode()) if ct.startswith("application/json") else raw

    body = {"username": list(handles), "resultsLimit": results_limit}
    run = _api("POST", f"/acts/{APIFY_ACTOR}/runs", body=body)["data"]
    run_id = run["id"]
    deadline = time.time() + timeout_sec
    while True:
        info = _api("GET", f"/actor-runs/{run_id}")["data"]
        status = info["status"]
        if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            break
        if time.time() > deadline:
            raise RuntimeError(f"Apify run {run_id} timed out at status {status}")
        time.sleep(5)
    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run {run_id} ended {status}")
    items = _api("GET", f'/datasets/{info["defaultDatasetId"]}/items?clean=1&format=json')
    if isinstance(items, bytes):
        items = json.loads(items.decode())
    return items


# ---------- Whisper transcription ----------

_whisper = None
_whisper_lock = threading.Lock()


def _get_whisper():
    global _whisper
    if _whisper is None:
        with _whisper_lock:
            if _whisper is None:
                from faster_whisper import WhisperModel
                _whisper = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper


def transcribe_audio_url(audio_url, shortcode, tmp_dir="/tmp/reels_audio"):
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, shortcode + ".mp4")
    if not os.path.exists(path):
        req = urllib.request.Request(audio_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(path, "wb") as fh:
            fh.write(resp.read())
    model = _get_whisper()
    segments, info = model.transcribe(path, language="en", beam_size=1)
    text = " ".join(s.text.strip() for s in segments).strip()
    try:
        os.remove(path)
    except OSError:
        pass
    return text, float(info.duration)


# ---------- Storage helpers ----------

def upsert_reel(handle, item):
    sc = item.get("shortCode") or item.get("shortcode")
    if not sc:
        return
    posted = (item.get("timestamp") or "").replace("T", " ").replace("Z", "")[:19] or None
    db_write(
        "INSERT INTO reels_cache (shortcode,ig_handle,caption,posted_at,duration_sec,"
        "view_count,like_count,comment_count,video_url,audio_url,raw_json) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE caption=VALUES(caption), view_count=VALUES(view_count),"
        " like_count=VALUES(like_count), comment_count=VALUES(comment_count),"
        " video_url=VALUES(video_url), audio_url=VALUES(audio_url),"
        " raw_json=VALUES(raw_json), scraped_at=NOW()",
        (sc, handle.lower(), item.get("caption") or "", posted,
         int(item.get("videoDuration") or 0) or None,
         item.get("videoPlayCount") or 0,
         item.get("likesCount") or 0,
         item.get("commentsCount") or 0,
         item.get("videoUrl") or "",
         item.get("audioUrl") or "",
         json.dumps(item, ensure_ascii=False, default=str)))


def get_handle_reels(handle, top_n=15):
    return db_read(
        "SELECT shortcode,ig_handle,caption,posted_at,duration_sec,view_count,"
        "like_count,comment_count,audio_url FROM reels_cache WHERE ig_handle=%s "
        "ORDER BY view_count DESC LIMIT %s",
        (handle.lower(), top_n)) or []


def get_transcript(shortcode):
    rows = db_read("SELECT transcript FROM reels_transcripts WHERE shortcode=%s",
                   (shortcode,))
    return rows[0]["transcript"] if rows else None


def save_transcript(shortcode, text, duration):
    db_write(
        "INSERT INTO reels_transcripts (shortcode,transcript,duration_sec) "
        "VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE transcript=VALUES(transcript)",
        (shortcode, text, duration))


def cache_fresh(handle, max_age_hours=24, min_count=5):
    rows = db_read(
        "SELECT COUNT(*) AS c FROM reels_cache WHERE ig_handle=%s "
        "AND scraped_at > (NOW() - INTERVAL %s HOUR)",
        (handle.lower(), max_age_hours))
    return bool(rows) and rows[0]["c"] >= min_count


# ---------- Claude analysis ----------

CLAUDE_MODEL = "claude-sonnet-4-6"


def call_claude(system, user_text, max_tokens=2500):
    key = cfg("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_text}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
        data=body, method="POST", headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode())
    parts = d.get("content") or []
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    usage = d.get("usage") or {}
    return text, usage


REPORT_SYSTEM = """You are the analyst inside The Automation Founders \
community. Your job: read a member's business context, their own Instagram \
reels, and their competitors' reels (with view counts and verbatim transcripts), \
then produce a brutally honest one-page report.

Rules:
- Open with one sentence on the single biggest gap.
- Quote specific transcript lines and view counts as evidence.
- Skip generic content advice ("post consistently!"). Be specific.
- End with EXACTLY 5 numbered reel scripts the member can shoot this week, \
each with: HOOK (verbatim first line), BODY (3-5 sentences they would say), \
CTA (verbatim closer with a keyword to comment). Voice should match the \
member's business context, not a generic creator.
- Markdown only. No emojis unless they appear in the member's own context."""


def _fmt_reel_block(label, reels_with_transcripts, limit=8):
    out = [f"### {label}"]
    for r in reels_with_transcripts[:limit]:
        cap = (r.get("caption") or "").replace("\n", " ").strip()[:240]
        tr = (r.get("transcript") or "").strip()
        handle = r.get("ig_handle") or "?"
        out.append(
            f"- @{handle} | {r.get('view_count', 0):>9,}v "
            f"{r.get('like_count', 0):>6,}l {r.get('comment_count', 0):>5,}c | "
            f"{int(r.get('duration_sec') or 0)}s\n"
            f"  caption: {cap or '(none)'}\n"
            f"  transcript: {tr or '(no transcript)'}"
        )
    return "\n".join(out)


def build_report_prompt(profile, member_reels, competitor_reels):
    parts = [
        "## Member business context",
        profile.get("business_context") or "(no context provided)",
        f"\nMember IG handle: @{profile.get('ig_handle')}",
        "",
        _fmt_reel_block(
            f"Member's own reels (@{profile['ig_handle']}, top {len(member_reels)} by views)",
            member_reels, limit=8),
        "",
        _fmt_reel_block(
            f"Competitors' top reels (across {len({r.get('ig_handle') for r in competitor_reels if r.get('ig_handle')})} handles)",
            competitor_reels, limit=15),
        "",
        "Produce the report now. Markdown only. Lead with the single biggest gap.",
    ]
    return "\n".join(parts)


# ---------- Orchestration ----------

def _ensure_handle_data(handle, results_limit=15):
    if not cache_fresh(handle, max_age_hours=24, min_count=results_limit // 2):
        items = apify_scrape([handle], results_limit=results_limit)
        for it in items:
            upsert_reel(handle, it)
    return get_handle_reels(handle, top_n=results_limit)


def _hydrate_transcripts(reels, max_per_handle=10):
    out = []
    for r in reels[:max_per_handle]:
        sc = r["shortcode"]
        tr = get_transcript(sc)
        if not tr and r.get("audio_url"):
            try:
                text, dur = transcribe_audio_url(r["audio_url"], sc)
                save_transcript(sc, text, dur)
                tr = text
            except Exception as e:
                tr = f"(transcription failed: {type(e).__name__})"
        out.append({**r, "transcript": tr or ""})
    return out


def run_report(email, report_id):
    """Synchronous full pipeline. Updates the report row as it progresses."""
    def _status(s, detail=""):
        db_write("UPDATE reels_reports SET status=%s, status_detail=%s "
                 "WHERE id=%s", (s, detail[:1000], report_id))

    try:
        _status("running", "loading profile")
        rows = db_read("SELECT * FROM reels_profiles WHERE email=%s", (email,))
        if not rows:
            _status("failed", "no profile")
            return
        profile = rows[0]

        handles = db_read(
            "SELECT ig_handle, kind FROM reels_handles WHERE email=%s",
            (email,)) or []
        if not handles:
            _status("failed", "no tracked handles")
            return
        self_handles = [h["ig_handle"] for h in handles if h["kind"] == "self"]
        comp_handles = [h["ig_handle"] for h in handles if h["kind"] == "competitor"]
        all_handles = list({h.lower() for h in self_handles + comp_handles})

        _status("running", f"scraping {len(all_handles)} handles via apify")
        for h in all_handles:
            _ensure_handle_data(h, results_limit=15)

        _status("running", "transcribing reels via whisper")
        member_reels = []
        for h in self_handles:
            member_reels += _hydrate_transcripts(get_handle_reels(h, top_n=10),
                                                 max_per_handle=10)
        comp_reels = []
        for h in comp_handles:
            comp_reels += _hydrate_transcripts(get_handle_reels(h, top_n=10),
                                               max_per_handle=10)

        _status("running", "asking claude to synthesize")
        prompt = build_report_prompt(profile, member_reels, comp_reels)
        body_text, usage = call_claude(REPORT_SYSTEM, prompt, max_tokens=3000)

        meta = {
            "competitors": comp_handles,
            "self_handles": self_handles,
            "member_reels_analyzed": len(member_reels),
            "competitor_reels_analyzed": len(comp_reels),
            "claude_usage": usage,
            "model": CLAUDE_MODEL,
        }
        db_write(
            "UPDATE reels_reports SET status=%s, status_detail=%s, body=%s, "
            "meta_json=%s, completed_at=NOW() WHERE id=%s",
            ("done", "", body_text, json.dumps(meta), report_id))
    except Exception as e:
        _status("failed", f"{type(e).__name__}: {e}")
        raise


def start_report_async(email):
    report_id = db_insert(
        "INSERT INTO reels_reports (email, status, status_detail) "
        "VALUES (%s, 'pending', 'queued')", (email,))
    if report_id:
        threading.Thread(
            target=run_report, args=(email, report_id),
            name=f"reels-report-{report_id}", daemon=True).start()
    return report_id


# ---------- Profile / handle helpers ----------

def get_profile(email):
    rows = db_read("SELECT * FROM reels_profiles WHERE email=%s", (email,))
    return rows[0] if rows else None


def upsert_profile(email, ig_handle, business_context, website_url=None):
    db_write(
        "INSERT INTO reels_profiles (email, ig_handle, business_context, website_url) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE ig_handle=VALUES(ig_handle), "
        "business_context=VALUES(business_context), website_url=VALUES(website_url)",
        (email, ig_handle.lower().lstrip("@"), business_context, website_url))


def fetch_url_text(url, max_bytes=80_000, timeout=15):
    """Fetch a URL and return its visible plain-text content, capped.

    Strips script/style/noscript blocks. Robust to bad encoding declarations
    (falls back to latin-1) and arbitrary content-types (best effort decode).
    """
    from html.parser import HTMLParser

    class _Strip(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self._skip = 0
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript", "svg"):
                self._skip += 1
        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript", "svg"):
                self._skip = max(0, self._skip - 1)
        def handle_data(self, data):
            if not self._skip:
                t = data.strip()
                if t:
                    self.parts.append(t)

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; reels-analyzer/0.2; +https://github.com/Build-With-Sumit/reels-analyzer)",
        "Accept": "text/html,*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    parser = _Strip()
    try:
        parser.feed(text)
    except Exception:
        pass
    return " ".join(parser.parts)


SUMMARIZE_SYSTEM = """You are summarizing a business for use as context in a \
content-strategy tool. The output goes into another AI's system prompt to \
recommend Instagram reel scripts. Be concrete: what does this company sell, \
who is the buyer, what's the unique angle. One paragraph, ~120-180 words. \
Voice: direct, founder-honest, no marketing fluff. No greetings, no \
disclaimers — start with the substance."""


def summarize_website(url):
    """Fetch a website and ask Claude to summarize the business + buyer.

    Returns the summary string. Raises on fetch failure or thin content.
    """
    if not url or not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    text = fetch_url_text(url)
    if len(text) < 80:
        raise RuntimeError(
            f"Site returned too little content to summarize ({len(text)} chars). "
            "Add a richer page or set business context manually.")
    user = f"Website URL: {url}\n\nHomepage content (HTML stripped):\n\n{text[:50000]}"
    summary, _usage = call_claude(SUMMARIZE_SYSTEM, user, max_tokens=400)
    return summary.strip()


def list_handles(email):
    return db_read(
        "SELECT id, ig_handle, kind FROM reels_handles WHERE email=%s "
        "ORDER BY kind, ig_handle", (email,)) or []


def set_handles(email, self_handles, competitor_handles):
    db_write("DELETE FROM reels_handles WHERE email=%s", (email,))
    for h in self_handles:
        h = (h or "").lower().lstrip("@").strip()
        if h:
            db_write("INSERT IGNORE INTO reels_handles "
                     "(email,ig_handle,kind) VALUES (%s,%s,'self')", (email, h))
    for h in competitor_handles:
        h = (h or "").lower().lstrip("@").strip()
        if h:
            db_write("INSERT IGNORE INTO reels_handles "
                     "(email,ig_handle,kind) VALUES (%s,%s,'competitor')", (email, h))


def list_reports(email, limit=20):
    return db_read(
        "SELECT id, status, status_detail, created_at, completed_at "
        "FROM reels_reports WHERE email=%s ORDER BY id DESC LIMIT %s",
        (email, limit)) or []


def get_report(report_id, email):
    rows = db_read(
        "SELECT * FROM reels_reports WHERE id=%s AND email=%s",
        (report_id, email))
    return rows[0] if rows else None
