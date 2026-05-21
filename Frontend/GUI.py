from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QGraphicsDropShadowEffect,
    QSizePolicy,
)
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QFont,
    QPen,
    QLinearGradient,
    QRadialGradient,
    QBrush,
)
from PyQt5.QtCore import Qt, QTimer, QPointF
from dotenv import dotenv_values
import random
import sys
import os

# ---------------- ENV ----------------
env_vars = dotenv_values(".env")
Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Nexus")
APP_TITLE = "Nexus Intelligence"

old_chat_message = ""

# ---------------- PATHS ----------------
current_dir = os.getcwd()
TempDirPath = os.path.join(current_dir, "Frontend", "Files")
GraphicsDirPath = os.path.join(current_dir, "Frontend", "Graphics")
os.makedirs(TempDirPath, exist_ok=True)

# ---------------- THEME (hacker / matrix) ----------------
COLORS = {
    "bg": "#030806",
    "accent": "#00ff66",
    "accent_dim": "#00aa44",
    "accent_glow": "#b8ffda",
    "matrix_head": "#ffffff",
    "matrix_trail": "#00ff41",
    "matrix_fade": "#00441a",
    "grid": "#0a2e18",
    "scanline": "#00ff88",
    "hud_red": "#ff2244",
    "text": "#e8fff4",
    "muted": "#7a9e8c",
    "panel": "rgba(4, 16, 10, 0.94)",
    "panel_border": "rgba(0, 255, 102, 0.4)",
    "card": "rgba(6, 20, 12, 0.96)",
    "danger": "#ff4466",
    "warn": "#ffee55",
}

# Charset for hacker rain (binary-heavy + hex + symbols)
HACK_BINARY = "01"
HACK_HEX = "0123456789ABCDEF"
HACK_SYMBOLS = "<>|/\\{}[]_$#@&*+=:-"


def TempDirectoryPath(filename):
    return os.path.join(TempDirPath, filename)


def TempFile(path):
    return os.path.join(TempDirPath, path)


def GraphicsFile(path):
    return os.path.join(GraphicsDirPath, path)


def AnswerModifier(text):
    return "\n".join([line.strip() for line in text.split("\n") if line.strip()])


def QueryModifier(query):
    try:
        from Backend.Language import prepare_query
        return prepare_query(query)
    except Exception:
        return (query or "").strip()


def SetMicrophoneStatus(state=None):
    """Mic always ON — ignore off requests."""
    with open(TempFile("Mic.data"), "w", encoding="utf-8") as f:
        f.write("true")


def GetMicrophoneStatus():
    return "true"


def SetAsssistantStatus(state):
    with open(TempFile("Status.data"), "w", encoding="utf-8") as f:
        f.write(state)


def SetAssistantStatus(state):
    SetAsssistantStatus(state)


def GetAssistantStatus():
    try:
        with open(TempFile("Status.data"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Available..."


def ShowTextToScreen(text):
    with open(TempFile("Responses.data"), "w", encoding="utf-8") as f:
        f.write(text)


def MicButtonInitiated():
    SetMicrophoneStatus("true")


def MicButtonClosed():
    SetMicrophoneStatus("true")


# ----------------  BINARY RAIN ----------------
class BinaryRainWidget(QWidget):
    """Matrix / terminal breach — falling streams, grid, scanlines, HUD."""

    COL_W = 15
    CHAR_H = 15

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.columns = []
        self._frame = 0
        self._scan_y = 0.0
        self._glitch_bars = []
        self._font = QFont("Consolas", 10)
        if not self._font.exactMatch():
            self._font = QFont("Courier New", 10)
        self._font.setStyleHint(QFont.Monospace)
        self._font.setBold(False)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(38)

    @staticmethod
    def _rand_char(stream: str) -> str:
        if stream == "hex":
            return random.choice(HACK_HEX)
        if stream == "symbol":
            return random.choice(HACK_SYMBOLS)
        if stream == "mix":
            pool = HACK_BINARY + HACK_HEX + HACK_SYMBOLS
            return random.choice(pool)
        return random.choice(HACK_BINARY)

    def _new_column(self, index: int, h: int):
        stream = random.choices(
            ["binary", "binary", "hex", "mix", "symbol"],
            weights=[45, 25, 15, 10, 5],
        )[0]
        length = random.randint(12, 28)
        return {
            "x": index * self.COL_W + random.randint(-2, 2),
            "y": random.uniform(-h * 0.6, 0),
            "speed": random.uniform(3.0, 9.5),
            "length": length,
            "stream": stream,
            "chars": [self._rand_char(stream) for _ in range(length)],
            "bright_head": random.random() > 0.35,
        }

    def _init_columns(self):
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        count = max(20, w // self.COL_W + 3)
        self.columns = [self._new_column(i, h) for i in range(count)]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._init_columns()

    def _tick(self):
        self._frame += 1
        h = self.height()
        self._scan_y = (self._scan_y + 4.5) % max(h, 1)

        for i, col in enumerate(self.columns):
            col["y"] += col["speed"]
            trail_end = col["y"] - col["length"] * self.CHAR_H
            if trail_end > h + 40:
                self.columns[i] = self._new_column(i, h)
            elif random.random() < 0.12:
                idx = random.randint(0, col["length"] - 1)
                col["chars"][idx] = self._rand_char(col["stream"])
            elif random.random() < 0.04 and col["length"] > 4:
                tail = random.randint(max(0, col["length"] - 4), col["length"] - 1)
                col["chars"][tail] = self._rand_char(col["stream"])

        if random.random() < 0.06 and h > 0:
            self._glitch_bars.append({
                "y": random.randint(0, h),
                "h": random.randint(2, 8),
                "life": random.randint(2, 6),
                "dx": random.randint(-3, 3),
            })
        self._glitch_bars = [
            {**g, "life": g["life"] - 1, "y": g["y"] + g.get("dx", 0) // 2}
            for g in self._glitch_bars
            if g["life"] > 0
        ]

        self.update()

    def _draw_background(self, p: QPainter, w: int, h: int):
        p.fillRect(0, 0, w, h, QColor("#020504"))

        grad = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.72)
        grad.setColorAt(0.0, QColor(0, 40, 20, 35))
        grad.setColorAt(0.55, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 200))
        p.fillRect(0, 0, w, h, QBrush(grad))

        edge = QLinearGradient(0, 0, w, 0)
        edge.setColorAt(0.0, QColor(255, 30, 60, 18))
        edge.setColorAt(0.08, QColor(0, 0, 0, 0))
        edge.setColorAt(0.92, QColor(0, 0, 0, 0))
        edge.setColorAt(1.0, QColor(255, 30, 60, 18))
        p.fillRect(0, 0, w, h, QBrush(edge))

    def _draw_grid(self, p: QPainter, w: int, h: int):
        grid_c = QColor(COLORS["grid"])
        grid_c.setAlpha(55)
        p.setPen(QPen(grid_c, 1))
        step = 48
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

        fine = QColor(COLORS["grid"])
        fine.setAlpha(22)
        p.setPen(QPen(fine, 1))
        for x in range(0, w, 16):
            if x % step != 0:
                p.drawLine(x, 0, x, h)

    def _draw_streams(self, p: QPainter, h: int):
        p.setFont(self._font)
        for col in self.columns:
            x = int(col["x"])
            y_head = col["y"]
            chars = col["chars"]
            for i, ch in enumerate(chars):
                y = int(y_head - i * self.CHAR_H)
                if y < -24 or y > h + 24:
                    continue

                if i == 0:
                    if col["bright_head"]:
                        c = QColor(COLORS["matrix_head"])
                        c.setAlpha(255)
                    else:
                        c = QColor(COLORS["accent_glow"])
                        c.setAlpha(230)
                elif i == 1:
                    c = QColor(COLORS["matrix_trail"])
                    c.setAlpha(220)
                elif i < 4:
                    c = QColor(COLORS["accent"])
                    c.setAlpha(max(120, 200 - i * 35))
                else:
                    fade = max(18, 130 - i * 9)
                    c = QColor(COLORS["matrix_fade"])
                    c.setAlpha(fade)

                p.setPen(c)
                p.drawText(x, y, ch)

    def _draw_scanlines(self, p: QPainter, w: int, h: int):
        line_c = QColor(0, 0, 0, 38)
        for y in range(0, h, 3):
            p.fillRect(0, y, w, 1, line_c)

        beam = int(self._scan_y)
        for offset, alpha in [(0, 90), (6, 35), (-6, 35)]:
            c = QColor(COLORS["scanline"])
            c.setAlpha(alpha)
            p.fillRect(0, beam + offset, w, 2, c)

        flicker = 12 + int(8 * abs((self._frame % 30) - 15) / 15)
        top_g = QLinearGradient(0, 0, 0, 80)
        top_g.setColorAt(0, QColor(0, 255, 120, flicker))
        top_g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, 80, QBrush(top_g))

    def _draw_glitch(self, p: QPainter, w: int):
        for g in self._glitch_bars:
            c = QColor(COLORS["matrix_trail"])
            c.setAlpha(70)
            p.fillRect(0, g["y"], w, g["h"], c)
            c2 = QColor(COLORS["hud_red"])
            c2.setAlpha(40)
            p.fillRect(4, g["y"] + 1, w - 8, max(1, g["h"] - 1), c2)

    def _draw_hud(self, p: QPainter, w: int, h: int):
        hud = QColor(COLORS["accent"])
        hud.setAlpha(100)
        red = QColor(COLORS["hud_red"])
        red.setAlpha(120)
        margin, arm = 22, 36
        p.setPen(QPen(hud, 1))

        for (x1, y1, x2, y2) in [
            (margin, margin, margin + arm, margin),
            (margin, margin, margin, margin + arm),
            (w - margin, margin, w - margin - arm, margin),
            (w - margin, margin, w - margin, margin + arm),
            (margin, h - margin, margin + arm, h - margin),
            (margin, h - margin, margin, h - margin - arm),
            (w - margin, h - margin, w - margin - arm, h - margin),
            (w - margin, h - margin, w - margin, h - margin - arm),
        ]:
            p.drawLine(x1, y1, x2, y2)

        p.setPen(QPen(red, 1))
        tag = "root@nexus:~# breach_detected"
        p.setFont(QFont("Consolas", 9))
        p.drawText(margin + 6, margin + 14, tag)
        p.drawText(margin + 6, h - margin - 8, f"stream // matrix [{len(self.columns)} cols]")

        pulse = 180 + int(75 * abs((self._frame % 40) - 20) / 20)
        dot = QColor(COLORS["matrix_trail"])
        dot.setAlpha(pulse)
        p.setBrush(QBrush(dot))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(w - margin - 10, margin + 12), 4, 4)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        w, h = self.width(), self.height()

        self._draw_background(p, w, h)
        self._draw_grid(p, w, h)
        self._draw_streams(p, h)
        self._draw_glitch(p, w)
        self._draw_scanlines(p, w, h)
        self._draw_hud(p, w, h)


# CRT-style overlay — UI readable, hacker vibe retained
class ContentScrim(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()

        center = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * 0.55)
        center.setColorAt(0.0, QColor(2, 8, 5, 95))
        center.setColorAt(0.7, QColor(2, 6, 4, 150))
        center.setColorAt(1.0, QColor(0, 0, 0, 175))
        p.fillRect(self.rect(), QBrush(center))

        top = QLinearGradient(0, 0, 0, 120)
        top.setColorAt(0, QColor(0, 255, 100, 8))
        top.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, 120, QBrush(top))


# ---------------- CHAT PANEL ----------------
class ChatSection(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatPanel")
        self.setStyleSheet(f"""
            QFrame#chatPanel {{
                background: {COLORS["panel"]};
                border: 1px solid {COLORS["panel_border"]};
                border-radius: 14px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        chat_header = QLabel("💬  Conversation")
        chat_header.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["accent_glow"]};
                font-size: 15px;
                font-weight: 600;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
                padding-bottom: 2px;
            }}
        """)
        layout.addWidget(chat_header)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setFrameShape(QFrame.NoFrame)
        self.chat.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                color: {COLORS["text"]};
                font-family: 'Segoe UI', 'Bahnschrift', sans-serif;
                font-size: 14px;
                line-height: 1.5;
                border: none;
                padding: 4px;
            }}
            QScrollBar:vertical {{
                background: rgba(0,0,0,0.3);
                width: 8px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS["accent_dim"]};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        layout.addWidget(self.chat)

        try:
            from Backend.Language import is_english_ui
            if is_english_ui():
                hint = (
                    "Speak in <b>English</b> (Indian accent is fine). "
                    "I control your PC, search the web, and read your screen."
                )
            else:
                hint = "Roman Hinglish ya Hindi mein bolo — main PC control kar sakti hun."
        except Exception:
            hint = "Speak in English. I control your PC and search the web."
        welcome = (
            f'<p style="color:{COLORS["text"]}; margin:0 0 8px 0; font-size:15px;">'
            f'<b style="color:{COLORS["accent"]};">Welcome!</b></p>'
            f'<p style="color:{COLORS["muted"]}; margin:0; line-height:1.6;">{hint}</p>'
        )
        self.chat.setHtml(welcome)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_chat)
        self._timer.start(120)

    def _append_formatted(self, raw: str):
        lines = raw.split("\n")
        html_parts = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith(f"{Username}:"):
                body = line[len(f"{Username}:"):].strip()
                html_parts.append(
                    f'<p style="margin:6px 0 2px 0;">'
                    f'<span style="color:{COLORS["accent_glow"]}; font-weight:600;">{Username}</span>'
                    f'<span style="color:{COLORS["muted"]};"> › </span>'
                    f'<span style="color:{COLORS["text"]};">{body}</span></p>'
                )
            elif line.startswith(f"{Assistantname}:"):
                body = line[len(f"{Assistantname}:"):].strip()
                html_parts.append(
                    f'<p style="margin:10px 0 4px 0;">'
                    f'<span style="color:{COLORS["accent"]}; font-weight:600;">{Assistantname}</span>'
                    f'<span style="color:{COLORS["muted"]};"> › </span>'
                    f'<span style="color:{COLORS["text"]};">{body}</span></p>'
                )
            else:
                html_parts.append(
                    f'<p style="color:{COLORS["text"]}; margin:4px 0;">{line}</p>'
                )
        if html_parts:
            self.chat.append("".join(html_parts))

    def _update_chat(self):
        global old_chat_message
        try:
            with open(TempFile("Responses.data"), "r", encoding="utf-8") as f:
                msg = f.read().strip()
            if msg and msg != old_chat_message:
                self._append_formatted(msg)
                old_chat_message = msg
        except FileNotFoundError:
            pass


# ---------------- STATUS BADGE ----------------
class StatusBadge(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS["card"]};
                border: 1px solid {COLORS["panel_border"]};
                border-radius: 10px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)

        lbl_static = QLabel("Status:")
        lbl_static.setStyleSheet(f"color: {COLORS['muted']}; font-size: 13px; background: transparent;")

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {COLORS['accent']}; font-size: 12px; background: transparent;")

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["accent_glow"]};
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }}
        """)

        lay.addWidget(lbl_static)
        lay.addWidget(self.status_dot)
        lay.addWidget(self.status_label)
        lay.addStretch()

    def set_status(self, status: str):
        try:
            from Backend.Language import is_english_ui
            english = is_english_ui()
        except Exception:
            english = True
        if english:
            friendly = {
                "available...": "Ready — microphone always on",
                "listening...": "Listening...",
                "thinking...": "Thinking...",
                "searching...": "Searching the web...",
                "answering...": "Speaking answer...",
                "executing on pc...": "Running on your PC...",
                "running powershell...": "Running PowerShell...",
                "running cmd...": "Running CMD...",
                "opening gmail...": "Opening Gmail...",
                "opening chrome...": "Opening Chrome...",
                "running": "Online",
            }
        else:
            friendly = {
                "available...": "Listening — mic always ON",
                "listening...": "Listening...",
                "thinking...": "Thinking...",
                "searching...": "Searching...",
                "answering...": "Answering...",
                "running": "Online",
            }
        key = status.strip().lower()
        text = friendly.get(key, status)
        self.status_label.setText(text)

        busy = key in ("listening...", "thinking...", "searching...", "answering...")
        color = COLORS["warn"] if key == "thinking..." else COLORS["accent_glow"]
        if not busy:
            color = COLORS["accent_dim"]
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")


# ---------------- MAIN WINDOW ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        self.setStyleSheet(f"QMainWindow {{ background: {COLORS['bg']}; }}")

        # Layered root: rain → content
        root = QWidget()
        self.setCentralWidget(root)

        rain = BinaryRainWidget(root)
        rain.setGeometry(0, 0, self.width(), self.height())

        scrim = ContentScrim(root)
        scrim.setGeometry(0, 0, self.width(), self.height())
        scrim.raise_()

        content = QWidget(root)
        content.setStyleSheet("background: transparent;")
        content.raise_()

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        # --- Header ---
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        title = QLabel(APP_TITLE)
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont("Segoe UI", 28, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["accent_glow"]};
                letter-spacing: 3px;
                background: transparent;
            }}
        """)
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(28)
        glow.setColor(QColor(COLORS["accent"]))
        glow.setOffset(0, 0)
        title.setGraphicsEffect(glow)

        subtitle = QLabel(f"AI Assistant  ·  Powered by {Assistantname}")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["muted"]};
                font-size: 13px;
                letter-spacing: 1px;
                background: transparent;
            }}
        """)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addWidget(header)

        self.status_badge = StatusBadge()
        main_layout.addWidget(self.status_badge)

        # --- Chat ---
        self.chat_panel = ChatSection()
        self.chat_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.chat_panel, stretch=1)

        # Sync status from file (do NOT overwrite Main.py status)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._sync_status)
        self._status_timer.start(200)

        self._rain = rain
        self._scrim = scrim
        self._content = content

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_rain"):
            w, h = self.width(), self.height()
            self._rain.setGeometry(0, 0, w, h)
            self._scrim.setGeometry(0, 0, w, h)
            self._content.setGeometry(0, 0, w, h)

    def _sync_status(self):
        status = GetAssistantStatus() or "Available..."
        self.status_badge.set_status(status)


def GraphicalUserInterface():
    SetMicrophoneStatus("true")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    GraphicalUserInterface()
