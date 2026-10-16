# -*- coding: utf-8 -*-
"""悬浮字幕条：透明、置顶、可点击穿透。

只用 Python 标准库（tkinter + ctypes），不引入任何额外依赖。
主线程跑本文件，字幕由后台线程通过 push() 送进来（队列传递，线程安全）。
"""
from __future__ import annotations

import ctypes
import queue
import tkinter as tk

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020   # 点击穿透：鼠标事件直接穿透到下面的窗口
WS_EX_TOOLWINDOW = 0x00000080    # 不出现在 Alt+Tab
WS_EX_NOACTIVATE = 0x08000000    # 不抢焦点


class SubtitleOverlay:
    def __init__(
        self,
        font_size: int = 28,
        source_font_size: int = 15,
        width_ratio: float = 0.82,
        bottom_offset: int = 90,
        alpha: float = 0.85,
        show_source: bool = True,
        click_through: bool = True,
        max_lines: int = 2,
        text_color: str = "#FFFFFF",
        source_color: str = "#9BB8D3",
        background: str = "#000000",
        font_family: str = "Microsoft YaHei",
    ):
        self.show_source = show_source
        self.alpha = alpha
        self.click_through = click_through
        self.max_lines = max(1, max_lines)
        self.width_ratio = width_ratio
        self.bottom_offset = bottom_offset
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._last = ("", "")

        self.root = tk.Tk()
        self.root.title("LiveCaptionZH")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", alpha)
        self.root.configure(bg=background)

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.win_w = int(self.screen_w * width_ratio)

        self.frame = tk.Frame(self.root, bg=background, padx=18, pady=8)
        self.frame.pack(fill="both", expand=True)

        self.lbl_source = tk.Label(
            self.frame, text="", fg=source_color, bg=background,
            font=(font_family, source_font_size), wraplength=self.win_w - 40,
            justify="center", anchor="center",
        )
        self.lbl_text = tk.Label(
            self.frame, text="", fg=text_color, bg=background,
            font=(font_family, font_size, "bold"), wraplength=self.win_w - 40,
            justify="center", anchor="center",
        )
        self.lbl_text.pack(fill="x")
        if self.show_source:
            self.lbl_source.pack(fill="x")

        self.root.geometry(f"{self.win_w}x60+0+0")
        self.root.update_idletasks()
        if self.click_through:
            self._enable_click_through()
        self.root.after(60, self._poll)

    # ---------- 对外接口 ----------
    def push(self, source: str, translation: str) -> None:
        """后台线程调用：送一条字幕进来。"""
        self._queue.put((source or "", translation or ""))

    def run(self) -> None:
        """阻塞，进入界面主循环。"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

    def close(self) -> None:
        try:
            self.root.after(0, self.root.destroy)
        except Exception:
            pass

    # ---------- 内部 ----------
    def _enable_click_through(self) -> None:
        """让字幕条不挡鼠标点击（Windows 专用）。"""
        if not hasattr(ctypes, "windll"):
            return
        user32 = ctypes.windll.user32
        handles = []
        try:
            child = self.root.winfo_id()
            parent = user32.GetParent(child)
            handles = [h for h in (parent, child) if h]
        except Exception:
            return
        LWA_ALPHA = 0x00000002
        for hwnd in handles:
            try:
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
                )
                # 关键：手改 WS_EX_LAYERED 会清掉分层属性，必须重新设置一次，
                # 否则窗口只剩背景、文字完全不渲染（实测踩过）
                user32.SetLayeredWindowAttributes(hwnd, 0, int(255 * 0.85), LWA_ALPHA)
            except Exception:
                pass

    def _poll(self) -> None:
        """主线程定时取队列里的最新字幕。"""
        latest = None
        try:
            while True:
                latest = self._queue.get_nowait()
        except queue.Empty:
            pass
        if latest is not None and latest != self._last:
            self._last = latest
            self._render(*latest)
        self.root.after(60, self._poll)

    def _render(self, source: str, translation: str) -> None:
        main = translation or source          # 还没翻译出来时先显示原文，避免空白
        self.lbl_text.config(text=main)
        if self.show_source:
            self.lbl_source.config(text=source if translation else "")
        self.root.update_idletasks()
        h = max(self.frame.winfo_reqheight(), 40)
        x = max(0, (self.screen_w - self.win_w) // 2)
        y = max(0, self.screen_h - h - self.bottom_offset)
        self.root.geometry(f"{self.win_w}x{h}+{x}+{y}")
        self.root.attributes("-alpha", self.alpha if main.strip() else 0.0)
        self.root.lift()