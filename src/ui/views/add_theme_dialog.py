# 檔案：src/ui/views/add_theme_dialog.py
# 新增主題視窗：輸入名稱、選擇明暗與全部色票（Windows 原生選色器），
# 建立後自動建立 assets/themes/<key>/ 資料夾並立即套用。
import customtkinter as ctk
from tkinter import colorchooser, messagebox
from src.ui.theme import Theme
from src.ui import theme_registry
from src.ui.components.auto_hide_scroll import AutoHideScrollableFrame

# 預設配色（粉嫩），作為「套用預設配色」與起始色票
_DARK_DEFAULTS = {
    "BG_DARK": "#18101F", "BG_CARD": "#241B2E",
    "NEON_CYAN": "#FF9EC4", "NEON_PINK": "#FF6B9D", "NEON_YELLOW": "#FFE08A",
    "NEON_GREEN": "#7FE0B0", "NEON_SELECT": "#C9A6FF", "NEON_MAIN": "#FFFFFF",
    "TEXT_MAIN": "#FFFFFF", "TEXT_MUTED": "#B7A9C4",
    "STATUS_PENDING": "#FF6B9D", "STATUS_TRANSFER": "#C9A6FF",
    "BUTTON_DISABLED": "#332A3D", "ON_ACCENT": "#1A0F1F",
}
_LIGHT_DEFAULTS = {
    "BG_DARK": "#FFF6FA", "BG_CARD": "#FFFFFF",
    "NEON_CYAN": "#FF7FB2", "NEON_PINK": "#E5484D", "NEON_YELLOW": "#F5C04A",
    "NEON_GREEN": "#3FBF7F", "NEON_SELECT": "#A78BDA", "NEON_MAIN": "#3D2A33",
    "TEXT_MAIN": "#3D2A33", "TEXT_MUTED": "#8F7D88",
    "STATUS_PENDING": "#E5484D", "STATUS_TRANSFER": "#A78BDA",
    "BUTTON_DISABLED": "#F0E2EA", "ON_ACCENT": "#3D2A33",
}

COLOR_SECTIONS = [
    ("背景與文字", [
        ("BG_DARK", "主背景"),
        ("BG_CARD", "卡片 / 側邊欄"),
        ("TEXT_MAIN", "主文字"),
        ("TEXT_MUTED", "次要文字"),
        ("BUTTON_DISABLED", "停用按鈕"),
    ]),
    ("強調與按鈕", [
        ("NEON_CYAN", "主強調（標題 / 主按鈕）"),
        ("NEON_SELECT", "次強調（選擇 / 轉交按鈕）"),
        ("NEON_MAIN", "強調文字"),
        ("ON_ACCENT", "按鈕上的文字"),
    ]),
    ("狀態色", [
        ("NEON_GREEN", "已處理"),
        ("STATUS_PENDING", "待處理 / 警示"),
        ("STATUS_TRANSFER", "轉交"),
        ("NEON_PINK", "刪除警示"),
        ("NEON_YELLOW", "特別標記"),
    ]),
]


class AddThemeDialog(ctk.CTkToplevel):
    """新增 / 編輯主題視窗。

    傳入 theme_key 為「編輯模式」：預填現有主題的名稱、明暗與色票；
    未傳入則為「新增模式」。on_saved 為編輯非啟用中主題儲存後的回呼（例如刷新選單）。
    """

    def __init__(self, master, theme_key=None, on_saved=None):
        super().__init__(master)
        self.main = master  # MainWindow（用於 apply_theme）
        self.theme_key = theme_key
        self.on_saved = on_saved
        self.is_edit = theme_key is not None
        self.title("編輯主題" if self.is_edit else "新增主題")
        self.geometry("560x700")
        self.resizable(False, False)

        self.name_var = ctk.StringVar()
        self.mode_var = ctk.StringVar(value="dark")
        self.color_buttons = {}

        if self.is_edit:
            existing = theme_registry.all_themes().get(theme_key)
            if existing is None:
                raise ValueError(f"主題不存在：{theme_key}")
            self.colors = dict(existing["colors"])
            self.name_var.set(existing["label"])
            self.mode_var.set(existing["mode"])
        else:
            self.colors = dict(_DARK_DEFAULTS)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_color_area()
        self._build_footer()

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()
        self.focus_set()

    # ==========================================
    # 表頭：名稱 + 明暗
    # ==========================================
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=("✏️ 編輯主題" if self.is_edit else "🎨 新增自訂主題"),
            font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN, anchor="w"
        ).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 4)
        )

        ctk.CTkLabel(header, text="主題名稱", font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w").grid(
            row=1, column=0, sticky="w", padx=12, pady=(4, 2)
        )
        self.entry_name = ctk.CTkEntry(header, textvariable=self.name_var, placeholder_text="例如：灰原哀", height=34)
        self.entry_name.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(header, text="明暗風格", font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w").grid(
            row=3, column=0, sticky="w", padx=12, pady=(2, 2)
        )
        self.mode_seg = ctk.CTkSegmentedButton(
            header, values=["🌙 暗色", "☀️ 明亮"],
            command=self._on_mode_change, font=Theme.FONT_SMALL
        )
        self.mode_seg.set("🌙 暗色" if self.mode_var.get() == "dark" else "☀️ 明亮")
        self.mode_seg.grid(row=4, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 10))

    def _on_mode_change(self, value):
        mode = "light" if value.startswith("☀️") else "dark"
        self.mode_var.set(mode)
        if self.is_edit:
            # 編輯模式：只切換明暗，不覆寫使用者已設定的色票
            return
        defaults = _LIGHT_DEFAULTS if mode == "light" else _DARK_DEFAULTS
        for token, hexv in defaults.items():
            self.colors[token] = hexv
            if token in self.color_buttons:
                self.color_buttons[token].configure(fg_color=hexv, text=hexv)

    # ==========================================
    # 色票區（滾動）
    # ==========================================
    def _build_color_area(self):
        body = AutoHideScrollableFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        body.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
        body.grid_columnconfigure(1, weight=1)

        row = 0
        for section, tokens in COLOR_SECTIONS:
            ctk.CTkLabel(
                body, text=f"◤ {section}", font=Theme.FONT_BODY,
                text_color=Theme.NEON_CYAN, anchor="w"
            ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 2))
            row += 1
            for token, desc in tokens:
                ctk.CTkLabel(
                    body, text=f"{desc}（{token}）", font=Theme.FONT_SMALL,
                    text_color=Theme.TEXT_MAIN, anchor="w"
                ).grid(row=row, column=0, sticky="w", padx=12, pady=3)
                btn = ctk.CTkButton(
                    body, text=self.colors[token], width=110, height=28,
                    fg_color=self.colors[token], text_color=self._text_on(self.colors[token]),
                    hover_color=self.colors[token],
                    command=lambda t=token: self._pick_color(t)
                )
                btn.grid(row=row, column=1, sticky="e", padx=12, pady=3)
                self.color_buttons[token] = btn
                row += 1

    @staticmethod
    def _text_on(hex_color):
        try:
            r = int(hex_color[1:3], 16); g = int(hex_color[3:5], 16); b = int(hex_color[5:7], 16)
            return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFFFFF"
        except (ValueError, IndexError):
            return "#FFFFFF"

    def _pick_color(self, token):
        result = colorchooser.askcolor(color=self.colors.get(token), title=f"選擇 {token}", parent=self)
        if result and result[1]:
            hexv = result[1]
            self.colors[token] = hexv
            self.color_buttons[token].configure(fg_color=hexv, text=hexv, hover_color=hexv, text_color=self._text_on(hexv))

    # ==========================================
    # 底部按鈕
    # ==========================================
    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))

        ctk.CTkButton(
            footer, text="🎀 套用預設配色", fg_color="transparent",
            text_color=Theme.TEXT_MUTED, border_width=1, border_color=Theme.TEXT_MUTED,
            width=120, command=self._apply_preset
        ).pack(side="left")
        ctk.CTkButton(
            footer, text="取消", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=80, command=self.destroy
        ).pack(side="right", padx=(0, 10))
        ctk.CTkButton(
            footer, text=("儲存變更" if self.is_edit else "建立主題"),
            fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=110, command=self._save
        ).pack(side="right")

    def _apply_preset(self):
        defaults = _LIGHT_DEFAULTS if self.mode_var.get() == "light" else _DARK_DEFAULTS
        for token, hexv in defaults.items():
            self.colors[token] = hexv
            self.color_buttons[token].configure(fg_color=hexv, text=hexv, hover_color=hexv, text_color=self._text_on(hexv))

    def _save(self):
        label = self.name_var.get().strip()
        if not label:
            messagebox.showwarning("警告", "請輸入主題名稱", parent=self)
            return
        missing = [t for t in theme_registry.REQUIRED_TOKENS if not self.colors.get(t)]
        if missing:
            messagebox.showwarning("警告", "還有未選擇的色票", parent=self)
            return
        try:
            if self.is_edit:
                key = theme_registry.update_theme(self.theme_key, label, self.mode_var.get(), self.colors)
            else:
                key = theme_registry.add_custom_theme(label, self.mode_var.get(), self.colors)
        except ValueError as e:
            messagebox.showerror("錯誤", str(e), parent=self)
            return

        if self.is_edit:
            if theme_registry.active_theme_name() == key:
                # 編輯的是啟用中主題 → 立即重建介面套用（本視窗與選單一併銷毀）
                if hasattr(self.main, "apply_theme"):
                    self.main.apply_theme(key)
            else:
                # 非啟用中 → 關閉並刷新選單預覽
                self.destroy()
                if self.on_saved:
                    self.on_saved()
            return

        messagebox.showinfo(
            "建立完成",
            f"主題「{label}」已建立並套用！\n\n"
            f"圖片放置資料夾：assets/themes/{key}/\n"
            f"  - mascot.png（側邊欄角色圖）\n"
            f"  - input.png（輸入表單小圖）",
            parent=self,
        )
        # 立即套用（會重建介面，本視窗一併銷毀）
        if hasattr(self.main, "apply_theme"):
            self.main.apply_theme(key)
