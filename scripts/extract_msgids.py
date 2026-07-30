"""Extract storefront msgids from all template roots."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOTS = [
    ROOT / "templates",
    ROOT / "accounts" / "templates",
    ROOT / "core" / "templates",
]

TRANS_DQ = re.compile(r'\{%\s*trans\s+"([^"]+)"')
TRANS_SQ = re.compile(r"\{%\s*trans\s+'([^']+)'")
FALLBACK_DQ = re.compile(r'fallback_key="([^"]+)"')
FALLBACK_SQ = re.compile(r"fallback_key='([^']+)'")
PY_DQ = re.compile(r'(?:gettext(?:_lazy)?|_)\(\s*"([^"]+)"\s*\)')
PY_SQ = re.compile(r"(?:gettext(?:_lazy)?|_)\(\s*'([^']+)'\s*\)")
BLOCKTRANS = re.compile(
    r"\{%\s*blocktrans(?:\s+[^%]*)?%\}(.*?)\{%\s*endblocktrans\s*%\}",
    re.S,
)


def _normalize_blocktrans(body: str) -> str:
    """Convert blocktrans body to a gettext msgid with %(var)s placeholders."""
    text = re.sub(r"\{\{\s*(\w+)\s*\}\}", r"%(\1)s", body)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def collect_msgids() -> set[str]:
    msgids: set[str] = set()
    for root in TEMPLATE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            msgids.update(TRANS_DQ.findall(text))
            msgids.update(TRANS_SQ.findall(text))
            msgids.update(FALLBACK_DQ.findall(text))
            msgids.update(FALLBACK_SQ.findall(text))
            for body in BLOCKTRANS.findall(text):
                msgid = _normalize_blocktrans(body)
                if msgid:
                    msgids.add(msgid)

    for path in ROOT.rglob("*.py"):
        if any(p in path.parts for p in ("venv", ".venv", "migrations", "node_modules", "scripts")):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        msgids.update(PY_DQ.findall(text))
        msgids.update(PY_SQ.findall(text))
    return msgids


if __name__ == "__main__":
    ids = sorted(collect_msgids())
    out = ROOT / "scripts" / "_msgids.txt"
    out.write_text("\n".join(ids), encoding="utf-8")
    print(f"{len(ids)} msgids -> {out}")
