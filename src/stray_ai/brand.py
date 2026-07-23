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
    """Shared terminal tokens, enclosure, background, and title treatment."""
    return """
:root{--bg-0:#05070b;--bg-1:#090d14;--bg-2:#0c1420;--panel:rgba(8,14,22,.94);--panel-2:rgba(13,21,32,.94);--text:#e8fbff;--muted:#8da7b3;--cyan:#39f6ff;--magenta:#ff4fd8;--yellow:#ffe66d;--line:rgba(57,246,255,.32);--line-magenta:rgba(255,79,216,.3);--accent:var(--cyan);--panel2:var(--panel-2);--terminal-cut:18px}
html{background:var(--bg-0)}
body{position:relative;background-color:var(--bg-0);background-image:radial-gradient(circle at 12% 0,rgba(255,79,216,.12),transparent 31rem),radial-gradient(circle at 88% 18%,rgba(57,246,255,.08),transparent 28rem),linear-gradient(rgba(57,246,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(57,246,255,.035) 1px,transparent 1px),linear-gradient(145deg,var(--bg-1),var(--bg-0) 58%,#080510);background-size:auto,auto,32px 32px,32px 32px,auto;color:var(--text)}
body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(255,255,255,.018) 0,rgba(255,255,255,.018) 1px,transparent 1px,transparent 4px);opacity:.55}
body::after{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;background-image:radial-gradient(rgba(232,251,255,.16) .45px,transparent .6px);background-size:5px 7px;opacity:.09}
.terminal-shell{position:relative;z-index:1;border:1px solid var(--cyan);clip-path:polygon(var(--terminal-cut) 0,calc(100% - 38px) 0,calc(100% - 28px) 10px,100% 10px,100% calc(100% - var(--terminal-cut)),calc(100% - var(--terminal-cut)) 100%,38px 100%,28px calc(100% - 10px),0 calc(100% - 10px),0 var(--terminal-cut));background:linear-gradient(145deg,rgba(13,21,32,.97),rgba(5,7,11,.93) 38%,rgba(9,8,18,.96));box-shadow:0 0 0 1px rgba(255,79,216,.34),inset 0 0 0 1px rgba(232,251,255,.055),inset 0 0 42px rgba(57,246,255,.025),0 0 34px rgba(57,246,255,.1)}
.terminal-shell::before{content:"STRAY // OBSERVATION TERMINAL";position:absolute;z-index:2;top:0;right:42px;padding:3px 10px;color:var(--magenta);background:var(--bg-0);font:600 9px/1.2 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.15em}
.terminal-shell::after{content:"";position:absolute;z-index:2;inset:8px;pointer-events:none;border-top:1px solid rgba(57,246,255,.16);border-bottom:1px solid rgba(255,79,216,.14);clip-path:inherit}
.title-zone{position:relative;padding:14px 0 18px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,rgba(57,246,255,.055),transparent 62%);box-shadow:0 8px 24px rgba(0,0,0,.18)}
.title-zone::after{content:"";position:absolute;left:0;bottom:-1px;width:min(38%,240px);height:2px;background:linear-gradient(90deg,var(--magenta),var(--cyan));box-shadow:0 0 10px var(--cyan)}
.title-row{display:flex;align-items:center;gap:clamp(12px,2vw,22px);min-width:0}.stray-mark{width:clamp(52px,8vw,82px);height:auto;flex:0 0 auto;filter:drop-shadow(0 0 12px rgba(57,246,255,.38)) drop-shadow(3px 1px 8px rgba(255,79,216,.2))}.title-row h1{min-width:0;overflow-wrap:anywhere;text-shadow:0 0 16px rgba(57,246,255,.34),2px 1px 0 rgba(255,79,216,.2)}
a{overflow-wrap:anywhere}a:focus-visible{outline:2px solid var(--yellow);outline-offset:4px;border-radius:2px}
@media(max-width:680px){:root{--terminal-cut:12px}.terminal-shell::before{right:24px;font-size:7px}.stray-mark{width:48px}.title-zone{padding-top:18px}}
"""
