#!/usr/bin/env python3
"""SSM Tunnel icon — two endpoints connected by a secured tunnel pipe."""
import sys, subprocess, shutil
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import (QPixmap, QPainter, QColor, QBrush,
                          QLinearGradient, QPen, QPainterPath)
from PyQt5.QtCore import Qt, QRectF, QPointF

app = QApplication(sys.argv)

ICONSET = [
    (16,  1, "icon_16x16.png"),
    (16,  2, "icon_16x16@2x.png"),
    (32,  1, "icon_32x32.png"),
    (32,  2, "icon_32x32@2x.png"),
    (128, 1, "icon_128x128.png"),
    (128, 2, "icon_128x128@2x.png"),
    (256, 1, "icon_256x256.png"),
    (256, 2, "icon_256x256@2x.png"),
    (512, 1, "icon_512x512.png"),
    (512, 2, "icon_512x512@2x.png"),
]


def draw_icon(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    s = float(size)

    # ── Background: deep navy → blue ──────────────────────────────────────────
    bg = QLinearGradient(QPointF(0, 0), QPointF(s * 0.8, s))
    bg.setColorAt(0.0, QColor("#0F172A"))   # slate-900
    bg.setColorAt(1.0, QColor("#1E3A8A"))   # blue-800
    p.setBrush(QBrush(bg))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)

    # ── Layout ────────────────────────────────────────────────────────────────
    cy  = s * 0.60          # pipe center Y (lower half gives room for lock above)
    nr  = s * 0.082         # node circle radius
    pad = s * 0.10          # edge padding
    lx  = pad + nr          # left node center X
    rx  = s - pad - nr      # right node center X
    ph  = s * 0.086         # pipe height

    # ── Tunnel pipe ───────────────────────────────────────────────────────────
    pg = QLinearGradient(QPointF(0, cy - ph/2), QPointF(0, cy + ph/2))
    pg.setColorAt(0.0, QColor(255, 255, 255, 55))
    pg.setColorAt(0.5, QColor(255, 255, 255, 18))
    pg.setColorAt(1.0, QColor(255, 255, 255, 50))
    p.setBrush(QBrush(pg))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(lx, cy - ph/2, rx - lx, ph), ph/2, ph/2)

    # ── Chevron arrows in pipe (skip lock-center zone) ────────────────────────
    if size >= 64:
        ah = ph * 0.52
        arrow_pen = QPen(QColor(147, 197, 253, 200))   # blue-300
        arrow_pen.setWidthF(s * 0.022)
        arrow_pen.setCapStyle(Qt.RoundCap)
        arrow_pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(arrow_pen)
        p.setBrush(Qt.NoBrush)
        for frac in (0.22, 0.78):   # left & right of center lock
            ax = lx + (rx - lx) * frac
            path = QPainterPath()
            path.moveTo(ax - ah * 0.42, cy - ah / 2)
            path.lineTo(ax + ah * 0.42, cy)
            path.lineTo(ax - ah * 0.42, cy + ah / 2)
            p.drawPath(path)
    elif size >= 32:
        lpen = QPen(QColor(147, 197, 253, 160))
        lpen.setWidthF(max(1.0, s * 0.065))
        lpen.setCapStyle(Qt.RoundCap)
        p.setPen(lpen)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(lx + nr, cy), QPointF(rx - nr, cy))

    # ── Left node: blue (local port) ─────────────────────────────────────────
    g_l = QLinearGradient(QPointF(lx, cy - nr), QPointF(lx, cy + nr))
    g_l.setColorAt(0, QColor("#93C5FD"))   # blue-300
    g_l.setColorAt(1, QColor("#1D4ED8"))   # blue-700
    p.setBrush(QBrush(g_l))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(lx, cy), nr, nr)

    # ── Right node: emerald (remote host) ────────────────────────────────────
    g_r = QLinearGradient(QPointF(rx, cy - nr), QPointF(rx, cy + nr))
    g_r.setColorAt(0, QColor("#6EE7B7"))   # emerald-300
    g_r.setColorAt(1, QColor("#047857"))   # emerald-700
    p.setBrush(QBrush(g_r))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(rx, cy), nr, nr)

    # ── Padlock — centered on pipe, hero element ──────────────────────────────
    if size >= 48:
        b_w  = s * 0.220   # body width
        b_h  = s * 0.160   # body height
        b_cx = s * 0.5
        b_x  = b_cx - b_w / 2
        b_y  = cy - b_h / 2    # body vertically centered on pipe

        # Shackle (U-arc above body)
        sh_w = b_w * 0.48
        sh_r = sh_w / 2
        sh_arc_h = sh_r * 1.9   # slightly taller than semicircle
        sh_top = b_y - sh_arc_h

        sp = QPen(QColor("#F59E0B"))         # amber-400
        sp.setWidthF(max(1.5, s * 0.031))
        sp.setCapStyle(Qt.RoundCap)
        p.setPen(sp)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(b_cx - sh_r, sh_top, sh_w, sh_arc_h * 2), 0, 180 * 16)

        # Body gradient (amber)
        bg2 = QLinearGradient(QPointF(b_x, b_y), QPointF(b_x, b_y + b_h))
        bg2.setColorAt(0.0, QColor("#FCD34D"))   # amber-300
        bg2.setColorAt(1.0, QColor("#B45309"))   # amber-700
        p.setBrush(QBrush(bg2))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(b_x, b_y, b_w, b_h), s * 0.026, s * 0.026)

        # Keyhole — circle + stem
        if size >= 80:
            kh_r  = s * 0.021
            kh_cy = b_y + b_h * 0.38
            p.setBrush(QColor(15, 23, 42, 210))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(b_cx, kh_cy), kh_r, kh_r)
            kpen = QPen(QColor(15, 23, 42, 210))
            kpen.setWidthF(kh_r * 1.5)
            kpen.setCapStyle(Qt.RoundCap)
            p.setPen(kpen)
            p.drawLine(QPointF(b_cx, kh_cy + kh_r * 0.9),
                       QPointF(b_cx, b_y + b_h * 0.75))

    p.end()
    return px


# ── Generate iconset ──────────────────────────────────────────────────────────
iconset_dir = Path("SSMTunnel.iconset")
iconset_dir.mkdir(exist_ok=True)
print("아이콘 생성 중...")
for pt, scale, fname in ICONSET:
    px = draw_icon(pt * scale)
    (iconset_dir / fname).with_suffix(".png")
    px.save(str(iconset_dir / fname), "PNG")
    print(f"  {fname}  ({pt * scale}px)")

result = subprocess.run(
    ["iconutil", "-c", "icns", str(iconset_dir), "-o", "icon.icns"],
    capture_output=True, text=True,
)
shutil.rmtree(iconset_dir)

if result.returncode != 0:
    print(f"iconutil 오류:\n{result.stderr}", file=sys.stderr)
    sys.exit(1)
print("icon.icns 생성 완료")
