# 檔案：src/ui/views/main_window.py
import customtkinter as ctk
import threading
import webbrowser
import calendar
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
from src.ui.theme import Theme
from src.ui import theme_registry
from src.core import updater
from src.db.repository import Repository
from src.core.excel_exporter import ExcelExporter # 引入匯出引擎
from src.utils.date_helper import selectable_years, to_roc_date
from src.ui.views.settings_view import SettingsView
from src.ui.views.transfer_view import TransferSystemView
from src.ui.views.db_search_view import DatabaseSearchView
from src.ui.views.overview_view import OverviewView
from src.ui.views.mail_view import MailView
from src.ui.views.theme_picker import ThemePickerDialog
from src.ui import phone_input
from src.ui.components.auto_hide_scroll import AutoHideScrollableFrame
from src.ui.components.pager import PaginationBar
from src.ui.components.batch import batch_render


def _safe_image_label(master, key, size):
    """依目前主題載入 assets 圖檔；缺檔或 Pillow 不可用時回傳 None（自動降級）。"""
    path = theme_registry.asset_path(key=key)
    if path is None:
        return None
    try:
        from PIL import Image
        image = ctk.CTkImage(
            light_image=Image.open(path),
            dark_image=Image.open(path),
            size=size,
        )
        return ctk.CTkLabel(master, image=image, text="", fg_color="transparent")
    except Exception:
        return None


# ==========================================
# 主視窗元件
# ==========================================
class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("工作日誌系統")
        self.geometry("1280x768") 
        self.configure(fg_color=Theme.BG_DARK)

        # 設定視窗圖示（左上角 + 工作列）；缺檔或失敗時沿用預設，不影響啟動
        _assets = Path(__file__).resolve().parent.parent.parent.parent / "assets"
        _icon = _assets / "app.ico"
        if _icon.exists():
            try:
                self.iconbitmap(str(_icon))
            except Exception:
                pass
        _png = _assets / "app.png"
        if _png.exists():
            try:
                self._app_icon_image = tk.PhotoImage(file=str(_png))
                self.iconphoto(True, self._app_icon_image)
            except Exception:
                pass

        self.current_view_name = "dashboard"
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main_frame()
        
        # 預設顯示 Dashboard
        self.show_view("dashboard")

        # 延遲一點點，等介面出現後再背景檢查更新（連線失敗時靜默略過）
        self.after(1200, self._start_background_update_check)
        # 啟動時背景同步客戶來信（已設定帳號且開啟自動同步時）
        self.after(1800, self._start_background_mail_sync)

    def _build_sidebar(self):
        """建構左側導覽列"""
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=0, width=250)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1) 

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="工作日誌\n紀錄系統", 
            font=Theme.FONT_HEADING,
            text_color=Theme.NEON_CYAN
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(40, 40))

        # 導覽按鈕 1：總覽
        self.btn_overview = ctk.CTkButton(
            self.sidebar_frame, text="📊 總覽", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK,
            command=lambda: self.show_view("overview")
        )
        self.btn_overview.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        # 導覽按鈕 2：工作紀錄
        self.btn_dashboard = ctk.CTkButton(
            self.sidebar_frame, text="💻工作紀錄", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MAIN, hover_color=Theme.BG_DARK,
            command=lambda: self.show_view("dashboard")
        )
        self.btn_dashboard.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # 導覽按鈕 3：客戶來信
        self.btn_mail = ctk.CTkButton(
            self.sidebar_frame, text="📩客戶來信", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK,
            command=lambda: self.show_view("mail")
        )
        self.btn_mail.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        # 導覽按鈕 4：系統設定
        self.btn_settings = ctk.CTkButton(
            self.sidebar_frame, text="⚙️系統設定", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK,
            command=lambda: self.show_view("settings")
        )
        self.btn_settings.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        # 導覽按鈕 5：轉交系統
        self.btn_transfer = ctk.CTkButton(
            self.sidebar_frame, text="📚 轉交系統", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK,
            command=lambda: self.show_view("transfer")
        )
        self.btn_transfer.grid(row=5, column=0, padx=20, pady=10, sticky="ew")

        # 導覽按鈕 6：資料庫搜尋
        self.btn_dbs = ctk.CTkButton(
            self.sidebar_frame, text="🔍 資料庫搜尋", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK,
            command=lambda: self.show_view("dbsearch")
        )
        self.btn_dbs.grid(row=6, column=0, padx=20, pady=10, sticky="ew")

        theme_label = theme_registry.active_theme().get("label", "主題")
        self.btn_theme = ctk.CTkButton(
            self.sidebar_frame, text=f"🎨 {theme_label}", font=Theme.FONT_BODY,
            fg_color="transparent", text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK,
            command=self.open_theme_picker
        )
        self.btn_theme.grid(row=8, column=0, padx=20, pady=10, sticky="ew")

        # === 底部：主題功能（row 7 為彈性空白，下列會被推到底部） ===
        self.mascot_label = _safe_image_label(self.sidebar_frame, "mascot", (225, 300))
        if self.mascot_label is not None:
            self.mascot_label.grid(row=9, column=0, pady=(0, 5), sticky="s")

        

    def _build_main_frame(self):
        """建構右側主工作區（其餘視圖延遲到第一次切到時才建立，加速啟動）。"""
        self.main_frame = ctk.CTkFrame(self, fg_color=Theme.BG_DARK, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # 預設首頁（工作紀錄）立即建立；其餘視圖首次切到時才建立
        self.view_dashboard = WorklogView(self.main_frame)
        self.view_dashboard.grid(row=0, column=0, sticky="nsew")
        self.view_overview = None
        self.view_mail = None
        self.view_settings = None
        self.view_transfer = None
        self.view_dbs = None

    def _get_view(self, view_name):
        """取得（必要時建立）指定視圖。"""
        view = getattr(self, f"view_{view_name}")
        if view is None:
            if view_name == "settings":
                view = SettingsView(
                    self.main_frame,
                    on_data_changed_callback=self.view_dashboard.load_projects_from_db,
                )
            else:
                factory = {
                    "overview": OverviewView,
                    "mail": MailView,
                    "transfer": TransferSystemView,
                    "dbsearch": DatabaseSearchView,
                }[view_name]
                view = factory(self.main_frame)
            setattr(self, f"view_{view_name}", view)
            view.grid(row=0, column=0, sticky="nsew")
        return view

    def show_view(self, view_name):
        """頁面切換控制機制"""
        self.current_view_name = view_name
        active_btn = {
            "overview": self.btn_overview,
            "dashboard": self.btn_dashboard,
            "mail": self.btn_mail,
            "settings": self.btn_settings,
            "transfer": self.btn_transfer,
            "dbsearch": self.btn_dbs,
        }[view_name]
        view = self._get_view(view_name)
        if view_name == "settings":
            view.refresh_mail_blocklist()
        # 這三頁會重設為當月；資料沒變動時略過重建，避免切頁卡頓
        if view_name in ("overview", "dashboard", "transfer") and hasattr(view, "reset_to_now"):
            view.reset_to_now()
        view.tkraise()  # 將指定頁面置頂
        for btn in (self.btn_overview, self.btn_dashboard, self.btn_mail, self.btn_settings, self.btn_transfer, self.btn_dbs):
            if btn is active_btn:
                btn.configure(border_width=1, border_color=Theme.NEON_CYAN, text_color=Theme.TEXT_MAIN)
            else:
                btn.configure(border_width=0, text_color=Theme.TEXT_MUTED)

    # ==========================================
    # 主題切換（直接重建整個介面）
    # ==========================================
    def open_theme_picker(self):
        ThemePickerDialog(self)

    def apply_theme(self, theme_name):
        if not theme_registry.set_active_theme(theme_name, persist=True):
            return
        ctk.set_appearance_mode(theme_registry.get_theme_mode())
        self.rebuild()

    def rebuild(self):
        """重建側邊欄與所有視圖並恢復目前所在頁面（未存檔輸入會清空）。"""
        current = getattr(self, "current_view_name", "dashboard")
        for child in self.winfo_children():
            child.destroy()
        self.configure(fg_color=Theme.BG_DARK)
        self._build_sidebar()
        self._build_main_frame()
        self.show_view(current)

    # ==========================================
    # 自動更新
    # ==========================================
    def _start_background_update_check(self):
        """背景執行緒檢查更新；有新版時回主執行緒詢問是否更新。"""

        def work():
            result = updater.check_for_update()
            self.after(0, lambda: self._handle_update_result(result, startup=True))

        threading.Thread(target=work, daemon=True).start()

    def _start_background_mail_sync(self):
        """啟動時若已設定信箱帳號且開啟自動同步，背景抓取客戶來信。"""
        from src.core import mail_config, mail_service

        cfg = mail_config.load_config()
        if not cfg.get("auto_sync") or not mail_config.is_configured(cfg):
            return

        def work():
            mail_service.fetch_new(cfg)
            self.after(0, self._refresh_mail_view)

        threading.Thread(target=work, daemon=True).start()

    def _refresh_mail_view(self):
        view = self._get_view("mail")
        view.refresh_list()

    def _handle_update_result(self, result, startup=False):
        if result is None:
            return
        if "error" in result:
            # 啟動時連線失敗靜默略過；手動檢查失敗才提示
            if not startup:
                messagebox.showwarning("檢查更新", result["error"], parent=self)
            return
        if not messagebox.askyesno(
            "發現新版本",
            f"發現新版本 {result['tag']}，是否立即更新？\n\n"
            "程式會自動下載、關閉並重新啟動，\n你的資料（工作紀錄、設定、主題圖）不會遺失。",
            parent=self,
        ):
            return
        self._apply_update_in_background(result["zip_url"], result["tag"])

    def _apply_update_in_background(self, zip_url, tag):
        def work():
            ok, msg = updater.apply_update(zip_url, tag)
            self.after(0, lambda: self._on_apply_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _on_apply_done(self, ok, msg):
        if not ok:
            messagebox.showerror("更新失敗", msg, parent=self)
            return
        # 更新程式已啟動（會等本程式關閉），稍等後關閉主程式讓它接手
        self.after(300, self.destroy)

# ==========================================
# 客製化元件：動態增長多行輸入框
# ==========================================
class AutoResizingTextbox(ctk.CTkTextbox):
    def __init__(self, master, placeholder_text="", min_height=32, max_height=150, default_text_color=None, phone_field=False, **kwargs):
        if default_text_color is None:
            default_text_color = Theme.TEXT_MAIN
        super().__init__(master, height=min_height, wrap="word", border_width=1, border_color=Theme.TEXT_MUTED, **kwargs)
        self.min_height = min_height
        self.max_height = max_height
        self.placeholder_text = placeholder_text
        self.default_text_color = default_text_color
        self.is_placeholder = True
        if self.placeholder_text:
            self.insert("0.0", self.placeholder_text)
            self.configure(text_color=Theme.TEXT_MUTED)
        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._restore_placeholder)
        self.bind("<KeyRelease>", self._adjust_height)
        self.bind("<Tab>", self._focus_next)
        self.bind("<Shift-Tab>", self._focus_prev) 
        if phone_field:
            phone_input.bind_phone_input(self)
        
    def _clear_placeholder(self, event=None):
        if self.is_placeholder:
            self.delete("0.0", "end")
            self.configure(text_color=self.default_text_color)
            self.is_placeholder = False
            
    def _restore_placeholder(self, event=None):
        if self.get("0.0", "end-1c").strip() == "":
            self.is_placeholder = True
            self.delete("0.0", "end")
            self.insert("0.0", self.placeholder_text)
            self.configure(text_color=Theme.TEXT_MUTED)
            self.configure(height=self.min_height)
            
    def _adjust_height(self, event=None):
        if self.is_placeholder: return
        try:
            res = self._textbox.count("1.0", "end", "displaylines")
            lines = res[0] if res else 1
        except:
            lines = len(self.get("0.0", "end").split("\n"))
        new_height = max(self.min_height, min((lines * 20) + 12, self.max_height))
        self.configure(height=new_height)
        
    def _focus_next(self, event):
        event.widget.tk_focusNext().focus()
        return "break"
    def _focus_prev(self, event):
        event.widget.tk_focusPrev().focus()
        return "break"
    def get_value(self):
        return "" if self.is_placeholder else self.get("0.0", "end-1c").strip()
    def set_value(self, text):
        self.delete("0.0", "end")
        if text:
            self.insert("0.0", text)
            self.configure(text_color=self.default_text_color)
            self.is_placeholder = False
        else:
            self._restore_placeholder()
        self._adjust_height()
    def clear_text(self):
        self.delete("0.0", "end")
        self._restore_placeholder()

# ==========================================
# 主視圖類別
# ==========================================
class WorklogView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=1) 
        self.grid_columnconfigure(0, weight=1)
        
        self.start_datetime = None
        self.finish_datetime = None
        self.current_status = "已處理"
        self.editing_log_id = None 
        self.selected_logs = {}     
        self.current_logs_data = {} 

        now = datetime.now()
        self.filter_year_var = ctk.StringVar(value=str(now.year))
        self.filter_month_var = ctk.StringVar(value=str(now.month).zfill(2))
        self.history_status_var = ctk.StringVar(value="全部")

        self.all_project_names = []
        self.all_school_names = []
        self.all_personnel_names = []

        self._data_version = -1
        self._render_seq = 0
        self._refresh_after_id = None

        self._build_form()
        self._build_list()
        self.load_projects_from_db()
        self.refresh_list()
        
    def _setup_searchable_combo(self, combo, var, all_names_attr, callback=None, placeholder=""):
        """獨立搜尋與點選：Enter搜尋並展開，原生滑鼠點擊觸發 callback。
        額外處理：值仍是提示字時，一輸入就清空；輸入後失焦且空白時，恢復提示字。"""
        def on_enter(event):
            current_all_names = getattr(self, all_names_attr, [])
            search_term = var.get().strip()
            
            if self._is_placeholder(search_term):
                filtered = current_all_names
            else:
                filtered = [name for name in current_all_names if search_term in name]
                
            combo.configure(values=filtered if filtered else ["【無符合結果】"])
            if hasattr(combo, '_open_dropdown_menu'):
                combo._open_dropdown_menu()

        def clear_placeholder_on_type(event=None):
            # 只在輸入實質內容（字元 / BackSpace / Delete）時清空提示，
            # 修飾鍵（Shift/Ctrl/Alt）不會誤觸發
            keysym = getattr(event, 'keysym', '') or ''
            if event is None or getattr(event, 'char', '') or keysym in ("BackSpace", "Delete", "KP_Delete"):
                if self._is_placeholder(var.get()):
                    var.set("")
            return None

        def restore_placeholder(event=None):
            # 輸入後失焦且內容空白 → 恢復提示字
            if not var.get().strip():
                var.set(placeholder)
            return None

        combo.bind("<Return>", on_enter)
        if hasattr(combo, '_entry'):
            combo._entry.bind("<Return>", on_enter)
            combo._entry.bind("<KeyPress>", clear_placeholder_on_type)
            combo._entry.bind("<FocusOut>", restore_placeholder)
            
        if callback:
            combo.configure(command=callback)

    def _build_form(self):
        form_frame = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        form_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20), ipadx=10, ipady=10)
        
        topbar = ctk.CTkFrame(form_frame, fg_color="transparent")
        topbar.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 15), sticky="ew")

        ctk.CTkLabel(topbar, text="工作日誌", font=Theme.FONT_HEADING, text_color=Theme.NEON_CYAN).pack(side="left")

        self.date_var = ctk.StringVar(value=str(datetime.now().date()))
        self.top_combo_year = ctk.CTkComboBox(
            topbar, values=selectable_years(Repository.get_min_worklog_year()),
            variable=self.filter_year_var, width=80, command=self._on_year_month_change
        )
        self.top_combo_year.pack(side="left", padx=(25, 5))
        self.top_combo_month = ctk.CTkComboBox(
            topbar, values=[str(m).zfill(2) for m in range(1, 13)],
            variable=self.filter_month_var, width=60, command=self._on_year_month_change
        )
        self.top_combo_month.pack(side="left", padx=5)

        ctk.CTkLabel(topbar, text="日期", font=Theme.FONT_BODY, text_color=Theme.TEXT_MUTED).pack(side="left", padx=(20, 5))
        self.date_entry = ctk.CTkEntry(topbar, textvariable=self.date_var, width=120)
        self.date_entry.pack(side="left")
        
        self.project_var = ctk.StringVar(value="【請設定專案資料】")
        self.project_combo = ctk.CTkComboBox(form_frame, variable=self.project_var, values=["【請設定專案資料】"], width=160)
        self.project_combo.grid(row=1, column=0, padx=10, pady=5, sticky="nw")
        self._setup_searchable_combo(self.project_combo, self.project_var, 'all_project_names', self.on_project_select, placeholder="【請選擇專案】")
        
        self.school_var = ctk.StringVar(value="【請設定學校】")
        self.school_combo = ctk.CTkComboBox(form_frame, variable=self.school_var, values=["【請設定學校】"], width=160)
        self.school_combo.grid(row=1, column=1, padx=10, pady=5, sticky="nw")
        self._setup_searchable_combo(self.school_combo, self.school_var, 'all_school_names', placeholder="【請選擇學校】")
        
        self.btn_open_browser = ctk.CTkButton(form_frame, text="🌐 導向專案", font=Theme.FONT_BODY, fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT, hover_color=Theme.NEON_GREEN, command=self.open_browser_and_start)
        self.btn_open_browser.grid(row=1, column=2, padx=10, pady=5, sticky="nw")

        self.phone_entry = AutoResizingTextbox(form_frame, placeholder_text="電話/#分機", width=160, phone_field=True)
        self.phone_entry.grid(row=2, column=0, padx=10, pady=5, sticky="nw")
        
        self.contact_entry = AutoResizingTextbox(form_frame, placeholder_text="聯絡人", width=160)
        self.contact_entry.grid(row=2, column=1, padx=10, pady=5, sticky="nw")
        
        self.pii_entry = AutoResizingTextbox(form_frame, placeholder_text="個資", width=280, default_text_color=Theme.NEON_PINK)
        self.pii_entry.grid(row=2, column=2, columnspan=2, padx=10, pady=5, sticky="nw")

        self.issue_entry = AutoResizingTextbox(form_frame, placeholder_text="問題內容...", width=340)
        self.issue_entry.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="nw")
        
        self.solution_entry = AutoResizingTextbox(form_frame, placeholder_text="處理情形...", width=340)
        self.solution_entry.grid(row=3, column=2, columnspan=2, padx=10, pady=5, sticky="nw")

        # --- 狀態切換與人員選單區 ---
        self.status_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        self.status_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=15, sticky="w")
        
        self.btn_status_done = ctk.CTkButton(self.status_frame, text="已處理", width=80, command=lambda: self.set_status("已處理"))
        self.btn_status_done.pack(side="left", padx=(0, 5))
        self.btn_status_pending = ctk.CTkButton(self.status_frame, text="待處理", width=80, command=lambda: self.set_status("待處理"))
        self.btn_status_pending.pack(side="left", padx=5)
        self.btn_status_transfer = ctk.CTkButton(self.status_frame, text="轉交", width=80, command=lambda: self.set_status("轉交"))
        self.btn_status_transfer.pack(side="left", padx=5)
        
        # 人員下拉選單：預設灰色字體提示
        self.personnel_var = ctk.StringVar(value="【無須轉交】")
        self.personnel_combo = ctk.CTkComboBox(
            self.status_frame, variable=self.personnel_var, values=["【無須轉交】"], width=130, 
            state="disabled", text_color=Theme.TEXT_MUTED
        )
        self.personnel_combo.pack(side="left", padx=(10, 0))
        self._setup_searchable_combo(self.personnel_combo, self.personnel_var, 'all_personnel_names', self._on_personnel_selected, placeholder="【請選擇人員】")

        self.update_status_buttons_ui()
        
        self.btn_clear = ctk.CTkButton(form_frame, text="清空", width=100, fg_color="transparent", border_width=1, border_color=Theme.TEXT_MUTED, text_color=Theme.TEXT_MUTED, hover_color=Theme.BG_DARK, command=self.clear_form)
        self.btn_clear.grid(row=4, column=2, padx=10, pady=15, sticky="e")

        self.btn_submit = ctk.CTkButton(form_frame, text="存檔", font=Theme.FONT_BODY, fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT, hover_color=Theme.NEON_CYAN, width=150, command=self.submit_form)
        self.btn_submit.grid(row=4, column=3, padx=10, pady=15, sticky="e")

        # 輸入表單角落的角色小圖（Bocchi 趴在上面）
        self.input_mascot = _safe_image_label(form_frame, "input", (200, 200))
        if self.input_mascot is not None:
            self.input_mascot.place(relx=1.0, rely=0.0, anchor="ne", x=-6, y=-2)

    def _build_list(self):
        self.list_frame = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        self.list_frame.grid(row=1, column=0, sticky="nsew")
        self.list_frame.grid_rowconfigure(1, weight=1)
        self.list_frame.grid_columnconfigure(0, weight=1)
        
        header = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        
        title = ctk.CTkLabel(header, text="歷史紀錄", font=Theme.FONT_HEADING, text_color=Theme.NEON_CYAN)
        title.pack(side="left")

        years = selectable_years(Repository.get_min_worklog_year())
        months = [str(m).zfill(2) for m in range(1, 13)]
        
        self.combo_year = ctk.CTkComboBox(header, values=years, variable=self.filter_year_var, width=80, command=self._on_year_month_change)
        self.combo_year.pack(side="left", padx=(20, 5))
        self.combo_month = ctk.CTkComboBox(header, values=months, variable=self.filter_month_var, width=60, command=self._on_year_month_change)
        self.combo_month.pack(side="left", padx=5)

        self.seg_history_status = ctk.CTkSegmentedButton(
            header, values=["全部", "已處理", "待處理", "轉交"],
            variable=self.history_status_var, font=Theme.FONT_SMALL, width=260,
            command=lambda _: self.refresh_list()
        )
        self.seg_history_status.pack(side="left", padx=(10, 0))

        self.btn_export = ctk.CTkButton(header, text="📊 匯出當月報表", font=Theme.FONT_BODY, fg_color=Theme.NEON_SELECT, text_color=Theme.TEXT_MAIN, hover_color=Theme.NEON_CYAN, width=120, command=self.export_to_excel)
        self.btn_export.pack(side="right", padx=(15, 0))

        self.btn_batch_delete = ctk.CTkButton(header, text="🗑️ 批次刪除", width=90, command=self.batch_delete)
        self.btn_batch_delete.pack(side="right", padx=5)
        
        self.btn_single_delete = ctk.CTkButton(header, text="🗑️ 單筆刪除", width=90, command=self.execute_single_delete)
        self.btn_single_delete.pack(side="right", padx=5)
        
        self.btn_edit = ctk.CTkButton(header, text="📝 編輯", width=80, command=self.execute_edit)
        self.btn_edit.pack(side="right", padx=5)
        
        self.scroll_frame = AutoHideScrollableFrame(self.list_frame, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.pager = PaginationBar(self.list_frame, page_size=30, on_change=self._on_page_change)
        self.pager.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))

    # ==========================================
    # 核心邏輯與按鈕事件
    # ==========================================
    def export_to_excel(self):
        y = self.filter_year_var.get()
        m = self.filter_month_var.get()
        logs = Repository.get_worklogs_by_month(y, m)
        if not logs:
            messagebox.showinfo("提示", f"{y}年{m}月 沒有任何紀錄可供匯出。")
            return
            
        logs_ascending = sorted(logs, key=lambda x: (x['work_date'], x['work_time'] or ""))

        filepath = filedialog.asksaveasfilename(
            title="選擇匯出檔案 (若選擇既有檔案，將自動追加或覆蓋當月分頁)",
            defaultextension=".xlsx",
            filetypes=[("Excel 活頁簿", "*.xlsx")],
            initialfile=f"工作日誌_{y}.xlsx" 
        )
        if not filepath: return 

        try:
            data_rows = []
            weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
            for idx, log in enumerate(logs_ascending, start=1):
                dt = datetime.strptime(log['work_date'], "%Y-%m-%d")
                w_time = log['work_time'][:5] if log['work_time'] else ""
                f_time = log['finish_time'][:5] if log['finish_time'] else ""
                row = [
                    idx,                                  
                    weekday_map[dt.weekday()],            
                    to_roc_date(log['work_date']),        
                    w_time,                               
                    log.get('project_name', ''),          
                    log.get('school_name', ''),           
                    log['issue_content'],                 
                    log.get('solution', ''),              
                    to_roc_date(log.get('finish_date', '')), 
                    f_time,                               
                    log.get('issue_code', '')             
                ]
                data_rows.append(row)
            sheet_name = f"{int(m)}月"
            exporter = ExcelExporter(filepath)
            exporter.append_monthly_data(sheet_name, data_rows)
            exporter.save()
            messagebox.showinfo("匯出成功", f"✅ {y}年{m}月 的資料已成功匯出！\n\n檔案位置：{filepath}\n分頁名稱：{sheet_name}")
        except Exception as e:
            messagebox.showerror("匯出失敗", f"寫入 Excel 時發生錯誤：\n{str(e)}")

    def submit_form(self):
        proj_name = self.project_var.get()
        issue = self.issue_entry.get_value()
        if proj_name == "【請設定專案資料】" or not proj_name:
            messagebox.showwarning("警告", "請先選擇或輸入專案！")
            return
        if not issue:
            messagebox.showwarning("警告", "問題內容不可為空！")
            return

        project_id = next((p['id'] for p in self.projects_data if p['name'] == proj_name), None)
        school_name = self.school_var.get()

        if project_id is None and not self._is_placeholder(proj_name):
            if messagebox.askyesno("建立專案", f"「{proj_name}」尚未建立，是否立即建立此專案？"):
                try:
                    project_id = Repository.add_project(proj_name)
                    self.load_projects_from_db()
                    self.project_var.set(proj_name)
                    self.on_project_select(proj_name)
                    self.school_var.set(school_name)
                except Exception as e:
                    messagebox.showerror("錯誤", f"建立專案失敗：\n{str(e)}")
                    return
            else:
                return

        schools = Repository.get_schools_by_project(project_id) if project_id else []
        school_id = next((s['id'] for s in schools if s['school_name'] == school_name), None)

        if school_id is None and not self._is_placeholder(school_name):
            if messagebox.askyesno("建立學校", f"「{school_name}」尚未建立，是否立即建立並加入專案「{proj_name}」？"):
                try:
                    school_id = Repository.add_school(school_name)
                    Repository.attach_school_to_project(project_id, school_id)
                    if school_name not in self.all_school_names:
                        self.all_school_names.append(school_name)
                        self.school_combo.configure(values=self.all_school_names)
                    self.school_var.set(school_name)
                except Exception as e:
                    messagebox.showerror("錯誤", f"建立學校失敗：\n{str(e)}")
                    return
            else:
                return

        now = datetime.now()
        s_dt = self.start_datetime if self.start_datetime else now

        date_str = self.date_var.get().strip()
        parsed_date = None
        if date_str:
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning("警告", "日期格式錯誤，應為 YYYY-MM-DD（例如 2026-07-10）。")
                return

        if self.editing_log_id:
            if parsed_date is not None:
                s_dt = datetime.combine(parsed_date, s_dt.time())
        else:
            if parsed_date is not None:
                s_dt = datetime.combine(parsed_date, s_dt.time())
            else:
                try:
                    sel_y = int(self.filter_year_var.get())
                    sel_m = int(self.filter_month_var.get())
                except (TypeError, ValueError):
                    sel_y, sel_m = now.year, now.month
                last_day = calendar.monthrange(sel_y, sel_m)[1]
                s_dt = s_dt.replace(year=sel_y, month=sel_m, day=min(s_dt.day, last_day))

        if self.current_status == "已處理":
            if not (self.editing_log_id and self.finish_datetime):
                self.finish_datetime = datetime.now()
        else:
            self.finish_datetime = None

        transfer_target = self.personnel_var.get() if self.current_status == "轉交" and not self._is_placeholder(self.personnel_var.get()) else None

        data = {
            "work_date": s_dt.strftime("%Y-%m-%d"),
            "work_time": s_dt.strftime("%H:%M:%S"),
            "project_id": project_id,
            "school_id": school_id,
            "contact_person": self.contact_entry.get_value(),
            "phone_ext": self.phone_entry.get_value(),
            "pii_info": self.pii_entry.get_value(),
            "issue_content": issue,
            "solution": self.solution_entry.get_value(),
            "status": self.current_status,
            "transfer_to": transfer_target,
            "finish_date": self.finish_datetime.strftime("%Y-%m-%d") if self.finish_datetime else None,
            "finish_time": self.finish_datetime.strftime("%H:%M:%S") if self.finish_datetime else None
        }

        try:
            if self.editing_log_id:
                Repository.update_worklog(self.editing_log_id, data)
            else:
                Repository.add_worklog(data)
        except Exception as e:
            messagebox.showerror("錯誤", f"資料庫存檔失敗：\n{str(e)}")
            return

        try:
            self.clear_form()
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("錯誤", f"畫面更新失敗：\n{str(e)}")

    def clear_form(self):
        self.editing_log_id = None
        self.btn_clear.configure(text="清空")
        self.date_var.set(self._default_date_for_selection())
        self.phone_entry.clear_text()
        self.contact_entry.clear_text()
        self.pii_entry.clear_text()
        self.issue_entry.clear_text()
        self.solution_entry.clear_text()
        self.start_datetime = None
        self.finish_datetime = None
        self.set_status("已處理")
        for var in self.selected_logs.values():
            var.set(False)
        self.update_action_buttons_state()

    def update_action_buttons_state(self):
        selected_ids = [log_id for log_id, var in self.selected_logs.items() if var.get()]
        count = len(selected_ids)
        disabled_fg = Theme.BUTTON_DISABLED
        disabled_text = Theme.TEXT_MUTED
        if count == 1:
            self.btn_edit.configure(state="normal", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT)
            self.btn_single_delete.configure(state="normal", fg_color=Theme.NEON_PINK, text_color=Theme.TEXT_MAIN)
        else:
            self.btn_edit.configure(state="disabled", fg_color=disabled_fg, text_color=disabled_text)
            self.btn_single_delete.configure(state="disabled", fg_color=disabled_fg, text_color=disabled_text)
        if count > 0:
            self.btn_batch_delete.configure(state="normal", fg_color=Theme.NEON_PINK, text_color=Theme.TEXT_MAIN)
        else:
            self.btn_batch_delete.configure(state="disabled", fg_color=disabled_fg, text_color=disabled_text)

    def execute_edit(self):
        selected_ids = [log_id for log_id, var in self.selected_logs.items() if var.get()]
        if len(selected_ids) == 1:
            self.enter_edit_mode(self.current_logs_data[selected_ids[0]])

    def execute_single_delete(self):
        selected_ids = [log_id for log_id, var in self.selected_logs.items() if var.get()]
        if len(selected_ids) == 1:
            log_data = self.current_logs_data[selected_ids[0]]
            if messagebox.askyesno("確認刪除", f"確定要刪除這筆紀錄嗎？\n{log_data['issue_content']}"):
                Repository.delete_worklogs([log_data['id']])
                self.refresh_list()

    def batch_delete(self):
        ids_to_delete = [log_id for log_id, var in self.selected_logs.items() if var.get()]
        if messagebox.askyesno("確認批次刪除", f"確定要刪除選取的 {len(ids_to_delete)} 筆紀錄嗎？此操作不可逆！"):
            Repository.delete_worklogs(ids_to_delete)
            self.refresh_list()

    def enter_edit_mode(self, log):
        self.editing_log_id = log['id']
        self.btn_clear.configure(text="取消")
        self.date_var.set(log.get('work_date') or self._default_date_for_selection())
        self.project_var.set(log.get('project_name') or "【請設定專案資料】")
        self.on_project_select(self.project_var.get())
        self.school_var.set(log.get('school_name') or "【請設定學校】")
        self.phone_entry.set_value(log.get('phone_ext', ''))
        self.contact_entry.set_value(log.get('contact_person', ''))
        self.pii_entry.set_value(log.get('pii_info', ''))
        self.issue_entry.set_value(log.get('issue_content', ''))
        self.solution_entry.set_value(log.get('solution', ''))
        
        def parse_dt(d, t):
            if not d: return None
            try: return datetime.strptime(f"{d} {t or '00:00:00'}", "%Y-%m-%d %H:%M:%S")
            except: return None
        self.start_datetime = parse_dt(log.get('work_date'), log.get('work_time'))
        self.finish_datetime = parse_dt(log.get('finish_date'), log.get('finish_time'))
        
        self.set_status(log.get('status', '已處理'))
        if log.get('status') == '轉交':
            self.personnel_var.set(log.get('transfer_to'))
            self.personnel_combo.configure(text_color=Theme.TEXT_MAIN)

    def _default_date_for_selection(self):
        now = datetime.now()
        try:
            y = int(self.filter_year_var.get())
            m = int(self.filter_month_var.get())
        except (TypeError, ValueError):
            y, m = now.year, now.month
        day = min(now.day, calendar.monthrange(y, m)[1])
        return f"{y:04d}-{m:02d}-{day:02d}"

    def _on_year_month_change(self, _=None):
        self.date_var.set(self._default_date_for_selection())
        # 年月下拉連動時常連續觸發，合併成一次刷新避免重複重建
        if self._refresh_after_id is not None:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(120, self.refresh_list)

    def _on_page_change(self):
        self.refresh_list()

    def _refresh_year_options(self):
        years = selectable_years(Repository.get_min_worklog_year())
        self.top_combo_year.configure(values=years)
        self.combo_year.configure(values=years)

    def reset_to_now(self):
        now = datetime.now()
        target = (str(now.year), str(now.month).zfill(2))
        current = (self.filter_year_var.get(), self.filter_month_var.get())
        self._refresh_year_options()
        self.filter_year_var.set(target[0])
        self.filter_month_var.set(target[1])
        self.date_var.set(str(now.date()))
        # 年月沒變且資料沒被改過 → 畫面已是現況，直接略過重建
        if current == target and self._data_version == Repository.get_data_version():
            return
        self.refresh_list()

    def refresh_list(self):
        self._render_seq += 1
        seq = self._render_seq
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.selected_logs.clear()
        self.current_logs_data.clear()
        y = self.filter_year_var.get()
        m = self.filter_month_var.get()
        status = None if self.history_status_var.get() == "全部" else self.history_status_var.get()

        # 篩選條件改變時跳回第一頁
        key = (y, m, status)
        if key != getattr(self, "_last_query_key", None):
            self.pager.set_page(1)
            self._last_query_key = key

        total = Repository.count_worklogs(y, m, status)
        self.pager.set_total(total)
        self.update_action_buttons_state()

        if not total:
            ctk.CTkLabel(self.scroll_frame, text=f"尚無 {y} 年 {m} 月 的工作日誌。", text_color=Theme.TEXT_MUTED).pack(pady=20)
            self._data_version = Repository.get_data_version()
            return

        page_size = self.pager.get_page_size()
        offset = (self.pager.get_page() - 1) * page_size
        logs = Repository.get_worklogs_page(y, m, status, page_size, offset)
        self._data_version = Repository.get_data_version()
        batch_render(
            self.scroll_frame, logs, self._build_log_card,
            is_stale=lambda: self._render_seq != seq,
        )

    def _build_log_card(self, log):
        self.current_logs_data[log['id']] = log
        card = ctk.CTkFrame(self.scroll_frame, fg_color=Theme.BG_DARK, corner_radius=6)
        card.pack(fill="x", pady=4, padx=5)

        var = ctk.BooleanVar(value=False)
        self.selected_logs[log['id']] = var

        # === 第一排：左側(勾選/時間/專案/學校) 與 右側(問題/電話/聯絡人/狀態) ===
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(10, 5))

        chk = ctk.CTkCheckBox(top_row, text="", variable=var, width=24, checkbox_width=18, checkbox_height=18, command=self.update_action_buttons_state)
        chk.pack(side="left", padx=(0, 10))

        try:
            d_obj = datetime.strptime(log.get('work_date') or "", "%Y-%m-%d")
        except (ValueError, TypeError):
            d_obj = None
        t_str = (log.get('work_time') or "")[:5]
        if d_obj:
            time_str = f"{d_obj.month}/{d_obj.day} {t_str}"
        else:
            time_str = f"{log.get('work_date') or ''} {t_str}".strip()
        status = log.get('status') or '待處理'
        color = Theme.NEON_GREEN if status == "已處理" else (Theme.STATUS_PENDING if status == "待處理" else Theme.STATUS_TRANSFER)

        # 左半部固定寬度
        ctk.CTkLabel(top_row, text=time_str, text_color=Theme.TEXT_MUTED, width=75, anchor="w").pack(side="left")
        ctk.CTkLabel(top_row, text=f"[{log.get('project_name', '未知')}]", text_color=Theme.NEON_CYAN, width=120, anchor="w").pack(side="left", padx=(0, 5))
        ctk.CTkLabel(top_row, text=log.get('school_name', ''), text_color=Theme.TEXT_MAIN, width=100, anchor="w").pack(side="left", padx=(0, 10))

        # 右側資訊 (由右至左 pack，確保靠右對齊)
        ctk.CTkLabel(top_row, text=status, text_color=color, width=55, anchor="e").pack(side="right", padx=(5, 0))
        if log.get('contact_person'):
            ctk.CTkLabel(top_row, text=f"👤 {log['contact_person']}", text_color=Theme.TEXT_MUTED, anchor="e").pack(side="right", padx=5)
        if log.get('phone_ext'):
            ctk.CTkLabel(top_row, text=f"☎ {log['phone_ext']}", text_color=Theme.TEXT_MUTED, anchor="e").pack(side="right", padx=5)

        # 問題內容 (填滿中間剩餘空間)
        ctk.CTkLabel(top_row, text=(log.get('issue_content') or ''), text_color=Theme.TEXT_MAIN, anchor="w", justify="left").pack(side="left", fill="x", expand=True)

        # === 第二排：處理情形、個資 (對齊上方問題內容的位置) ===
        details = []
        if log.get('solution'): details.append(f"▸ 處理情形: {log['solution']}")
        if log.get('pii_info'): details.append(f"🔒 個資: {log['pii_info']}")

        if details or log.get('transfer_to'):
            bottom_row = ctk.CTkFrame(card, fg_color="transparent")
            bottom_row.pack(fill="x", padx=10, pady=(0, 5))
            if details:
                # 左側偏移量：34(勾選) + 75(時間) + 125(專案) + 110(學校) = 344px
                ctk.CTkLabel(
                    bottom_row, text="   |   ".join(details),
                    text_color=Theme.TEXT_MUTED, anchor="w", justify="left"
                ).pack(side="left", fill="x", expand=True, padx=(344, 0))
            if log.get('transfer_to'):
                ctk.CTkLabel(
                    bottom_row, text=f"⮑ 轉交人員: {log['transfer_to']}",
                    text_color=Theme.STATUS_TRANSFER, anchor="e"
                ).pack(side="right", padx=(10, 5))
        else:
            top_row.pack_configure(pady=(10, 10)) # 如果二三排都沒有，增加底部留白

        def make_clickable(widget, v=var):
            widget.bind("<Button-1>", lambda e: [v.set(not v.get()), self.update_action_buttons_state()])
            for child in widget.winfo_children():
                if not isinstance(child, ctk.CTkCheckBox):
                    make_clickable(child, v)
        make_clickable(card)

    def open_browser_and_start(self):
        # 開啟目前選中專案設定的網址；未選專案或沒設網址時提示
        proj_name = self.project_var.get()
        target_url = None
        if self.projects_data:
            proj = next((p for p in self.projects_data if p['name'] == proj_name), None)
            if proj:
                target_url = (proj.get('url') or '').strip()

        if self._is_placeholder(proj_name):
            messagebox.showwarning("未選擇專案", "請先在專案欄位選擇要導向的專案。")
        elif not target_url:
            messagebox.showwarning("未設定網址", f"專案「{proj_name}」尚未設定網址。\n請到「系統設定 → 專案管理」為它填上專案網址。")
        else:
            if not target_url.startswith(("http://", "https://")):
                target_url = "https://" + target_url
            webbrowser.open(target_url)

        # 記錄開始/完成時間
        self.start_datetime = datetime.now()
        if self.current_status == "已處理":
            self.finish_datetime = datetime.now()

    def set_status(self, new_status):
        self.current_status = new_status
        if new_status == "轉交":
            self.finish_datetime = None  
            self.personnel_combo.configure(state="normal")
            if self._is_placeholder(self.personnel_var.get()):
                self.personnel_var.set("【請選擇人員】")
                self.personnel_combo.configure(text_color=Theme.TEXT_MUTED)
        else:
            if new_status == "已處理":
                if self.start_datetime:
                    self.finish_datetime = datetime.now()
            else:
                self.finish_datetime = None
            self.personnel_combo.configure(state="disabled", text_color=Theme.TEXT_MUTED)
            self.personnel_var.set("【無須轉交】")
            
        self.update_status_buttons_ui()

    def update_status_buttons_ui(self):
        inactive_style = {"fg_color": "transparent", "text_color": Theme.TEXT_MUTED, "border_width": 1, "border_color": Theme.TEXT_MUTED}
        self.btn_status_done.configure(**inactive_style)
        self.btn_status_pending.configure(**inactive_style)
        self.btn_status_transfer.configure(**inactive_style)
        if self.current_status == "已處理":
            self.btn_status_done.configure(fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT, border_width=0)
        elif self.current_status == "待處理":
            self.btn_status_pending.configure(fg_color=Theme.STATUS_PENDING, text_color=Theme.TEXT_MAIN, border_width=0)
        elif self.current_status == "轉交":
            self.btn_status_transfer.configure(fg_color=Theme.STATUS_TRANSFER, text_color=Theme.TEXT_MAIN, border_width=0)

    @staticmethod
    def _is_placeholder(value):
        v = value.strip()
        if not v: return True
        return v.startswith("【") or v in ("【無符合結果】", "【無學校資料】", "【無須轉交】", "【選擇人員】", "【選擇專案】")

    def _on_personnel_selected(self, value):
        if not self._is_placeholder(value):
            self.personnel_combo.configure(text_color=Theme.TEXT_MAIN)

    def load_projects_from_db(self):
        self.projects_data = Repository.get_all_projects() 
        if self.projects_data:
            self.all_project_names = [p['name'] for p in self.projects_data]
            self.project_combo.configure(values=self.all_project_names)
            self.project_var.set("【請選擇專案】") 
            self.on_project_select(self.all_project_names[0])
        else:
            self.all_project_names = []
            self.project_var.set("【請設定專案資料】")
            
        contacts = Repository.get_all_contacts()
        if contacts:
            self.all_personnel_names = [c['name'] for c in contacts]
        else:
            self.all_personnel_names = ["【請設定轉交人員】"]
            
        self.personnel_combo.configure(values=self.all_personnel_names)

    def on_project_select(self, selected_project_name):
        selected_project_id = next((p['id'] for p in self.projects_data if p['name'] == selected_project_name), None)
        if selected_project_id:
            schools = Repository.get_schools_by_project(selected_project_id)
            if schools:
                self.all_school_names = [s['school_name'] for s in schools]
                self.school_combo.configure(values=self.all_school_names)
                self.school_var.set("【請選擇學校】")
            else:
                self.all_school_names = []
                self.school_combo.configure(values=["【無學校資料】"])
                self.school_var.set("【無學校資料】")