"""Replays partageables, sans enregistrer l'ecran ni de donnees sensibles."""

from __future__ import annotations

import json
import os
from pathlib import Path


def export(entries: list[dict], destination: Path, title: str = "Doot Replay") -> Path:
    """Ecrit un HTML autonome anime a partir de l'historique deja collecte."""

    destination = Path(destination)
    if destination.suffix.casefold() != ".html":
        destination = destination / "doot-replay.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe_entries = [
        {key: value for key, value in entry.items()
         if key in ("at", "kind", "count", "formation", "name", "special")
         and isinstance(value, (str, int, float, bool))}
        for entry in entries[-50:] if isinstance(entry, dict)
    ]
    payload = json.dumps(safe_entries, ensure_ascii=False).replace("</", "<\\/")
    safe_title = str(title).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:80]
    html = f"""<!doctype html><meta charset=utf-8><title>{safe_title}</title>
<style>body{{margin:0;background:#09070f;color:#fff;font:20px system-ui;display:grid;place-items:center;height:100vh}}
#card{{width:min(760px,90vw);padding:3rem;border:2px solid #b993ff;border-radius:24px;text-align:center;box-shadow:0 0 50px #6b3fa088}}
#skull{{font-size:7rem}} small{{color:#cbb7ea}}</style>
<div id=card><div id=skull>💀🎺</div><h1>{safe_title}</h1><p id=line>La crypte se reveille...</p><small id=count></small></div>
<script>const e={payload};let i=0;function show(){{if(!e.length)return;const x=e[i%e.length];
line.textContent=(x.kind||'doot')+(x.count?' × '+x.count:'')+(x.name?' — '+x.name:'')+(x.special?' — '+x.special:'');
count.textContent=(i%e.length+1)+' / '+e.length;i++}}show();setInterval(show,1400)</script>"""
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(html, encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return destination
