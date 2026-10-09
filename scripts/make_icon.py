"""앱 아이콘을 그려서 PNG / ICO(Windows) / ICNS(macOS)로 저장한다.

    uv run python scripts/make_icon.py

겹쳐진 PDF 문서 두 장을 그려 '여러 PDF를 하나로 합친다'는 뜻을 담는다.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# offscreen 모드는 시스템 글꼴을 스스로 찾지 못하므로 글꼴 폴더를 알려 준다.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))
elif sys.platform == "darwin":
    os.environ.setdefault("QT_QPA_FONTDIR", "/System/Library/Fonts")

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

SIZE = 1024
ASSETS = Path(__file__).resolve().parent.parent / "src" / "pdf_merger" / "assets"

RED = QColor("#E5484D")
RED_DARK = QColor("#B9232B")
PAPER = QColor("#FFFFFF")
PAPER_BACK = QColor("#FFE1E2")
LINE = QColor("#F3A5A8")


def sheet_path(rect: QRectF, fold: float) -> QPainterPath:
    """오른쪽 위 모서리가 접힌 종이 모양."""
    p = QPainterPath()
    p.moveTo(rect.left(), rect.top())
    p.lineTo(rect.right() - fold, rect.top())
    p.lineTo(rect.right(), rect.top() + fold)
    p.lineTo(rect.right(), rect.bottom())
    p.lineTo(rect.left(), rect.bottom())
    p.closeSubpath()
    return p


def draw_sheet(painter: QPainter, rect: QRectF, fold: float, color: QColor) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPath(sheet_path(rect, fold))
    # 접힌 부분은 살짝 어둡게
    flap = QPainterPath()
    flap.moveTo(rect.right() - fold, rect.top())
    flap.lineTo(rect.right() - fold, rect.top() + fold)
    flap.lineTo(rect.right(), rect.top() + fold)
    flap.closeSubpath()
    painter.setBrush(color.darker(112))
    painter.drawPath(flap)


def draw_icon(size: int = SIZE) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    s = size / SIZE  # 1024 기준 좌표를 실제 크기로 환산

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # 둥근 사각형 배경 (빨간 그라데이션)
    inset = 64 * s
    bg = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    grad = QLinearGradient(QPointF(bg.left(), bg.top()), QPointF(bg.right(), bg.bottom()))
    grad.setColorAt(0, RED)
    grad.setColorAt(1, RED_DARK)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grad)
    painter.drawRoundedRect(bg, 200 * s, 200 * s)

    # 뒤에 깔린 종이 (합쳐지는 다른 PDF)
    back = QRectF(252 * s, 200 * s, 440 * s, 560 * s)
    draw_sheet(painter, back, 110 * s, PAPER_BACK)

    # 앞 종이
    front = QRectF(332 * s, 280 * s, 440 * s, 560 * s)
    draw_sheet(painter, front, 110 * s, PAPER)

    # 글줄 느낌의 선
    painter.setPen(QPen(LINE, 22 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i, w in enumerate((200, 280, 240)):
        y = front.top() + (190 + i * 70) * s
        painter.drawLine(QPointF(front.left() + 60 * s, y), QPointF(front.left() + (60 + w) * s, y))

    # PDF 글자
    font = QFont("Arial")
    font.setBold(True)
    font.setPixelSize(int(140 * s))
    painter.setFont(font)
    painter.setPen(RED_DARK)
    label = QRectF(front.left(), front.bottom() - 220 * s, front.width(), 180 * s)
    painter.drawText(label, Qt.AlignmentFlag.AlignCenter, "PDF")

    painter.end()
    return img


def main() -> None:
    QGuiApplication([])
    ASSETS.mkdir(parents=True, exist_ok=True)

    png = ASSETS / "icon.png"
    draw_icon().save(str(png))

    base = Image.open(png)
    base.save(ASSETS / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    base.save(ASSETS / "icon.icns")
    for f in ("icon.png", "icon.ico", "icon.icns"):
        print(f"{ASSETS / f}  ({(ASSETS / f).stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
