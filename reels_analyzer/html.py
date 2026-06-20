"""Reels Analyzer — Claude-aesthetic HTML templates.

These build full HTML pages (head + body + chrome) so a host server only has
to ``self._send_html(200, reels_analyzer.html.setup_html(...))``.

The design is deliberately Anthropic/Claude-flavoured: cream background,
Newsreader serif headings, Claude-orange accent, generous whitespace.
"""

import json


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


_CSS = """
:root{
  --bg:#FAF9F5; --surface:#FFFFFF; --surface-sunken:#F4F1EA;
  --text:#1F1E1B; --text-muted:#76746E; --text-soft:#3C3A35;
  --accent:#C7714B; --accent-hover:#A95B36; --accent-soft:#F6E9DF;
  --border:#E8E4D9; --border-strong:#D4CFC0;
  --done-bg:#E0EEDE; --done-fg:#296A3D;
  --run-bg:#E0EAFB; --run-fg:#2154A8;
  --fail-bg:#FBE2DC; --fail-fg:#9F361D;
  --pend-bg:#EDE9DD; --pend-fg:#5E5B50;
  --radius:8px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--text);
  font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  line-height:1.6; -webkit-font-smoothing:antialiased;
}
a{color:var(--accent); text-decoration:none}
a:hover{color:var(--accent-hover); text-decoration:underline}
h1,h2,h3,h4{
  font-family:'Newsreader',Georgia,'Times New Roman',serif;
  font-weight:500; letter-spacing:-0.01em; line-height:1.2;
  color:var(--text); margin:0 0 .6rem;
}
h1{font-size:2.4rem; font-weight:500; letter-spacing:-0.02em}
h2{font-size:1.55rem}
h3{font-family:'Inter',sans-serif; font-weight:600; font-size:1.05rem; letter-spacing:0}
p{margin:0 0 1rem}
.topnav{
  position:sticky; top:0; z-index:50;
  background:rgba(250,249,245,0.85); backdrop-filter:blur(10px);
  border-bottom:1px solid var(--border);
}
.topnav-inner{
  max-width:760px; margin:0 auto; padding:0 24px;
  display:flex; justify-content:space-between; align-items:center;
  height:60px; font-size:.92rem;
}
.brand{font-weight:600; color:var(--text)}
.brand:hover{text-decoration:none; color:var(--text)}
.brand-pill{
  display:inline-block; margin-left:.6rem;
  padding:.18rem .55rem; border-radius:5px;
  background:var(--accent-soft); color:var(--accent);
  font-size:.72rem; font-weight:600; letter-spacing:.05em;
  text-transform:uppercase;
}
.container{max-width:760px; margin:0 auto; padding:0 24px}
main{padding:3rem 0 5rem}
.eyebrow{
  display:inline-block; font-size:.74rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--accent); font-weight:600;
  margin-bottom:.7rem;
}
.lead{font-size:1.12rem; color:var(--text-soft); line-height:1.65; margin-bottom:2rem}
.muted{color:var(--text-muted)}
.small{font-size:.86rem}
.btn{
  display:inline-block; font-family:inherit; font-weight:500; font-size:.95rem;
  padding:.7rem 1.3rem; border-radius:var(--radius);
  border:1px solid var(--border-strong); background:var(--surface);
  color:var(--text); cursor:pointer; text-decoration:none; transition:.15s;
}
.btn:hover{border-color:var(--accent); color:var(--accent); text-decoration:none}
.btn-primary{
  background:var(--accent); color:#fff !important; border-color:var(--accent);
}
.btn-primary:hover{
  background:var(--accent-hover); border-color:var(--accent-hover); color:#fff !important;
}
.btn-lg{padding:.85rem 1.6rem; font-size:1rem}
input[type=text],input[type=email],textarea{
  width:100%; font-family:inherit; font-size:.97rem;
  padding:.75rem .9rem; color:var(--text);
  border:1px solid var(--border-strong); border-radius:var(--radius);
  background:var(--surface); transition:.15s;
}
input:focus,textarea:focus{
  outline:none; border-color:var(--accent);
  box-shadow:0 0 0 3px var(--accent-soft);
}
textarea{resize:vertical; line-height:1.55}
label{
  display:block; margin-bottom:1.2rem;
  font-weight:500; font-size:.92rem; color:var(--text-soft);
}
label > input,label > textarea{margin-top:.35rem; font-weight:400}
.panel{
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:1.4rem 1.5rem; margin-bottom:1rem;
}
.panel.accent{background:#FFF8F2; border-color:#F0DCC8}
.row{display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap}
.handle{
  font-family:ui-monospace,Menlo,monospace; font-size:.88rem;
  background:var(--surface-sunken); padding:.18rem .55rem; border-radius:5px;
  color:var(--text);
}
.badge{
  display:inline-block; font-size:.7rem; font-weight:600;
  letter-spacing:.05em; text-transform:uppercase;
  padding:.2rem .55rem; border-radius:5px;
}
.badge-done{background:var(--done-bg); color:var(--done-fg)}
.badge-running{background:var(--run-bg); color:var(--run-fg)}
.badge-pending{background:var(--pend-bg); color:var(--pend-fg)}
.badge-failed{background:var(--fail-bg); color:var(--fail-fg)}
.divider{border:none; border-top:1px solid var(--border); margin:2.5rem 0}
.form-error{color:var(--fail-fg); margin-top:.7rem; font-size:.92rem}
.spinner{
  display:inline-block; width:14px; height:14px;
  border:2px solid var(--border-strong); border-top-color:var(--accent);
  border-radius:50%; animation:spin .9s linear infinite;
  vertical-align:-2px; margin-right:.5rem;
}
@keyframes spin{to{transform:rotate(360deg)}}
.report{
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:2.2rem 2.4rem;
  font-size:1.04rem; line-height:1.7; color:var(--text);
}
.report h1{font-size:1.8rem; margin-top:0; font-weight:500}
.report h2{font-size:1.35rem; margin:2rem 0 .6rem}
.report h3{font-size:1.05rem; font-family:'Inter',sans-serif; font-weight:600; margin:1.5rem 0 .5rem}
.report p{margin:0 0 1rem}
.report ul,.report ol{padding-left:1.4rem; margin:0 0 1rem}
.report li{margin:.4rem 0}
.report strong{font-weight:600; color:var(--text)}
.report blockquote{
  border-left:3px solid var(--accent); margin:1.2rem 0;
  padding:.4rem 0 .4rem 1.2rem; color:var(--text-soft);
}
.report code{
  font-family:ui-monospace,Menlo,monospace; font-size:.92em;
  background:var(--surface-sunken); padding:.15em .4em; border-radius:4px;
}
.report pre{
  background:var(--surface-sunken); padding:1rem; border-radius:var(--radius);
  overflow-x:auto; font-size:.9rem;
}
.meta-line{
  margin-top:1.2rem; color:var(--text-muted); font-size:.85rem;
}
.back-link{
  display:inline-block; margin-bottom:1.6rem; color:var(--text-muted);
  font-size:.92rem;
}
.back-link:hover{color:var(--accent)}
"""


def _shell(title, body_html, head_extra="", site_name="Build With Sumit",
           home_url="/members", back_label="All features"):
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_esc(title)}</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?'
        'family=Inter:wght@400;500;600;700&'
        'family=Newsreader:opsz,wght@6..72,300;6..72,400;6..72,500&display=swap" '
        'rel="stylesheet">'
        f'<style>{_CSS}</style>'
        f'{head_extra}'
        '</head><body>'
        '<header class="topnav"><div class="topnav-inner">'
        f'<a class="brand" href="{home_url}">{site_name}'
        '<span class="brand-pill">Reels</span></a>'
        f'<a href="{home_url}" class="muted">&larr; {_esc(back_label)}</a>'
        '</div></header>'
        f'<main><div class="container">{body_html}</div></main>'
        '</body></html>'
    )


def _badge(status):
    return f'<span class="badge badge-{_esc(status)}">{_esc(status)}</span>'


def setup_html(email, profile=None, handles=None, message="", action="/members/reels/setup",
               back_url="/members"):
    profile = profile or {}
    handles = handles or []
    ig = _esc(profile.get("ig_handle") or "")
    ctx = _esc(profile.get("business_context") or "")
    selfs = "\n".join(h["ig_handle"] for h in handles if h["kind"] == "self")
    comps = "\n".join(h["ig_handle"] for h in handles if h["kind"] == "competitor")
    note = f'<p class="form-error">{_esc(message)}</p>' if message else ""
    is_edit = bool(profile)
    body = (
        f'<a class="back-link" href="{back_url}">&larr; Members area</a>'
        '<span class="eyebrow">Reels Analyzer</span>'
        f'<h1>{"Edit your radar" if is_edit else "Set up your radar"}</h1>'
        '<p class="lead">'
        'Drop in your Instagram handle, a short note about your business, and the '
        'competitor accounts you want to study. Each report scrapes their reels, '
        'transcribes the audio verbatim, and returns 5 reel scripts you can shoot '
        'this week.'
        '</p>'
        f'<form method="POST" action="{action}" class="panel">'
        '<label>Your Instagram handle'
        f'<input type="text" name="ig_handle" required placeholder="yourname" value="{ig}">'
        '</label>'
        "<label>What does your business do? Who's the buyer?"
        '<textarea name="business_context" required rows="4" '
        'placeholder="e.g. We sell EmpMonitor — workforce monitoring software for SMBs '
        '(10-200 employees). Buyers are operations managers / IT leads who want to '
        'track productivity without micro-managing.">'
        f'{ctx}</textarea></label>'
        '<label>Competitor IG handles (one per line, up to 5)'
        '<textarea name="competitors" required rows="5" '
        'placeholder="lukebuildsai&#10;gregisenberg&#10;wowxmanish">'
        f'{_esc(comps)}</textarea></label>'
        '<label>Other handles to track as your own (optional)'
        '<textarea name="self_aliases" rows="2" '
        'placeholder="(blank if just your main account)">'
        f'{_esc(selfs)}</textarea></label>'
        '<button class="btn btn-primary btn-lg" type="submit">'
        f'{"Save changes" if is_edit else "Save and continue"}</button>'
        f'{note}</form>'
    )
    return _shell("Reels Analyzer · Setup", body, home_url=back_url)


def dashboard_html(email, profile, handles, reports,
                   run_url="/members/reels/run",
                   setup_url="/members/reels/setup",
                   report_url="/members/reels/report",
                   back_url="/members"):
    selfs = [h["ig_handle"] for h in handles if h["kind"] == "self"]
    comps = [h["ig_handle"] for h in handles if h["kind"] == "competitor"]
    self_chips = " ".join(f'<span class="handle">@{_esc(h)}</span>' for h in selfs) or '<span class="muted">none</span>'
    comp_chips = " ".join(f'<span class="handle">@{_esc(h)}</span>' for h in comps) or '<span class="muted">none</span>'

    rows = []
    for r in reports:
        rid = r["id"]
        created = r["created_at"].strftime("%b %d, %Y · %H:%M") if r.get("created_at") else "—"
        detail = _esc((r.get("status_detail") or "")[:90])
        rows.append(
            '<div class="panel">'
            '<div class="row">'
            f'<div><a href="{report_url}?id={rid}" '
            f'style="color:var(--text);font-weight:500">Report #{rid}</a>'
            f'<div class="small muted" style="margin-top:.2rem">{created}'
            + (f' · {detail}' if detail else '')
            + '</div></div>'
            f'<div>{_badge(r["status"])}</div>'
            '</div></div>'
        )
    rows_html = "".join(rows) if rows else (
        '<p class="muted">No reports yet. Generate your first one — '
        'first run takes 3-8 minutes (scrape + transcribe + analyze).</p>'
    )

    body = (
        f'<a class="back-link" href="{back_url}">&larr; Members area</a>'
        '<span class="eyebrow">Reels Analyzer</span>'
        '<h1>Your competitor radar</h1>'
        '<p class="lead">'
        "Read what's working in your niche, get 5 reel scripts to shoot next."
        '</p>'
        '<div class="panel">'
        '<h3>Tracking</h3>'
        f'<p style="margin:.4rem 0"><span class="muted small">Your handles</span><br>{self_chips}</p>'
        f'<p style="margin:.4rem 0 .8rem"><span class="muted small">Competitors</span><br>{comp_chips}</p>'
        f'<a class="btn" href="{setup_url}">Edit list</a>'
        '</div>'
        '<div class="panel accent">'
        '<h3>Generate a fresh report</h3>'
        '<p class="muted" style="margin-bottom:1rem">'
        'Scrapes the latest reels, transcribes everything spoken, and returns '
        'a one-page brief with 5 reel scripts in your voice.'
        '</p>'
        f'<form method="POST" action="{run_url}" style="margin:0">'
        '<button class="btn btn-primary btn-lg" type="submit">Run analysis</button>'
        '</form></div>'
        '<hr class="divider">'
        '<h2 style="margin-bottom:1rem">Past reports</h2>'
        f'{rows_html}'
    )
    return _shell("Reels Analyzer · Dashboard", body, home_url=back_url)


_MD_SCRIPT = (
    '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>'
    '<script>document.addEventListener("DOMContentLoaded",function(){'
    'var el=document.getElementById("md");'
    'if(el && window.marked){'
    'var text=el.textContent;'
    'el.innerHTML=marked.parse(text);'
    '}});</script>'
)


def report_html(email, report, dashboard_url="/members/reels",
                run_url="/members/reels/run"):
    status = report.get("status", "?")
    rid = report.get("id")
    created = report["created_at"].strftime("%B %d, %Y at %H:%M") if report.get("created_at") else "?"
    completed = (report["completed_at"].strftime("%B %d, %Y at %H:%M")
                 if report.get("completed_at") else "")
    detail = _esc(report.get("status_detail") or "")

    head_extra = ""
    inner = ""

    if status in ("pending", "running"):
        head_extra = '<meta http-equiv="refresh" content="6">'
        inner = (
            '<div class="panel" style="text-align:center;padding:2.5rem 2rem">'
            '<h2 style="margin:0 0 .5rem">'
            '<span class="spinner"></span>Analysis in progress'
            '</h2>'
            f'<p class="muted">{_esc(detail) or "queued"}</p>'
            '<p class="muted small" style="margin-top:1.2rem">'
            'This page auto-refreshes every 6 seconds. First reports take '
            '3-8 minutes (scrape + transcribe + analyze).</p>'
            '</div>'
        )
    elif status == "failed":
        inner = (
            '<div class="panel" style="background:var(--fail-bg);border-color:#F1B5A8">'
            '<h2 style="color:var(--fail-fg);margin:0 0 .5rem">Analysis failed</h2>'
            f'<p style="color:var(--text-soft);margin-bottom:1.2rem">{detail or "Unknown error"}</p>'
            f'<form method="POST" action="{run_url}" style="margin:0">'
            '<button class="btn btn-primary" type="submit">Retry</button>'
            '</form></div>'
        )
    else:  # done
        try:
            meta = json.loads(report.get("meta_json") or "{}")
        except Exception:
            meta = {}
        usage = meta.get("claude_usage") or {}
        meta_line = (
            f"Analyzed {meta.get('member_reels_analyzed', 0)} of your reels · "
            f"{meta.get('competitor_reels_analyzed', 0)} competitor reels "
            f"across @{', @'.join(meta.get('competitors') or []) or '—'}. "
            f"{meta.get('model', '?')}, "
            f"{usage.get('input_tokens', 0):,} in / "
            f"{usage.get('output_tokens', 0):,} out."
        )
        md = report.get("body") or ""
        inner = (
            '<article class="report">'
            f'<div id="md" style="white-space:pre-wrap">{_esc(md)}</div>'
            '</article>'
            f'<p class="meta-line">{_esc(meta_line)}</p>'
            f'<form method="POST" action="{run_url}" '
            'style="margin-top:1.5rem"><button class="btn" type="submit">'
            'Run a fresh report</button></form>'
            + _MD_SCRIPT
        )

    body = (
        f'<a class="back-link" href="{dashboard_url}">&larr; Back to dashboard</a>'
        f'<span class="eyebrow">Report #{rid} · {_badge(status)}</span>'
        f'<h1>Report from {created}</h1>'
        + (f'<p class="muted small">Completed {completed}</p>' if completed else "")
        + inner
    )
    return _shell(f"Reels Analyzer · Report #{rid}", body, head_extra=head_extra,
                  home_url=dashboard_url)
