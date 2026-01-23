from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _wrap_line(text: str, max_chars: int = 95) -> list[str]:
    """Very simple wrapping by characters (stable)."""
    text = text or ""
    words = text.split()
    lines = []
    cur = []
    cur_len = 0
    for w in words:
        add = len(w) + (1 if cur else 0)
        if cur_len + add > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += add
    if cur:
        lines.append(" ".join(cur))
    return lines or [""]


def render_structured_pdf(
    out_path: str | Path,
    title: str,
    blocks: Iterable[Tuple[str, list[str]]],
) -> Path:
    """
    blocks: iterable of (section_title, lines)
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out_path), pagesize=A4)
    width, height = A4

    y = height - 60

    # Title
    c.setFont("Helvetica-Bold", 16)
    for tl in _wrap_line(title, 80):
        c.drawString(50, y, tl)
        y -= 22
    y -= 8

    def new_page():
        nonlocal y
        c.showPage()
        y = height - 60

    for sec_title, lines in blocks:
        if y < 100:
            new_page()

        # Section header
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, sec_title)
        y -= 18

        # Content
        c.setFont("Helvetica", 11)
        for line in lines:
            # bullet formatting
            if line.startswith("- "):
                text = "• " + line[2:]
            else:
                text = line

            wrapped = _wrap_line(text, 95)
            for w in wrapped:
                if y < 60:
                    new_page()
                    c.setFont("Helvetica", 11)
                c.drawString(60, y, w)
                y -= 14

        y -= 10

    c.save()
    return out_path


def text_to_pdf(text: str, out_path: str | Path, title: str = "Document"):
    """
    Wrapper for compatibility with simple text input.
    Splits text by newlines and treats them as blocks.
    """
    lines = text.split('\n')
    blocks = [("Content", lines)]
    return render_structured_pdf(out_path, title, blocks)
