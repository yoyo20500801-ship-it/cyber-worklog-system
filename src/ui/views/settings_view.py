# 檔案：src/ui/views/settings_view.py
import customtkinter as ctk
import threading
from datetime import datetime
from tkinter import messagebox
from src.ui.theme import Theme
from src.core import updater
from src.db.repository import Repository

class SettingsView(ctk.CTkFrame):
    def __init__(self, master, on_data_changed_callback=None):
        super().__init__(master, fg_color="transparent")
        self.on_data_changed_callback = on_data_changed_callback

        self.PAGE_SIZE = 20
        self.proj_page = 1
        self.sch_page = 1
        self.contact_page = 1

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 建立 TabView (頁籤)
        self.tabview = ctk.CTkTabview(self, fg_color=Theme.BG_CARD, segmented_button_selected_color=Theme.NEON_SELECT)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_projects = self.tabview.add("專案管理")
        self.tab_schools = self.tabview.add("學校管理")
        self.tab_contacts = self.tabview.add("人員管理")
        self.tab_sync = self.tabview.add("匯入/匯出")

        self._build_projects_tab()
        self._build_schools_tab()
        self._build_contacts_tab()
        self._build_sync_tab()

    # ==========================================
    # 分頁輔助
    # ==========================================
    def _paginate(self, items, page):
        """回傳 (當頁項目, 調整後的頁碼, 總頁數)"""
        total = len(items)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        page = min(max(page, 1), total_pages)
        start = (page - 1) * self.PAGE_SIZE
        return items[start:start + self.PAGE_SIZE], page, total_pages

    def _set_page(self, which, page):
        if which == "proj":
            self.proj_page = page
            self.refresh_projects_list()
        elif which == "sch":
            self.sch_page = page
            self.refresh_schools_list()
        else:
            self.contact_page = page
            self.refresh_contacts_list()

    # ==========================================
    # 1. 專案管理 Tab
    # ==========================================
    def _build_projects_tab(self):
        self.tab_projects.grid_columnconfigure(0, weight=1)
        
        # 新增表單
        form_frame = ctk.CTkFrame(self.tab_projects, fg_color=Theme.BG_DARK)
        form_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(form_frame, text="新增專案", font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN).pack(anchor="w", padx=10, pady=(10, 5))
        
        input_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(0, 10))

        self.entry_proj_name = ctk.CTkEntry(input_row, placeholder_text="專案名稱", width=220)
        self.entry_proj_name.pack(side="left", padx=(0, 10))

        self.entry_proj_url = ctk.CTkEntry(input_row, placeholder_text="專案網址 URL (https://...)", width=350)
        self.entry_proj_url.pack(side="left", padx=10)

        btn_add = ctk.CTkButton(input_row, text="新增專案", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT, command=self._add_project)
        btn_add.pack(side="left", padx=10)

        # 排序模式切換
        sort_bar = ctk.CTkFrame(self.tab_projects, fg_color="transparent")
        sort_bar.pack(fill="x", padx=15, pady=(0, 5))
        ctk.CTkLabel(sort_bar, text="排序：", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(side="left")
        self.sort_mode_projects = ctk.CTkSegmentedButton(
            sort_bar, values=["手動排序", "依名稱"], font=Theme.FONT_SMALL,
            command=lambda _: self.refresh_projects_list()
        )
        self.sort_mode_projects.set("手動排序")
        self.sort_mode_projects.pack(side="left", padx=(10, 0))

        # 清單容器
        self.scroll_proj = ctk.CTkScrollableFrame(self.tab_projects, fg_color="transparent")
        self.scroll_proj.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        self.proj_page_bar = _PaginationBar(self.tab_projects, on_change=lambda p: self._set_page("proj", p))
        self.proj_page_bar.pack(fill="x", padx=15, pady=(0, 10))
        self.refresh_projects_list()

    def _add_project(self):
        name = self.entry_proj_name.get().strip()
        url = self.entry_proj_url.get().strip()
        if not name:
            messagebox.showwarning("警告", "專案名稱不可為空！")
            return
        try:
            Repository.add_project(name, url if url else None)
            self.entry_proj_name.delete(0, "end")
            self.entry_proj_url.delete(0, "end")
            self.refresh_projects_list()
            self.refresh_schools_tab_combos()
            if self.on_data_changed_callback: self.on_data_changed_callback()
        except Exception as e:
            messagebox.showerror("錯誤", f"新增失敗 (名稱可能重複)：\n{str(e)}")

    def refresh_projects_list(self):
        for w in self.scroll_proj.winfo_children(): w.destroy()
        projects = Repository.get_all_projects()
        if self.sort_mode_projects.get() == "依名稱":
            projects = sorted(projects, key=lambda p: p['name'])
        page_items, self.proj_page, total_pages = self._paginate(projects, self.proj_page)
        self.proj_page_bar.update_state(self.proj_page, total_pages)
        for p in page_items:
            card = ctk.CTkFrame(self.scroll_proj, fg_color=Theme.BG_DARK)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text=p['name'], font=Theme.FONT_BODY, text_color=Theme.TEXT_MAIN, width=200, anchor="w").pack(side="left", padx=15, pady=8)
            ctk.CTkLabel(card, text=p['url'] or "無網址", text_color=Theme.TEXT_MUTED, anchor="w").pack(side="left", fill="x", expand=True, padx=10)
            btn_del = ctk.CTkButton(card, text="刪除", fg_color=Theme.NEON_PINK, width=60, command=lambda pid=p['id']: self._del_project(pid))
            btn_del.pack(side="right", padx=10)
            btn_edit = ctk.CTkButton(card, text="編輯", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT, width=60, command=lambda pp=p: self._edit_project(pp))
            btn_edit.pack(side="right", padx=(0, 5))
            if self.sort_mode_projects.get() == "手動排序":
                ctk.CTkButton(card, text="▼", width=32, command=lambda pid=p['id']: self._move_project(pid, 1)).pack(side="right", padx=(0, 5))
                ctk.CTkButton(card, text="▲", width=32, command=lambda pid=p['id']: self._move_project(pid, -1)).pack(side="right", padx=(0, 5))
                

    def _move_project(self, pid, direction):
        Repository.move_project(pid, direction)
        self.refresh_projects_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _edit_project(self, p):
        dlg = _SimpleEditDialog(self, "編輯專案", [("專案名稱", p['name']), ("專案網址 URL", p['url'] or "")])
        self.wait_window(dlg)
        if dlg.values is None:
            return
        name, url = dlg.values
        name = name.strip()
        if not name:
            messagebox.showwarning("警告", "專案名稱不可為空！")
            return
        try:
            Repository.update_project(p['id'], name, url.strip() or None)
        except Exception as e:
            messagebox.showerror("錯誤", f"更新失敗（名稱可能重複）：\n{str(e)}")
            return
        self.refresh_projects_list()
        self.refresh_schools_tab_combos()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _del_project(self, pid):
        if messagebox.askyesno("確認刪除", "刪除專案將一併解除底下的學校關聯（學校本身會保留），確定刪除？"):
            Repository.delete_project(pid)
            self.refresh_projects_list()
            self.refresh_schools_tab_combos()
            if self.on_data_changed_callback: self.on_data_changed_callback()

    # ==========================================
    # 2. 學校管理 Tab
    # ==========================================
    def _build_schools_tab(self):
        self._quick_add_mode = False
        self._quick_check_vars = []

        self.form_frame = ctk.CTkFrame(self.tab_schools, fg_color=Theme.BG_DARK)
        self.form_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(self.form_frame, text="新增學校", font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN).pack(anchor="w", padx=10, pady=(10, 5))

        input_row = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(0, 10))

        self.combo_sch_proj = ctk.CTkComboBox(input_row, values=["【請設定專案資料】"], width=180, command=lambda _: self.refresh_schools_list())
        self.combo_sch_proj.pack(side="left", padx=(0, 10))

        self.entry_sch_name = ctk.CTkEntry(input_row, placeholder_text="學校", width=220)
        self.entry_sch_name.pack(side="left", padx=10)

        self.entry_sch_code = ctk.CTkEntry(input_row, placeholder_text="學校代碼 (選填)", width=120)
        self.entry_sch_code.pack(side="left", padx=10)

        btn_add = ctk.CTkButton(input_row, text="新增學校", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT, command=self._add_school)
        btn_add.pack(side="left", padx=10)

        self.btn_quick_add = ctk.CTkButton(input_row, text="＋ 從現有學校加入此專案", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT, command=self._toggle_quick_add)
        self.btn_quick_add.pack(side="left", padx=(10, 0))

        # 工具列：正常模式的排序切換 / 快速加入模式的搜尋
        self.tool_bar = ctk.CTkFrame(self.tab_schools, fg_color="transparent")
        self.tool_bar.pack(fill="x", padx=15, pady=(0, 5))

        self.sort_label = ctk.CTkLabel(self.tool_bar, text="排序：", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        self.sort_label.pack(side="left", padx=(0, 10))
        self.sort_mode_schools = ctk.CTkSegmentedButton(
            self.tool_bar, values=["手動排序", "依名稱"], font=Theme.FONT_SMALL,
            command=lambda _: self.refresh_schools_list()
        )
        self.sort_mode_schools.set("手動排序")
        self.sort_mode_schools.pack(side="left", padx=(10, 0))

        self.search_label = ctk.CTkLabel(self.tool_bar, text="搜尋：", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        self.search_label.pack(side="left", padx=(10, 0))
        self.entry_sch_search = ctk.CTkEntry(self.tool_bar, placeholder_text="輸入學校名稱 / 代碼…", width=280)
        self.entry_sch_search.bind("<Return>", lambda _: self.refresh_schools_list())
        self.entry_sch_search.pack(side="left", padx=(10,0))

        self.scroll_sch = ctk.CTkScrollableFrame(self.tab_schools, fg_color="transparent")
        self.scroll_sch.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        # 快速加入模式的動作列（返回 / 加入所選）
        self.quick_action_bar = ctk.CTkFrame(self.tab_schools, fg_color="transparent")
        self.btn_quick_cancel = ctk.CTkButton(self.quick_action_bar, text="← 返回", fg_color="transparent", text_color=Theme.TEXT_MUTED, width=90, command=self._exit_quick_add)
        self.btn_quick_cancel.pack(side="left")
        self.btn_quick_confirm = ctk.CTkButton(self.quick_action_bar, text="加入所選學校 (0)", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT, width=180, command=self._confirm_quick_add)
        self.btn_quick_confirm.pack(side="right")
        self.btn_quick_confirm.configure(state="disabled")

        self.sch_page_bar = _PaginationBar(self.tab_schools, on_change=lambda p: self._set_page("sch", p))
        self.sch_page_bar.pack(fill="x", padx=15, pady=(0, 10))

        self.refresh_schools_tab_combos()

    def _get_current_project_id(self):
        pname = self.combo_sch_proj.get()
        for p in Repository.get_all_projects():
            if p['name'] == pname:
                return p['id']
        return None

    def refresh_schools_tab_combos(self):
        current = self.combo_sch_proj.get()
        projects = Repository.get_all_projects()
        if projects:
            pnames = [p['name'] for p in projects]
            self.combo_sch_proj.configure(values=pnames)
            if current in pnames:
                self.combo_sch_proj.set(current)
            else:
                self.combo_sch_proj.set(pnames[0])
        else:
            self.combo_sch_proj.configure(values=["【無專案】"])
            self.combo_sch_proj.set("【無專案】")
        self.refresh_schools_list()

    # ---------- 快速加入模式 ----------
    def _toggle_quick_add(self):
        if self._quick_add_mode:
            self._exit_quick_add()
            return
        if self._get_current_project_id() is None:
            messagebox.showwarning("警告", "請先選擇專案！")
            return
        self._quick_add_mode = True
        self.entry_sch_search.delete(0, "end")
        self._update_schools_tab_ui()
        self.refresh_schools_list()

    def _exit_quick_add(self):
        self._quick_add_mode = False
        self._update_schools_tab_ui()
        self.refresh_schools_list()

    def _update_schools_tab_ui(self):
        for w in (self.form_frame, self.tool_bar, self.scroll_sch, self.quick_action_bar, self.sch_page_bar):
            w.pack_forget()
        self.form_frame.pack(fill="x", padx=15, pady=15)
        self.tool_bar.pack(fill="x", padx=15, pady=(0, 5))
        self.scroll_sch.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        if self._quick_add_mode:
            self.btn_quick_add.configure(text="← 返回專案學校清單")
            self.sort_label.pack_forget()
            self.sort_mode_schools.pack_forget()
            self.search_label.pack(side="left", padx=(0, 5))
            self.entry_sch_search.pack(side="left")
            self.quick_action_bar.pack(fill="x", padx=15, pady=(0, 10))
        else:
            self.btn_quick_add.configure(text="＋ 從現有學校加入此專案")
            self.search_label.pack_forget()
            #self.entry_sch_search.pack_forget()
            self.sort_label.pack(side="left", padx=(0, 10))
            self.sort_mode_schools.pack(side="left", padx=(10, 0))
            self.sch_page_bar.pack(fill="x", padx=15, pady=(0, 10))
            self.search_label.pack(side="left", padx=(0, 5))
            self.entry_sch_search.pack(side="left", padx=(0,10))

    def _add_school(self):
        pid = self._get_current_project_id()
        sname = self.entry_sch_name.get().strip()
        scode = self.entry_sch_code.get().strip() or None

        if pid is None:
            messagebox.showwarning("警告", "請先選擇專案！")
            return
        if not sname:
            messagebox.showwarning("警告", "學校名稱不可為空！")
            return

        existing = Repository.find_school_by_name(sname, scode)
        if existing:
            if messagebox.askyesno("學校已存在", f"「{sname}」已存在於資料庫，是否加入目前專案？\n（不會重複新增學校）"):
                Repository.attach_school_to_project(pid, existing["id"])
            else:
                return
        else:
            sid = Repository.add_school(sname, scode)
            Repository.attach_school_to_project(pid, sid)

        self.entry_sch_name.delete(0, "end")
        self.entry_sch_code.delete(0, "end")
        self.refresh_schools_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def refresh_schools_list(self):
        for w in self.scroll_sch.winfo_children(): w.destroy()
        if self._quick_add_mode :
            self._render_quick_add_list()
        else:
            self._render_project_schools_list()

    def _render_project_schools_list(self):
        pid = self._get_current_project_id()
        if not pid:
            self.sch_page_bar.update_state(1, 1)
            return
        schools = Repository.get_schools_by_project(pid)

        if self.entry_sch_search.get():
            in_project = {s['id'] for s in Repository.get_schools_by_project(pid)}
            keyword = self.entry_sch_search.get().strip().lower()
            schools = [
                s for s in Repository.get_all_schools()
                if s['id'] not in in_project
                and (not keyword
                        or keyword in s['school_name'].lower()
                        or (s['school_code'] and keyword in s['school_code'].lower()))
            ]

        elif self.sort_mode_schools.get() == "依名稱":
            schools = sorted(schools, key=lambda s: s['school_name'])
        page_items, self.sch_page, total_pages = self._paginate(schools, self.sch_page)
        self.sch_page_bar.update_state(self.sch_page, total_pages)
        for s in page_items:
            card = ctk.CTkFrame(self.scroll_sch, fg_color=Theme.BG_DARK)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text=s['school_name'], font=Theme.FONT_BODY, text_color=Theme.TEXT_MAIN, width=220, anchor="w").pack(side="left", padx=15, pady=8)
            ctk.CTkLabel(card, text=f"代碼: {s['school_code'] or '無'}", text_color=Theme.TEXT_MUTED, anchor="w").pack(side="left", fill="x", expand=True, padx=10)
            btn_del = ctk.CTkButton(card, text="移除", fg_color=Theme.NEON_PINK, width=60, command=lambda sid=s['id']: self._detach_school(sid))
            btn_del.pack(side="right", padx=10)
            btn_edit = ctk.CTkButton(card, text="編輯", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT, width=60, command=lambda ss=s: self._edit_school(ss))
            btn_edit.pack(side="right", padx=(0, 5))
            if self.sort_mode_schools.get() == "手動排序" and not self.entry_sch_search.get():
                ctk.CTkButton(card, text="▼", width=32, command=lambda p=pid, sid=s['id']: self._move_school(p, sid, 1)).pack(side="right", padx=(0, 5))
                ctk.CTkButton(card, text="▲", width=32, command=lambda p=pid, sid=s['id']: self._move_school(p, sid, -1)).pack(side="right", padx=(0, 5))
            

    def _render_quick_add_list(self):
        pid = self._get_current_project_id()
        if not pid:
            self._update_quick_confirm_label()
            return
        in_project = {s['id'] for s in Repository.get_schools_by_project(pid)}
        keyword = self.entry_sch_search.get().strip().lower()
        results = [
            s for s in Repository.get_all_schools()
            if s['id'] not in in_project
            and (not keyword
                 or keyword in s['school_name'].lower()
                 or (s['school_code'] and keyword in s['school_code'].lower()))
        ]
        self._quick_check_vars = []
        for s in results:
            var = ctk.BooleanVar(value=False)
            self._quick_check_vars.append((s, var))
            card = ctk.CTkFrame(self.scroll_sch, fg_color=Theme.BG_DARK)
            card.pack(fill="x", pady=3)
            label = s['school_name'] + (f"（{s['school_code']}）" if s['school_code'] else "")
            ctk.CTkCheckBox(
                card, text=label, variable=var, command=self._update_quick_confirm_label,
                checkbox_width=22, checkbox_height=22, text_color=Theme.TEXT_MAIN, font=Theme.FONT_BODY
            ).pack(side="left", padx=15, pady=8)
        if not results:
            ctk.CTkLabel(
                self.scroll_sch,
                text="沒有符合的學校" if keyword else "沒有可加入的學校（全庫學校都已加入此專案）",
                text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL
            ).pack(anchor="w", padx=15, pady=10)
        self._update_quick_confirm_label()

    def _update_quick_confirm_label(self):
        count = sum(1 for _, var in self._quick_check_vars if var.get())
        self.btn_quick_confirm.configure(text=f"加入所選學校 ({count})")
        self.btn_quick_confirm.configure(state="normal" if count else "disabled")

    def _confirm_quick_add(self):
        pid = self._get_current_project_id()
        if pid is None:
            return
        selected = [s for s, var in self._quick_check_vars if var.get()]
        if not selected:
            messagebox.showwarning("警告", "請先勾選要加入的學校。")
            return
        for s in selected:
            Repository.attach_school_to_project(pid, s['id'])
        self._quick_add_mode = False
        self._update_schools_tab_ui()
        self.refresh_schools_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _move_school(self, pid, sid, direction):
        Repository.move_school(pid, sid, direction)
        self.refresh_schools_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _edit_school(self, s):
        dlg = _SimpleEditDialog(self, "編輯學校/單位", [("學校/單位名稱", s['school_name']), ("代碼", s['school_code'] or "")])
        self.wait_window(dlg)
        if dlg.values is None:
            return
        sname, scode = dlg.values
        sname = sname.strip()
        if not sname:
            messagebox.showwarning("警告", "學校名稱不可為空！")
            return
        Repository.update_school(s['id'], sname, scode.strip() or None)
        self.refresh_schools_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _detach_school(self, sid):
        pid = self._get_current_project_id()
        if pid is None:
            return
        if messagebox.askyesno("確認移除", "確定將此學校從目前專案中移除？\n（學校仍保留在資料庫，其他專案不受影響）"):
            Repository.detach_school_from_project(pid, sid)
            self.refresh_schools_list()
            if self.on_data_changed_callback: self.on_data_changed_callback()

    # ==========================================
    # 3. 人員管理 Tab
    # ==========================================
    def _build_contacts_tab(self):
        form_frame = ctk.CTkFrame(self.tab_contacts, fg_color=Theme.BG_DARK)
        form_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(form_frame, text="新增轉交人員", font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN).pack(anchor="w", padx=10, pady=(10, 5))

        input_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(0, 10))

        self.entry_c_name = ctk.CTkEntry(input_row, placeholder_text="人員姓名", width=220)
        self.entry_c_name.pack(side="left", padx=(0, 10))

        btn_add = ctk.CTkButton(input_row, text="新增人員", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT, command=self._add_contact)
        btn_add.pack(side="left", padx=10)

        # 排序模式切換
        sort_bar = ctk.CTkFrame(self.tab_contacts, fg_color="transparent")
        sort_bar.pack(fill="x", padx=15, pady=(0, 5))
        ctk.CTkLabel(sort_bar, text="排序：", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(side="left")
        self.sort_mode_contacts = ctk.CTkSegmentedButton(
            sort_bar, values=["手動排序", "依名稱"], font=Theme.FONT_SMALL,
            command=lambda _: self.refresh_contacts_list()
        )
        self.sort_mode_contacts.set("手動排序")
        self.sort_mode_contacts.pack(side="left", padx=(10, 0))

        self.scroll_contact = ctk.CTkScrollableFrame(self.tab_contacts, fg_color="transparent")
        self.scroll_contact.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        self.contact_page_bar = _PaginationBar(self.tab_contacts, on_change=lambda p: self._set_page("contact", p))
        self.contact_page_bar.pack(fill="x", padx=15, pady=(0, 10))

        self.refresh_contacts_list()

    def _add_contact(self):
        name = self.entry_c_name.get().strip()

        if not name:
            messagebox.showwarning("警告", "人員姓名不可為空！")
            return

        Repository.add_contact(name, None)
        self.entry_c_name.delete(0, "end")
        self.refresh_contacts_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def refresh_contacts_list(self):
        for w in self.scroll_contact.winfo_children(): w.destroy()
        contacts = Repository.get_all_contacts()
        if self.sort_mode_contacts.get() == "依名稱":
            contacts = sorted(contacts, key=lambda c: c['name'])
        page_items, self.contact_page, total_pages = self._paginate(contacts, self.contact_page)
        self.contact_page_bar.update_state(self.contact_page, total_pages)
        for c in page_items:
            card = ctk.CTkFrame(self.scroll_contact, fg_color=Theme.BG_DARK)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text=c['name'], font=Theme.FONT_BODY, text_color=Theme.TEXT_MAIN, width=200, anchor="w").pack(side="left", padx=15, pady=8)
            ctk.CTkButton(card, text="刪除", fg_color=Theme.NEON_PINK, width=60, command=lambda cid=c['id']: self._del_contact(cid)).pack(side="right", padx=10)
            btn_edit = ctk.CTkButton(card, text="編輯", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT, width=60, command=lambda cc=c: self._edit_contact(cc))
            btn_edit.pack(side="right", padx=(0, 5))
            if self.sort_mode_contacts.get() == "手動排序":
                ctk.CTkButton(card, text="▼", width=32, command=lambda cid=c['id']: self._move_contact(cid, 1)).pack(side="right", padx=(0, 5))
                ctk.CTkButton(card, text="▲", width=32, command=lambda cid=c['id']: self._move_contact(cid, -1)).pack(side="right", padx=(0, 5))
                

    def _move_contact(self, cid, direction):
        Repository.move_contact(cid, direction)
        self.refresh_contacts_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _edit_contact(self, c):
        dlg = _SimpleEditDialog(self, "編輯轉交人員", [("人員姓名", c['name'])])
        self.wait_window(dlg)
        if dlg.values is None:
            return
        name = dlg.values[0].strip()
        if not name:
            messagebox.showwarning("警告", "人員姓名不可為空！")
            return
        Repository.update_contact(c['id'], name, c.get('phone_ext'))
        self.refresh_contacts_list()
        if self.on_data_changed_callback: self.on_data_changed_callback()

    def _del_contact(self, cid):
        if messagebox.askyesno("確認刪除", "確定刪除此人員？"):
            Repository.delete_contact(cid)
            self.refresh_contacts_list()
            if self.on_data_changed_callback: self.on_data_changed_callback()

    # ==========================================
    # 4. 匯入/匯出 Tab
    # ==========================================
    def _build_sync_tab(self):
        info_frame = ctk.CTkFrame(self.tab_sync, fg_color=Theme.BG_DARK)
        info_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(
            info_frame, text="設定資料同步（專案 / 學校 / 轉交人員）",
            font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            info_frame,
            text="匯出：將目前設定的專案、學校與轉交人員儲存成 JSON 檔案，可分享給其他電腦。\n"
                 "匯入：選擇他人提供的 JSON 檔案，系統會先做差異比對（新增/衝突/相同），再依你的選擇套用。",
            text_color=Theme.TEXT_MUTED, anchor="w", justify="left", font=Theme.FONT_SMALL
        ).pack(anchor="w", padx=10, pady=(0, 10))

        btn_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_export_settings = ctk.CTkButton(
            btn_row, text="⬆️ 匯出設定", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT,
            width=140, command=self._export_settings
        )
        self.btn_export_settings.pack(side="left", padx=(0, 10))

        self.btn_import_settings = ctk.CTkButton(
            btn_row, text="⬇️ 匯入設定", fg_color=Theme.NEON_SELECT, text_color=Theme.TEXT_MAIN,
            width=140, command=self._import_settings
        )
        self.btn_import_settings.pack(side="left", padx=10)

        self.sync_result_label = ctk.CTkLabel(
            info_frame, text="", text_color=Theme.NEON_GREEN, anchor="w", font=Theme.FONT_SMALL
        )
        self.sync_result_label.pack(anchor="w", padx=10, pady=(0, 10))

        # --- 程式更新 ---
        update_frame = ctk.CTkFrame(self.tab_sync, fg_color=Theme.BG_DARK)
        update_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(
            update_frame, text="程式更新",
            font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            update_frame,
            text=f"目前版本：{updater.get_version()}\n"
                 "檢查 GitHub 是否有新版本；有新版本時會自動下載、關閉並重新啟動，資料不會遺失。",
            text_color=Theme.TEXT_MUTED, anchor="w", justify="left", font=Theme.FONT_SMALL
        ).pack(anchor="w", padx=10, pady=(0, 10))

        upd_btn_row = ctk.CTkFrame(update_frame, fg_color="transparent")
        upd_btn_row.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_check_update = ctk.CTkButton(
            upd_btn_row, text="🔄 檢查更新", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=140, command=self._check_update
        )
        self.btn_check_update.pack(side="left", padx=(0, 10))

        self.update_result_label = ctk.CTkLabel(
            update_frame, text="", text_color=Theme.NEON_GREEN, anchor="w", font=Theme.FONT_SMALL
        )
        self.update_result_label.pack(anchor="w", padx=10, pady=(0, 10))

    def _check_update(self):
        """手動檢查更新（背景執行緒，避免卡住介面）。"""
        self.btn_check_update.configure(state="disabled", text="🔄 檢查中…")
        self.update_result_label.configure(text="")

        def work():
            result = updater.check_for_update()
            self.after(0, lambda: self._on_update_check_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _on_update_check_done(self, result):
        self.btn_check_update.configure(state="normal", text="🔄 檢查更新")
        if result is None:
            self.update_result_label.configure(text="✅ 目前已是最新版本")
            return
        if "error" in result:
            messagebox.showwarning("檢查更新", result["error"], parent=self)
            return
        tag = result["tag"]
        if messagebox.askyesno(
            "發現新版本",
            f"發現新版本 {tag}，是否立即更新？\n\n"
            "程式會自動下載、關閉並重新啟動，\n你的資料（工作紀錄、設定、主題圖）不會遺失。",
            parent=self,
        ):
            self.update_result_label.configure(text=f"⬇️ 正在下載 {tag} …")
            self.btn_check_update.configure(state="disabled", text="🔄 更新中…")
            self._run_apply(result["zip_url"], tag)

    def _run_apply(self, zip_url, tag):
        def work():
            ok, msg = updater.apply_update(zip_url, tag)
            self.after(0, lambda: self._on_apply_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _on_apply_done(self, ok, msg):
        if not ok:
            self.btn_check_update.configure(state="normal", text="🔄 檢查更新")
            self.update_result_label.configure(text="")
            messagebox.showerror("更新失敗", msg, parent=self)
            return
        # 更新程式已啟動，關閉主視窗讓它接手覆蓋與重啟
        top = self.winfo_toplevel()
        top.after(300, top.destroy)

    def _export_settings(self):
        from tkinter import filedialog
        from src.core.data_sync import save_export

        filepath = filedialog.asksaveasfilename(
            title="匯出系統設定",
            defaultextension=".json",
            filetypes=[("JSON 檔案", "*.json")],
            initialfile=f"系統設定匯出_{datetime.now().strftime('%Y%m%d')}.json"
        )
        if not filepath:
            return
        try:
            data = save_export(filepath)
            counts = {
                "專案": len(data["projects"]),
                "學校（全庫）": len(data["schools"]),
                "學校關聯": sum(len(p.get("schools") or []) for p in data["projects"]),
                "人員": len(data["contacts"]),
            }
            self.sync_result_label.configure(text="✅ 匯出成功")
            messagebox.showinfo(
                "匯出成功",
                f"已匯出以下資料到：\n{filepath}\n\n"
                + "\n".join(f"{k}: {v} 筆" for k, v in counts.items())
            )
        except Exception as e:
            messagebox.showerror("匯出失敗", f"發生錯誤：\n{str(e)}")

    def _import_settings(self):
        from tkinter import filedialog
        from src.core.data_sync import load_import, compute_diff

        filepath = filedialog.askopenfilename(
            title="選擇要匯入的設定檔",
            filetypes=[("JSON 檔案", "*.json")]
        )
        if not filepath:
            return
        try:
            data = load_import(filepath)
        except Exception as e:
            messagebox.showerror("匯入失敗", f"讀取檔案發生錯誤：\n{str(e)}")
            return

        diff = compute_diff(data)
        total_new = sum(len(d["new"]) for d in diff.values())
        total_conflict = sum(len(d["conflict"]) for d in diff.values())

        if total_new == 0 and total_conflict == 0:
            messagebox.showinfo("差異比對", "比對結果：所有資料皆與目前設定相同，沒有需要匯入的項目。")
            return

        try:
            dialog = _ImportPreviewDialog(self, diff)
        except Exception as e:
            messagebox.showerror("匯入失敗", f"建立匯入預覽時發生錯誤：\n{str(e)}")
            return
        self.wait_window(dialog)
        if not dialog.applied:
            return

        added, updated = dialog.result
        self.sync_result_label.configure(text="✅ 匯入完成")
        messagebox.showinfo(
            "匯入完成",
            f"匯入結果：\n\n新增 {added} 筆\n更新 {updated} 筆"
        )
        self.refresh_projects_list()
        self.refresh_schools_tab_combos()
        self.refresh_contacts_list()
        if self.on_data_changed_callback:
            self.on_data_changed_callback()


# ==========================================
# 分頁列 (上一頁 / 頁碼 / 下一頁)
# ==========================================
class _PaginationBar(ctk.CTkFrame):
    def __init__(self, master, on_change, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self.page = 1
        self.total_pages = 1

        self.btn_prev = ctk.CTkButton(
            self, text="◀ 上一頁", width=80, fg_color="transparent",
            text_color=Theme.TEXT_MUTED, border_width=1, border_color=Theme.TEXT_MUTED,
            command=lambda: self._go(-1)
        )
        self.btn_prev.pack(side="left", padx=(0, 5))

        self.label = ctk.CTkLabel(self, text="第 1 / 1 頁", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        self.label.pack(side="left", padx=10)

        self.btn_next = ctk.CTkButton(
            self, text="下一頁 ▶", width=80, fg_color="transparent",
            text_color=Theme.TEXT_MUTED, border_width=1, border_color=Theme.TEXT_MUTED,
            command=lambda: self._go(1)
        )
        self.btn_next.pack(side="left", padx=(5, 0))

    def update_state(self, page, total_pages):
        self.page = page
        self.total_pages = total_pages
        self.label.configure(text=f"第 {page} / {max(total_pages, 1)} 頁")
        self.btn_prev.configure(state="disabled" if page <= 1 else "normal")
        self.btn_next.configure(state="disabled" if page >= total_pages else "normal")

    def _go(self, delta):
        new_page = self.page + delta
        if 1 <= new_page <= max(self.total_pages, 1):
            self.on_change(new_page)


# ==========================================
# 匯入預覽視窗（差異比對結果 + 勾選套用）
# ==========================================
class _ImportPreviewDialog(ctk.CTkToplevel):
    ENTITY_LABELS = {
        "projects": "專案",
        "schools": "學校（全庫）",
        "project_schools": "專案學校關聯",
        "contacts": "轉交人員",
    }

    def __init__(self, master, diff):
        super().__init__(master)
        self.title("匯入預覽 - 差異比對")
        self.geometry("680x560")
        self.resizable(False, False)
        self.applied = False
        self.result = (0, 0)

        self.diff = diff
        self.check_vars = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=Theme.BG_CARD)
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        ctk.CTkLabel(
            header,
            text="以下為差異比對結果，勾選要套用的項目後按下「開始匯入」",
            text_color=Theme.TEXT_MAIN, font=Theme.FONT_SMALL
        ).pack(anchor="w", padx=10, pady=8)

        body = ctk.CTkScrollableFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        body.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 10))
        body.grid_columnconfigure(0, weight=1)

        self._build_sections(body)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.btn_apply = ctk.CTkButton(
            btn_frame, text="開始匯入", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=130, command=self._apply
        )
        self.btn_apply.pack(side="right")
        ctk.CTkButton(
            btn_frame, text="取消", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=100, command=self.destroy
        ).pack(side="right", padx=(0, 10))

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()

    def _build_sections(self, body):
        row = 0
        for key, label in self.ENTITY_LABELS.items():
            section = self.diff[key]
            self.check_vars[key] = {}

            ctk.CTkLabel(
                body, text=f"◤ {label}",
                font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN, anchor="w"
            ).grid(row=row, column=0, sticky="ew", padx=10, pady=(12, 2)); row += 1

            if not section["new"] and not section["conflict"]:
                ctk.CTkLabel(
                    body, text=f"   無差異（相同 {len(section['same'])} 筆，略過）",
                    text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w"
                ).grid(row=row, column=0, sticky="w", padx=10, pady=1); row += 1

            for item in section["new"]:
                var = ctk.BooleanVar(value=True)
                self.check_vars[key]["new_" + str(len(self.check_vars[key]))] = (item, var)
                self._add_check_row(body, row, f"➕ 新增: {self._desc(item)}", var)
                row += 1

            for item in section["conflict"]:
                var = ctk.BooleanVar(value=False)
                self.check_vars[key]["conflict_" + str(len(self.check_vars[key]))] = (item, var)
                text = f"⚠️ 差異: {self._desc_conflict(item)}"
                self._add_check_row(body, row, text, var, conflict=True)
                row += 1

            if len(section["same"]):
                ctk.CTkLabel(
                    body, text=f"   ✔ 相同 {len(section['same'])} 筆（略過）",
                    text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w"
                ).grid(row=row, column=0, sticky="w", padx=10, pady=1); row += 1

    def _add_check_row(self, body, row, text, var, conflict=False):
        ctk.CTkCheckBox(
            body, text=text, variable=var, checkbox_width=18, checkbox_height=18,
            text_color=Theme.NEON_YELLOW if conflict else Theme.TEXT_MAIN,
            font=Theme.FONT_SMALL
        ).grid(row=row, column=0, sticky="w", padx=10, pady=2)

    @staticmethod
    def _desc(item):
        if "project" in item:  # 專案學校關聯
            return f"{item.get('name', '')} → 專案「{item.get('project', '')}」"
        if "phone_ext" in item:
            return f"{item['name']}"
        return item.get("name", "")

    @staticmethod
    def _desc_conflict(item):
        imp = item["imported"]
        old = item["existing"]
        if "url" in imp:
            return f"{imp['name']}  網址 {old.get('url') or '無'} → {imp.get('url') or '無'}"
        if "phone_ext" in imp:
            return f"{imp['name']}"
        return f"{imp['name']}  代碼 {old.get('code') or '無'} → {imp.get('code') or '無'}"

    def _apply(self):
        from src.core.data_sync import apply_import

        import_data = {"projects": [], "schools": [], "project_schools": [], "contacts": []}
        for key in self.ENTITY_LABELS:
            for item, var in self.check_vars[key].values():
                if var.get():
                    import_data[key].append(item)

        try:
            new_count, update_count = apply_import(import_data, True, True)
        except Exception as e:
            messagebox.showerror("匯入失敗", f"寫入資料庫時發生錯誤：\n{str(e)}")
            return

        self.result = (new_count, update_count)
        self.applied = True
        self.destroy()


# ==========================================
# 通用編輯視窗（欄位由呼叫端指定）
# ==========================================
class _SimpleEditDialog(ctk.CTkToplevel):
    def __init__(self, master, title, fields):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.values = None
        self.entries = []

        self.grid_columnconfigure(0, weight=1)

        body = ctk.CTkFrame(self, fg_color=Theme.BG_CARD)
        body.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        body.grid_columnconfigure(0, weight=1)

        for i, (label, initial) in enumerate(fields):
            ctk.CTkLabel(body, text=label, font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w").grid(row=i, column=0, sticky="ew", padx=10, pady=(8, 2))
            entry = ctk.CTkEntry(body, width=340, font=Theme.FONT_SMALL)
            entry.insert(0, initial)
            entry.grid(row=i, column=0, sticky="ew", padx=10, pady=(0, 6))
            self.entries.append(entry)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
        ctk.CTkButton(
            btn_frame, text="儲存", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=100, command=self._ok
        ).pack(side="right")
        ctk.CTkButton(
            btn_frame, text="取消", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=80, command=self.destroy
        ).pack(side="right", padx=(0, 10))

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()

    def _ok(self):
        self.values = [e.get() for e in self.entries]
        self.destroy()