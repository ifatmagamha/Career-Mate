# src/export/pdf.py
from __future__ import annotations

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def text_to_pdf(text: str, out_path: str | Path, title: str = "") -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(out_path), pagesize=A4)
    width, height = A4

    y = height - 60
    if title:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, title)
        y -= 30

    c.setFont("Helvetica", 11)

    for line in (text or "").splitlines():
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 11)
            y = height - 60
        c.drawString(50, y, line[:120])
        y -= 15

    c.save()
    return out_path
