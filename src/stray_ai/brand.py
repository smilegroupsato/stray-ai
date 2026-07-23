from __future__ import annotations

from urllib.parse import quote


_MARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><radialGradient id="g"><stop stop-color="#ff4fd8" stop-opacity=".95"/><stop offset="1" stop-color="#ff4fd8" stop-opacity="0"/></radialGradient></defs><path d="M32 4C48 5 59 17 57 33 55 49 44 60 29 59 14 58 5 47 7 31 9 16 17 3 32 4Z" fill="#090d14" stroke="#39f6ff" stroke-width="2"/><path d="M31 11C43 10 51 20 50 32 49 44 41 52 29 51 18 50 12 42 14 30 15 19 21 12 31 11Z" fill="none" stroke="#ff4fd8" stroke-opacity=".58" stroke-width="1.5"/><path d="M32 18C41 18 46 24 45 33 43 42 38 47 29 45 21 44 18 38 20 30 21 22 25 19 32 18Z" fill="none" stroke="#39f6ff" stroke-opacity=".7" stroke-width="1.5"/><circle cx="33" cy="31" r="12" fill="url(#g)"/><circle cx="33" cy="31" r="3.5" fill="#ff4fd8"/><path d="M14 43C22 53 39 56 49 42 43 48 25 49 14 43Z" fill="#39f6ff" fill-opacity=".72"/></svg>"""


def inline_title_mark_svg() -> str:
    """Return the deterministic decorative Stray AI title mark."""
    return _MARK_SVG.replace("<svg ", '<svg class="stray-mark" aria-hidden="true" focusable="false" ')


def svg_favicon_data_uri() -> str:
    """Return the mark as an escaped, self-contained SVG favicon URI."""
    return "data:image/svg+xml," + quote(_MARK_SVG, safe="")


def favicon_link_html() -> str:
    return f'<link rel="icon" href="{svg_favicon_data_uri()}">'


def cyberpunk_css() -> str:
    """Shared tokens and restrained background/title treatment."""
    return """
:root{--bg-0:#05070b;--bg-1:#090d14;--panel:rgba(8,14,22,.92);--panel-2:rgba(13,21,32,.92);--text:#e8fbff;--muted:#8da7b3;--cyan:#39f6ff;--magenta:#ff4fd8;--yellow:#ffe66d;--line:rgba(57,246,255,.28);--line-magenta:rgba(255,79,216,.25);--accent:var(--cyan);--panel2:var(--panel-2)}
body{background-color:var(--bg-0);background-image:linear-gradient(rgba(57,246,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(57,246,255,.025) 1px,transparent 1px),radial-gradient(circle at 12% 0,rgba(255,79,216,.09),transparent 34%);background-size:32px 32px,32px 32px,auto;color:var(--text)}
.title-row{display:flex;align-items:center;gap:14px}.stray-mark{width:clamp(38px,6vw,58px);height:auto;flex:0 0 auto;filter:drop-shadow(0 0 9px rgba(57,246,255,.22))}.title-row h1{min-width:0}
"""
