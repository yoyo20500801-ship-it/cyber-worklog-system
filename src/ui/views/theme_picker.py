# 檔案：src/ui/views/theme_picker.py
import customtkinter as ctk
from tkinter import messagebox
from src.ui.theme import Theme
from src.ui import theme_registry
from src.ui.views.add_theme_dialog import AddThemeDialog


class ThemePickerDialog(ctk.CTkToplevel):
    """主題選擇視窗：列出所有主題，可新增/刪除自訂主題、隱藏/顯示任何主題。"""

    PREVIEW_TOKENS = ("BG_DARK", "BG_CARD", "NEON_CYAN", "NEON_GREEN", "NEON_SELECT")

    def __init__(self, master):
        super().__init__(master)
        self.title("主題選擇")
        self.geometry("520x560")
        self.resizable(False, False)
        self.main = master  # MainWindow

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(4, 10))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._refresh()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))
        ctk.CTkButton(
            btn_frame, text="關閉", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=90, command=self.destroy
        ).pack(side="right")

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()
        self.focus_set()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="🎨 選擇主題（套用後會重建介面，未存檔的表單輸入會被清空）",
            font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="➕ 新增主題", font=Theme.FONT_SMALL,
            fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=100, command=self._open_add
        ).grid(row=0, column=1, sticky="e", padx=(10, 0))

    # ==========================================
    # 清單
    # ==========================================
    def _refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        active = theme_registry.active_theme_name()
        for name, theme in theme_registry.list_themes().items():
            self._build_row(name, theme, active)

    def _build_row(self, name, theme, active):
        is_active = name == active
        is_custom = theme_registry.is_custom(name)
        hidden = theme_registry.is_hidden(name)

        row = ctk.CTkFrame(self.scroll, fg_color=Theme.BG_DARK, corner_radius=8)
        row.pack(fill="x", pady=6, padx=2)
        if is_active:
            row.configure(border_width=2, border_color=Theme.NEON_CYAN)
        elif hidden:
            row.configure(border_width=1, border_color=Theme.TEXT_MUTED)

        # 左側色票預覽
        swatch = ctk.CTkFrame(row, fg_color="transparent")
        swatch.pack(side="left", padx=(12, 10), pady=10)
        for token in self.PREVIEW_TOKENS:
            ctk.CTkFrame(
                swatch, width=16, height=16, corner_radius=3,
                fg_color=theme["colors"].get(token, "#888888")
            ).pack(side="left", padx=1)

        # 中段：名稱 + 標記 + 明暗/圖片
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=10)
        name_line = theme["label"]
        if is_custom:
            name_line = f"{name_line}　(自訂)"
        if hidden:
            name_line = f"{name_line}　[已隱藏]"
        ctk.CTkLabel(
            info, text=name_line, font=Theme.FONT_BODY,
            text_color=Theme.TEXT_MAIN if not hidden else Theme.TEXT_MUTED, anchor="w"
        ).pack(fill="x")
        mode_text = "🌙 暗色" if theme["mode"] == "dark" else "☀️ 明亮"
        has_img = (theme_registry.asset_path(name, "mascot") is not None
                   or theme_registry.asset_path(name, "input") is not None)
        ctk.CTkLabel(
            info,
            text=f"{mode_text}" + ("　・　🖼 有圖片裝飾" if has_img else ""),
            font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w"
        ).pack(fill="x")

        # 右側按鈕（由右至左：使用 / 隱藏|顯示 / 刪除）
        if is_active:
            ctk.CTkLabel(
                row, text="✓ 使用中", font=Theme.FONT_SMALL,
                text_color=Theme.NEON_GREEN, width=80
            ).pack(side="right", padx=10)
        else:
            ctk.CTkButton(
                row, text="使用", width=70, fg_color=Theme.NEON_CYAN,
                text_color=Theme.ON_ACCENT, hover_color=Theme.NEON_GREEN,
                command=lambda n=name: self._apply(n)
            ).pack(side="right", padx=10)

            if hidden:
                ctk.CTkButton(
                    row, text="👁 顯示", width=70, fg_color="transparent",
                    text_color=Theme.TEXT_MUTED, border_width=1, border_color=Theme.TEXT_MUTED,
                    command=lambda n=name: self._toggle_hidden(n, False)
                ).pack(side="right", padx=(0, 5))
            else:
                btn_hide = ctk.CTkButton(
                    row, text="🙈 隱藏", width=70, fg_color="transparent",
                    text_color=Theme.TEXT_MUTED, border_width=1, border_color=Theme.TEXT_MUTED,
                    command=lambda n=name: self._toggle_hidden(n, True)
                )
                btn_hide.pack(side="right", padx=(0, 5))

            if is_custom:
                ctk.CTkButton(
                    row, text="🗑️ 刪除", width=70, fg_color=Theme.NEON_PINK,
                    text_color=Theme.TEXT_MAIN,
                    command=lambda n=name: self._delete(n)
                ).pack(side="right", padx=(0, 5))

    # ==========================================
    # 動作
    # ==========================================
    def _open_add(self):
        AddThemeDialog(self.main)  # 建立後 apply_theme 重建，會連本視窗一起銷毀

    def _apply(self, theme_name):
        main = self.main
        self.destroy()
        if hasattr(main, "apply_theme"):
            main.apply_theme(theme_name)

    def _toggle_hidden(self, name, hidden):
        theme_registry.set_hidden(name, hidden)
        self._refresh()

    def _delete(self, name):
        theme = theme_registry.all_themes().get(name, {})
        label = theme.get("label", name)
        if not messagebox.askyesno("確認刪除", f"確定刪除主題「{label}」？此操作不可逆！", parent=self):
            return

        delete_assets = False
        folder = theme_registry.ASSETS_ROOT / name
        if folder.is_dir():
            delete_assets = messagebox.askyesno(
                "圖片資料夾",
                f"是否同時刪除圖片資料夾 assets/themes/{name}/？\n（建議保留，方便以後重新使用）",
                parent=self, default=messagebox.NO,
            )

        was_active = theme_registry.active_theme_name() == name
        theme_registry.delete_custom_theme(name, delete_assets=delete_assets)
        if was_active:
            # 回退到預設主題並重建介面
            if hasattr(self.main, "apply_theme"):
                self.main.apply_theme(theme_registry.DEFAULT_THEME)
        else:
            self._refresh()
