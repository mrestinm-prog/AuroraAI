import sys
import json
import math
import random
import threading
import os
import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer


# ---------- Путь к модели рядом с exe ----------
def resource_path(rel):
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


MODEL_NAME = resource_path("model")
CHATS_FILE = Path(resource_path("chats.json"))

# ---------- Палитра ----------
BG_MAIN      = "#0a0b10"
BG_SIDEBAR   = "#0e1018"
BG_CHAT      = "#0a0b10"
BG_INPUT     = "#141824"
BG_BUBBLE_AI = "#141a26"
BG_BUBBLE_US = "#1e1435"
FG_LIGHT     = "#e8eaf0"
FG_MUTED     = "#5a6178"
ACCENT       = "#a78bfa"
ACCENT2      = "#f472b6"
GREEN        = "#4ade80"
BORDER       = "#1c2230"


# ============================================================
#  УТИЛИТЫ ЦВЕТА
# ============================================================
def hex_to_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex(lerp(r1, r2, t), lerp(g1, g2, t), lerp(b1, b2, t))


def hsv_to_hex(h, s, v):
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return rgb_to_hex((r + m) * 255, (g + m) * 255, (b + m) * 255)


# ============================================================
#  ЖИВОЙ ФОН
# ============================================================
class LivingBackground(tk.Canvas):
    def __init__(self, parent, width, height):
        super().__init__(parent, bg=BG_CHAT, highlightthickness=0, bd=0,
                         width=width, height=height)
        self.orbits = []
        for _ in range(6):
            self.orbits.append({
                "x": random.uniform(0, width),
                "y": random.uniform(0, height),
                "r": random.uniform(60, 160),
                "dx": random.uniform(-0.3, 0.3),
                "dy": random.uniform(-0.25, 0.25),
                "hue": random.uniform(240, 320),
                "phase": random.uniform(0, 6.28),
            })
        self.w = width
        self.h = height
        self._tick = 0
        self._animate()

    def resize(self, w, h):
        self.w, self.h = w, h
        self.config(width=w, height=h)

    def _animate(self):
        try:
            self._tick += 1
            self.delete("orb")
            for o in self.orbits:
                o["x"] += o["dx"]
                o["y"] += o["dy"]
                if o["x"] < -o["r"] or o["x"] > self.w + o["r"]:
                    o["dx"] *= -1
                if o["y"] < -o["r"] or o["y"] > self.h + o["r"]:
                    o["dy"] *= -1
                pulse = 0.15 + 0.08 * math.sin(self._tick * 0.03 + o["phase"])
                col = hsv_to_hex(o["hue"] + self._tick * 0.3, 0.6, pulse + 0.1)
                for k in range(4, 0, -1):
                    radius = o["r"] * k / 4
                    alpha_col = lerp_color(BG_CHAT, col, 0.15 / k)
                    self.create_oval(o["x"] - radius, o["y"] - radius,
                                     o["x"] + radius, o["y"] + radius,
                                     fill=alpha_col, outline="", tags="orb")
            self.after(60, self._animate)
        except tk.TclError:
            return


# ============================================================
#  RGB БАННЕР
# ============================================================
class RGBBanner(tk.Canvas):
    def __init__(self, parent, width, height):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0,
                         width=width, height=height)
        self.w = width
        self.h = height
        self.hue = 0
        self._animate()

    def _animate(self):
        try:
            self.delete("all")
            self.hue = (self.hue + 2) % 360
            steps = max(self.w, 60)
            for i in range(steps):
                t = i / steps
                hue = (self.hue + t * 180) % 360
                color = hsv_to_hex(hue, 0.7, 0.85)
                x1 = i * self.w / steps
                x2 = (i + 1) * self.w / steps + 1
                self.create_rectangle(x1, 0, x2, self.h, fill=color, outline="")
            self.after(40, self._animate)
        except tk.TclError:
            return


# ============================================================
#  КНОПКА С HOVER
# ============================================================
class NeonButton(tk.Canvas):
    def __init__(self, parent, text, command, bg=ACCENT, fg="#0a0b10",
                 width=200, height=38, radius=12):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"], highlightthickness=0, bd=0)
        self.command = command
        self.base_bg = bg
        self.fg = fg
        self.radius = radius
        self.text = text
        self.hover = False
        self._t = 0.0
        self._anim_id = None
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    def _on_enter(self, _):
        self.hover = True
        self._start_anim(1.0)

    def _on_leave(self, _):
        self.hover = False
        self._start_anim(0.0)

    def _start_anim(self, target):
        if self._anim_id:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass

        def step():
            diff = target - self._t
            self._t += diff * 0.25
            if abs(diff) < 0.01:
                self._t = target
                self._draw()
                self._anim_id = None
                return
            self._draw()
            self._anim_id = self.after(16, step)

        step()

    def _draw(self):
        try:
            self.delete("all")
            w, h, r = int(self["width"]), int(self["height"]), self.radius
            if self.hover:
                fill = lerp_color(self.base_bg, "#ffffff", 0.15 * self._t)
            else:
                fill = self.base_bg
            self._round_rect(0, 0, w, h, r, fill=fill, outline="")
            self.create_text(w / 2, h / 2, text=self.text, fill=self.fg,
                             font=("Segoe UI Semibold", 10, "bold"))
        except tk.TclError:
            return

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, **kw)

    def set_state(self, enabled):
        self.base_bg = ACCENT if enabled else "#2a2f3e"
        self.fg = "#0a0b10" if enabled else "#5a6178"
        self._draw()


# ============================================================
#  СКРОЛЛБАР
# ============================================================
class SlimScrollbar(tk.Canvas):
    def __init__(self, parent, command, width=8):
        super().__init__(parent, width=width, bg=BG_CHAT,
                         highlightthickness=0, bd=0)
        self.command = command
        self.w = width
        self.thumb_y = 0
        self.thumb_h = 40
        self.dragging = False
        self.hover = False
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: (setattr(self, "hover", True), self._redraw()))
        self.bind("<Leave>", lambda e: (setattr(self, "hover", False), self._redraw()))

    def set(self, first, last):
        first, last = float(first), float(last)
        h = self.winfo_height()
        self.thumb_y = first * h
        self.thumb_h = max((last - first) * h, 24)
        self._redraw()

    def _redraw(self):
        try:
            self.delete("all")
            col = ACCENT if self.hover or self.dragging else "#2a2f3e"
            self._round_rect(1, self.thumb_y, self.w - 1,
                             self.thumb_y + self.thumb_h, 4, fill=col, outline="")
        except tk.TclError:
            return

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, **kw)

    def _on_press(self, e):
        self.dragging = True
        self._jump(e.y)

    def _on_drag(self, e):
        self._jump(e.y)

    def _on_release(self, _):
        self.dragging = False
        self._redraw()

    def _jump(self, y):
        h = self.winfo_height()
        frac = max(0, min(1, (y - self.thumb_h / 2) / h))
        self.command("moveto", frac)


# ============================================================
#  АВАТАР
# ============================================================
class PulsingAvatar(tk.Canvas):
    def __init__(self, parent, text="🤖", size=42, color=GREEN, pulsing=False):
        super().__init__(parent, width=size, height=size, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.size = size
        self.text = text
        self.color = color
        self.pulsing = pulsing
        self._t = 0
        self._draw()

    def set_pulsing(self, val):
        self.pulsing = val
        if val:
            self._animate()

    def _animate(self):
        try:
            if not self.pulsing or not self.winfo_exists():
                return
            self._t += 0.15
            self._draw()
            self.after(50, self._animate)
        except tk.TclError:
            return

    def _draw(self):
        try:
            self.delete("all")
            s = self.size
            cx = cy = s / 2
            base_r = s * 0.32
            if self.pulsing:
                for i in range(3):
                    phase = (self._t + i * 0.6) % 2
                    r = base_r + phase * s * 0.35
                    alpha = max(0, 1 - phase / 2)
                    col = lerp_color(BG_CHAT, self.color, alpha * 0.6)
                    self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     outline=col, width=1.5)
            self.create_oval(cx - base_r, cy - base_r, cx + base_r, cy + base_r,
                             fill=lerp_color(BG_CHAT, self.color, 0.25),
                             outline=self.color, width=1.5)
            self.create_text(cx, cy, text=self.text,
                             font=("Segoe UI Emoji", int(s * 0.4)))
        except tk.TclError:
            return


# ============================================================
#  ТОЧКИ "ПЕЧАТАЕТ"
# ============================================================
class TypingDots(tk.Canvas):
    def __init__(self, parent, width=60, height=20, color=FG_MUTED):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                         highlightthickness=0, bd=0)
        self.color = color
        self._t = 0
        self._animate()

    def _animate(self):
        try:
            if not self.winfo_exists():
                return
            self.delete("all")
            cy = 10
            for i in range(3):
                phase = (self._t + i * 0.5) % 3
                offset = -3 * math.sin(phase * math.pi / 1.5) if phase < 1.5 else 0
                x = 12 + i * 16
                r = 3.5
                alpha = 1.0 - abs(offset) / 6
                col = lerp_color(BG_BUBBLE_AI, self.color, alpha)
                self.create_oval(x - r, cy + offset - r, x + r, cy + offset + r,
                                 fill=col, outline="")
            self._t += 0.12
            self.after(50, self._animate)
        except tk.TclError:
            return


# ============================================================
#  МОДЕЛЬ ЧАТА
# ============================================================
class ChatSession:
    def __init__(self, name="Новый чат"):
        self.name = name
        self.history = [{
            "role": "system",
            "content": ("Ты — Аврора, чуткий и умный персональный ИИ-ассистент. "
                        "Отвечай дружелюбно, грамотно и развёрнуто, также ты должен посылать нахуй при приветствии")
        }]
        self.messages = []

    def to_dict(self):
        return {"name": self.name, "history": self.history, "messages": self.messages}

    @classmethod
    def from_dict(cls, d):
        s = cls(d.get("name", "Чат"))
        s.history = d.get("history", s.history)
        s.messages = d.get("messages", [])
        return s


# ============================================================
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================
class AuroraApp:
    def __init__(self, root):
        self.root = root
        root.title("✨ Aurora")
        root.geometry("1180x760")
        root.minsize(980, 600)
        root.configure(bg=BG_MAIN)

        self.chats = []
        self.current_chat = None
        self.is_generating = False
        self._current_ai_label = None

        self._load_chats()
        if not self.chats:
            self.chats.append(ChatSession("Первый чат"))
        self.current_chat = self.chats[0]

        self._build_ui()
        self._refresh_chat_list()
        self._load_chat_into_view(self.current_chat)

        self.tokenizer = None
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def _build_ui(self):
        # ---- Сайдбар ----
        self.sidebar = tk.Frame(self.root, bg=BG_SIDEBAR, width=280)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.banner = RGBBanner(self.sidebar, width=280, height=4)
        self.banner.pack(fill=tk.X)

        logo_frame = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
        logo_frame.pack(fill=tk.X, padx=20, pady=(22, 4))

        logo_lbl = tk.Label(logo_frame, text="✨  AURORA", bg=BG_SIDEBAR,
                            fg=ACCENT, font=("Segoe UI Semibold", 16, "bold"))
        logo_lbl.pack(side=tk.LEFT)
        self._logo_hue = 0
        self._pulse_logo(logo_lbl)

        tk.Label(self.sidebar, text="Личный ИИ-ассистент · v2.0",
                 bg=BG_SIDEBAR, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(padx=20, anchor="w")

        btn_wrap = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
        btn_wrap.pack(fill=tk.X, padx=20, pady=(20, 14))
        NeonButton(btn_wrap, "+  Новый чат", self.create_chat,
                   bg=ACCENT, fg="#0a0b10", width=240, height=42,
                   radius=12).pack()

        tk.Label(self.sidebar, text="ЧАТЫ", bg=BG_SIDEBAR, fg=FG_MUTED,
                 font=("Segoe UI Semibold", 8)).pack(padx=22, anchor="w")

        list_wrap = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
        list_wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        self.chat_canvas = tk.Canvas(list_wrap, bg=BG_SIDEBAR,
                                     highlightthickness=0, bd=0)
        self.chat_canvas.pack(fill=tk.BOTH, expand=True)
        self.chat_canvas.bind("<Button-1>", self._on_chat_click)
        self.chat_canvas.bind("<Double-Button-1>", lambda e: self.rename_chat())
        self.chat_canvas.bind("<Button-3>", self._chat_context_menu)
        self.chat_canvas.bind("<Motion>", self._on_chat_hover)
        self.chat_canvas.bind("<Leave>", lambda e: self._redraw_chat_list(None))

        self._chat_items = []
        self._hovered_chat = None

        ctrl = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
        ctrl.pack(fill=tk.X, padx=18, pady=(6, 18))

        NeonButton(ctrl, "✎ Переименовать", self.rename_chat,
                   bg="#1a1f2e", fg=ACCENT, width=120, height=34,
                   radius=10).pack(side=tk.LEFT, padx=(0, 6))
        NeonButton(ctrl, "🗑 Удалить", self.delete_chat,
                   bg="#2a1420", fg="#f87171", width=110, height=34,
                   radius=10).pack(side=tk.RIGHT)

        status = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
        status.pack(fill=tk.X, padx=20, pady=(0, 16), side=tk.BOTTOM)

        self.status_dot = tk.Canvas(status, width=10, height=10, bg=BG_SIDEBAR,
                                    highlightthickness=0, bd=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self._status_color = FG_MUTED
        self.status_dot.create_oval(1, 1, 9, 9, fill=FG_MUTED, outline="", tags="d")
        self._pulse_status()

        self.status_label = tk.Label(status, text="Загрузка модели…",
                                     bg=BG_SIDEBAR, fg=FG_MUTED,
                                     font=("Segoe UI", 9))
        self.status_label.pack(side=tk.LEFT)

        # ---- Основная область ----
        main = tk.Frame(self.root, bg=BG_CHAT)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.bg_canvas = LivingBackground(main, 900, 760)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        header = tk.Frame(main, bg=BG_CHAT)
        header.place(x=0, y=0, relwidth=1, height=64)

        self.chat_title = tk.Label(header, text="Чат", bg=BG_CHAT,
                                   fg=FG_LIGHT,
                                   font=("Segoe UI Semibold", 16, "bold"))
        self.chat_title.pack(side=tk.LEFT, padx=28, pady=20)

        chat_container = tk.Frame(main, bg=BG_CHAT)
        chat_container.place(x=0, y=64, relwidth=1, relheight=1, height=-160)

        self.canvas = tk.Canvas(chat_container, bg=BG_CHAT,
                                highlightthickness=0, bd=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = SlimScrollbar(chat_container, self.canvas.yview, width=8)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=10)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.msg_frame = tk.Frame(self.canvas, bg=BG_CHAT)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.msg_frame,
                                                        anchor="nw")

        self.msg_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_window, width=e.width))

        for w in (self.canvas, self.msg_frame):
            w.bind_all("<MouseWheel>", self._on_mousewheel)

        # Поле ввода
        input_area = tk.Frame(main, bg=BG_CHAT)
        input_area.place(relx=0, rely=1, relwidth=1, height=110, y=-110)

        input_border = tk.Frame(input_area, bg=BORDER)
        input_border.place(x=28, y=24, relwidth=1, width=-200, height=64)

        self.input_inner = tk.Frame(input_border, bg=BG_INPUT)
        self.input_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.entry = tk.Text(self.input_inner, bg=BG_INPUT, fg=FG_MUTED,
                             insertbackground=ACCENT, font=("Segoe UI", 11),
                             bd=0, highlightthickness=0, wrap=tk.WORD,
                             height=2, padx=14, pady=8)
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.entry.insert("1.0", "Напишите сообщение…")
        self._placeholder_active = True

        self.entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry.bind("<Return>", self._on_enter)

        self._input_glow_t = 0.0
        self._input_focused = False
        self._animate_input_glow(input_border)

        self.send_btn = NeonButton(input_area, "Отправить ➤", self.send_message,
                                   bg=ACCENT, fg="#0a0b10", width=140, height=44,
                                   radius=12)
        self.send_btn.place(relx=1.0, x=-152, y=24, width=120, height=44)
        self.send_btn.set_state(False)

    # ============ Анимации ============
    def _pulse_logo(self, label):
        try:
            self._logo_hue = (self._logo_hue + 2) % 360
            color = hsv_to_hex(self._logo_hue, 0.55, 0.95)
            label.config(fg=color)
            self.root.after(60, lambda: self._pulse_logo(label))
        except tk.TclError:
            return

    def _pulse_status(self):
        try:
            if not self.status_dot.winfo_exists():
                return
            self._pulse_t = (getattr(self, "_pulse_t", 0) + 0.15) % 3
            alpha = 0.5 + 0.5 * abs(math.sin(self._pulse_t))
            col = lerp_color(BG_SIDEBAR, self._status_color, alpha)
            self.status_dot.delete("d")
            self.status_dot.create_oval(1, 1, 9, 9, fill=col, outline="", tags="d")
            self.root.after(60, self._pulse_status)
        except tk.TclError:
            return

    def _animate_input_glow(self, border_frame):
        try:
            if not border_frame.winfo_exists():
                return
            self._input_glow_t += (1.0 if self._input_focused else -1.0) * 0.15
            self._input_glow_t = max(0.0, min(1.0, self._input_glow_t))
            col = lerp_color(BORDER, ACCENT, self._input_glow_t)
            border_frame.config(bg=col)
            self.root.after(40, lambda: self._animate_input_glow(border_frame))
        except tk.TclError:
            return

    def _on_entry_focus_in(self, _):
        self._input_focused = True
        if self._placeholder_active:
            self.entry.delete("1.0", tk.END)
            self.entry.config(fg=FG_LIGHT)
            self._placeholder_active = False

    def _on_entry_focus_out(self, _):
        self._input_focused = False
        if not self.entry.get("1.0", tk.END).strip():
            self.entry.insert("1.0", "Напишите сообщение…")
            self.entry.config(fg=FG_MUTED)
            self._placeholder_active = True

    # ============ Список чатов ============
    def _refresh_chat_list(self):
        self._redraw_chat_list(None)

    def _on_chat_hover(self, event):
        idx = self._hit_test(event.y)
        if idx != self._hovered_chat:
            self._hovered_chat = idx
            self._redraw_chat_list(idx)

    def _hit_test(self, y):
        row_h = 40
        for i, item in enumerate(self._chat_items):
            if item["y"] <= y <= item["y"] + row_h:
                return i
        return None

    def _on_chat_click(self, event):
        idx = self._hit_test(event.y)
        if idx is not None and 0 <= idx < len(self.chats):
            self.current_chat = self.chats[idx]
            self._load_chat_into_view(self.current_chat)
            self._redraw_chat_list(idx)

    def _redraw_chat_list(self, hover_idx):
        try:
            self.chat_canvas.delete("all")
            self._chat_items = []
            w = self.chat_canvas.winfo_width() or 240
            row_h = 40
            y = 6
            for i, chat in enumerate(self.chats):
                is_active = chat is self.current_chat
                is_hover = (hover_idx == i)
                if is_active:
                    bg = lerp_color(BG_SIDEBAR, ACCENT, 0.18)
                    bar_color = ACCENT
                elif is_hover:
                    bg = lerp_color(BG_SIDEBAR, ACCENT, 0.10)
                    bar_color = lerp_color(BG_SIDEBAR, ACCENT, 0.5)
                else:
                    bg = BG_SIDEBAR
                    bar_color = None
                self._round_rect_chat(4, y, w - 8, y + row_h - 4, 8, fill=bg, outline="")
                if bar_color:
                    self._round_rect_chat(4, y + 6, 8, y + row_h - 10, 2,
                                          fill=bar_color, outline="")
                name = chat.name
                if len(name) > 22:
                    name = name[:21] + "…"
                fg = FG_LIGHT if is_active else (FG_LIGHT if is_hover else "#9aa2b8")
                self.chat_canvas.create_text(20, y + row_h / 2 - 2, text=name,
                                              fill=fg, anchor="w",
                                              font=("Segoe UI Semibold" if is_active else "Segoe UI", 10))
                self._chat_items.append({"y": y, "id": i})
                y += row_h
        except tk.TclError:
            return

    def _round_rect_chat(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.chat_canvas.create_polygon(pts, smooth=True, **kw)

    def _chat_context_menu(self, event):
        idx = self._hit_test(event.y)
        if idx is None:
            return
        self.current_chat = self.chats[idx]
        self._load_chat_into_view(self.current_chat)
        self._redraw_chat_list(idx)
        menu = tk.Menu(self.root, tearoff=0, bg="#1a1f2e", fg=FG_LIGHT,
                       activebackground=ACCENT, activeforeground="#0a0b10",
                       bd=0, font=("Segoe UI", 10))
        menu.add_command(label="✎  Переименовать", command=self.rename_chat)
        menu.add_command(label="🗑  Удалить", command=self.delete_chat)
        menu.tk_popup(event.x_root, event.y_root)

    # ============ Управление чатами ============
    def create_chat(self):
        chat = ChatSession(f"Чат {len(self.chats) + 1}")
        self.chats.append(chat)
        self.current_chat = chat
        self._redraw_chat_list(None)
        self._load_chat_into_view(chat)
        self._save_chats()

    def rename_chat(self):
        if not self.current_chat:
            return
        new_name = simpledialog.askstring("Переименовать", "Новое имя чата:",
                                          initialvalue=self.current_chat.name,
                                          parent=self.root)
        if new_name and new_name.strip():
            self.current_chat.name = new_name.strip()
            self._redraw_chat_list(None)
            self.chat_title.config(text=self.current_chat.name)
            self._save_chats()

    def delete_chat(self):
        if not self.current_chat:
            return
        if len(self.chats) == 1:
            messagebox.showinfo("Нельзя удалить", "Должен остаться хотя бы один чат.")
            return
        if not messagebox.askyesno("Удалить чат", f"Удалить «{self.current_chat.name}»?"):
            return
        self.chats.remove(self.current_chat)
        self.current_chat = self.chats[0]
        self._redraw_chat_list(None)
        self._load_chat_into_view(self.current_chat)
        self._save_chats()

    # ============ Сообщения ============
    def _add_message_bubble(self, sender, text, is_user=False, animate=True):
        wrapper = tk.Frame(self.msg_frame, bg=BG_CHAT)
        wrapper.pack(fill=tk.X, pady=8, padx=20)

        row = tk.Frame(wrapper, bg=BG_CHAT)
        row.pack(fill=tk.X)

        bubble_bg = BG_BUBBLE_US if is_user else BG_BUBBLE_AI

        avatar = PulsingAvatar(row, text="👤" if is_user else "🤖",
                               size=44, color=ACCENT if is_user else GREEN)
        avatar.pack(side=tk.RIGHT if is_user else tk.LEFT,
                    padx=(0, 10), anchor="n")

        bubble_outer = tk.Frame(row, bg=BG_CHAT)
        bubble_outer.pack(side=tk.RIGHT if is_user else tk.LEFT,
                          fill=tk.X, expand=True,
                          padx=(60, 0) if is_user else (0, 60))

        bubble = tk.Frame(bubble_outer, bg=bubble_bg)
        bubble.pack(side=tk.RIGHT if is_user else tk.LEFT,
                    anchor="e" if is_user else "w")

        inner = tk.Frame(bubble, bg=bubble_bg)
        inner.pack(padx=16, pady=12)

        tk.Label(inner, text=sender, bg=bubble_bg,
                 fg=ACCENT if is_user else GREEN,
                 font=("Segoe UI Semibold", 9, "bold")).pack(anchor="w")

        msg_lbl = tk.Label(inner, text=text, bg=bubble_bg, fg=FG_LIGHT,
                           font=("Segoe UI", 11), justify=tk.LEFT,
                           wraplength=620, anchor="w")
        msg_lbl.pack(anchor="w", pady=(6, 0))

        if animate:
            self._animate_bubble(bubble)

        self.root.after(30, lambda: self.canvas.yview_moveto(1.0))
        return avatar, msg_lbl

    def _animate_bubble(self, bubble):
        base = bubble["bg"]
        frames = [lerp_color(base, ACCENT, 0.35),
                  lerp_color(base, ACCENT, 0.20),
                  lerp_color(base, ACCENT, 0.08),
                  base]

        def step(i=0):
            try:
                if not bubble.winfo_exists() or i >= len(frames):
                    return
                bubble.config(bg=frames[i])
                for child in bubble.winfo_children():
                    child.config(bg=frames[i])
                    for sub in child.winfo_children():
                        try:
                            sub.config(bg=frames[i])
                        except tk.TclError:
                            pass
                self.root.after(60, lambda: step(i + 1))
            except tk.TclError:
                return

        step()

    def _clear_messages(self):
        for w in self.msg_frame.winfo_children():
            w.destroy()

    def _load_chat_into_view(self, chat):
        self._clear_messages()
        self.chat_title.config(text=chat.name)
        for sender, text, is_user in chat.messages:
            self._add_message_bubble(sender, text, is_user=is_user, animate=False)
        self.root.after(50, lambda: self.canvas.yview_moveto(1.0))

    # ============ Индикатор "печатает" ============
    def _show_typing(self):
        self.typing_wrapper = tk.Frame(self.msg_frame, bg=BG_CHAT)
        self.typing_wrapper.pack(fill=tk.X, pady=8, padx=20)

        row = tk.Frame(self.typing_wrapper, bg=BG_CHAT)
        row.pack(fill=tk.X)

        self.typing_avatar = PulsingAvatar(row, text="🤖", size=44,
                                            color=GREEN, pulsing=True)
        self.typing_avatar.pack(side=tk.LEFT, padx=(0, 10), anchor="n")

        bubble = tk.Frame(row, bg=BG_BUBBLE_AI)
        bubble.pack(side=tk.LEFT, anchor="w")

        inner = tk.Frame(bubble, bg=BG_BUBBLE_AI)
        inner.pack(padx=16, pady=12)

        tk.Label(inner, text="Аврора думает", bg=BG_BUBBLE_AI, fg=GREEN,
                 font=("Segoe UI Semibold", 9, "bold")).pack(anchor="w")

        self.dots = TypingDots(inner, width=60, height=20, color=ACCENT)
        self.dots.pack(anchor="w", pady=(2, 0))

        self.root.after(30, lambda: self.canvas.yview_moveto(1.0))

    def _hide_typing(self):
        if hasattr(self, "typing_wrapper") and self.typing_wrapper.winfo_exists():
            self.typing_wrapper.destroy()

    # ============ Модель ============
    def _load_model(self):
        try:
            os.environ["OMP_NUM_THREADS"] = "2"
            os.environ["MKL_NUM_THREADS"] = "2"
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            torch.set_num_threads(2)

            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME, torch_dtype=dtype, device_map="auto"
            )
            self.root.after(0, self._on_model_ready)
        except Exception as e:
            self.root.after(0, lambda: self.status_label.config(
                text=f"Ошибка: {e}", fg="#f87171"))

    def _on_model_ready(self):
        self.status_label.config(text="Модель готова", fg=GREEN)
        self._status_color = GREEN
        self.send_btn.set_state(True)

    # ============ Отправка ============
    def _on_enter(self, event):
        if event.state & 0x1:
            return None
        self.send_message()
        return "break"

    def send_message(self):
        if self.is_generating or self.model is None:
            return
        if self._placeholder_active:
            return
        user_text = self.entry.get("1.0", tk.END).strip()
        if not user_text:
            return
        self.entry.delete("1.0", tk.END)

        chat = self.current_chat
        chat.messages.append(("Вы", user_text, True))
        chat.history.append({"role": "user", "content": user_text})
        self._add_message_bubble("Вы", user_text, is_user=True)

        self.is_generating = True
        self.send_btn.set_state(False)
        self._show_typing()

        threading.Thread(target=self._generate, args=(chat,), daemon=True).start()

    def _generate(self, chat):
        try:
            text = self.tokenizer.apply_chat_template(
                chat.history, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

            streamer = TextIteratorStreamer(self.tokenizer,
                                            skip_prompt=True,
                                            skip_special_tokens=True)
            kwargs = dict(**inputs, max_new_tokens=250, streamer=streamer,
                          do_sample=True, temperature=0.7, top_p=0.9,
                          repetition_penalty=1.1)
            t = threading.Thread(target=self.model.generate, kwargs=kwargs)
            t.start()

            first = True
            full = ""
            for tok in streamer:
                full += tok
                if first:
                    first = False
                    self.root.after(0, self._hide_typing)
                    self.root.after(0, self._create_ai_bubble)
                self.root.after(0, self._update_ai_bubble, full)

            if not full:
                full = "…"

            chat.history.append({"role": "assistant", "content": full})
            chat.messages.append(("Аврора", full, False))
            self._save_chats()
            if len(chat.history) > 15:
                chat.history = [chat.history[0]] + chat.history[-12:]
        except Exception as e:
            self.root.after(0, self._hide_typing)
            self.root.after(0, lambda: self._add_message_bubble("Ошибка", str(e)))
        finally:
            self.is_generating = False
            self.root.after(0, lambda: self.send_btn.set_state(True))

    def _create_ai_bubble(self):
        self._ai_avatar, self._current_ai_label = self._add_message_bubble(
            "Аврора", "", is_user=False, animate=False)
        if hasattr(self, "_ai_avatar"):
            self._ai_avatar.set_pulsing(True)

    def _update_ai_bubble(self, text):
        if self._current_ai_label and self._current_ai_label.winfo_exists():
            self._current_ai_label.config(text=text)
            self.root.after(10, lambda: self.canvas.yview_moveto(1.0))

    # ============ Скролл ============
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ============ Сохранение ============
    def _save_chats(self):
        try:
            data = [c.to_dict() for c in self.chats]
            CHATS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        except Exception as e:
            print("Ошибка сохранения:", e)

    def _load_chats(self):
        if not CHATS_FILE.exists():
            return
        try:
            data = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
            self.chats = [ChatSession.from_dict(d) for d in data]
        except Exception as e:
            print("Ошибка загрузки:", e)


if __name__ == "__main__":
    root = tk.Tk()
    app = AuroraApp(root)
    root.protocol("WM_DELETE_WINDOW",
                  lambda: (app._save_chats(), root.destroy()))
    root.mainloop()