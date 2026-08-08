# 檔案：src/db/repository.py
from src.db.connection import DBConnection

class Repository:
    # ===============================
    # 專案 (Projects) 操作
    # ===============================
    @staticmethod
    def add_project(name: str, url: str = None) -> int:
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM projects")
            next_order = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO projects (name, url, sort_order) VALUES (?, ?, ?)",
                (name, url, next_order)
            )
            return cursor.lastrowid

    @staticmethod
    def get_all_projects() -> list:
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY sort_order, id")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def delete_project(project_id: int):
        """刪除專案 (CASCADE 會自動連同關聯學校一併清除)"""
        with DBConnection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    @staticmethod
    def update_project(project_id: int, name: str, url: str):
        """更新專案名稱與網址"""
        with DBConnection() as conn:
            conn.execute(
                "UPDATE projects SET name = ?, url = ? WHERE id = ?",
                (name, url, project_id)
            )

    @staticmethod
    def move_project(project_id: int, direction: int):
        """手動排序：direction -1 上移、+1 下移"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM projects ORDER BY sort_order, id")
            ids = [r["id"] for r in cursor.fetchall()]
            if project_id not in ids:
                return
            idx = ids.index(project_id)
            target = idx + direction
            if target < 0 or target >= len(ids):
                return
            ids[idx], ids[target] = ids[target], ids[idx]
            for i, pid in enumerate(ids):
                conn.execute("UPDATE projects SET sort_order = ? WHERE id = ?", (i + 1, pid))

    # ===============================
    # 學校 (Schools) 操作
    # 全庫唯一，透過 project_schools 與專案多對多關聯
    # ===============================
    @staticmethod
    def find_school_by_name(school_name: str, school_code: str = None):
        """依 (名稱, 代碼) 找全庫唯一的學校，不存在回傳 None"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM schools WHERE school_name = ? AND COALESCE(school_code, '') = ? "
                "ORDER BY id LIMIT 1",
                (school_name, school_code or ""),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def add_school(school_name: str, school_code: str = None) -> int:
        """全域新增學校；若同 (名稱, 代碼) 已存在則回傳既有 id，不重複新增"""
        existing = Repository.find_school_by_name(school_name, school_code)
        if existing:
            return existing["id"]
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO schools (school_name, school_code) VALUES (?, ?)",
                (school_name, school_code),
            )
            return cursor.lastrowid

    @staticmethod
    def get_all_schools() -> list:
        """取得全庫所有（唯一）學校"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schools ORDER BY school_name, id")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_schools_by_project(project_id: int) -> list:
        """取得指定專案關聯的學校（介面與舊版一致，Dashboard 免改）"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.*, ps.sort_order
                FROM project_schools ps
                JOIN schools s ON s.id = ps.school_id
                WHERE ps.project_id = ?
                ORDER BY ps.sort_order, ps.school_id
                """,
                (project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def attach_school_to_project(project_id: int, school_id: int):
        """將既有學校加入專案（已存在則略過）"""
        with DBConnection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO project_schools (project_id, school_id, sort_order) "
                "SELECT ?, ?, COALESCE(MAX(sort_order), 0) + 1 FROM project_schools WHERE project_id = ?",
                (project_id, school_id, project_id),
            )

    @staticmethod
    def detach_school_from_project(project_id: int, school_id: int):
        """將學校自專案移除（學校本身仍保留在資料庫）"""
        with DBConnection() as conn:
            conn.execute(
                "DELETE FROM project_schools WHERE project_id = ? AND school_id = ?",
                (project_id, school_id),
            )

    @staticmethod
    def update_school(school_id: int, school_name: str, school_code: str):
        """全域更新學校名稱與代碼（影響所有關聯專案）"""
        with DBConnection() as conn:
            conn.execute(
                "UPDATE schools SET school_name = ?, school_code = ? WHERE id = ?",
                (school_name, school_code, school_id),
            )

    @staticmethod
    def move_school(project_id: int, school_id: int, direction: int):
        """手動排序（僅在指定專案的關聯內移動）"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT school_id FROM project_schools WHERE project_id = ? ORDER BY sort_order, school_id",
                (project_id,),
            )
            ids = [r["school_id"] for r in cursor.fetchall()]
            if school_id not in ids:
                return
            idx = ids.index(school_id)
            target = idx + direction
            if target < 0 or target >= len(ids):
                return
            ids[idx], ids[target] = ids[target], ids[idx]
            for i, sid in enumerate(ids):
                conn.execute(
                    "UPDATE project_schools SET sort_order = ? WHERE project_id = ? AND school_id = ?",
                    (i + 1, project_id, sid),
                )

    # ===============================
    # 人員 (Contacts / Personnel) 操作
    # ===============================
    @staticmethod
    def add_contact(name: str, phone_ext: str = None, project_id: int = None, school_id: int = None) -> int:
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM contacts")
            next_order = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO contacts (name, phone_ext, project_id, school_id, sort_order) VALUES (?, ?, ?, ?, ?)",
                (name, phone_ext, project_id, school_id, next_order)
            )
            return cursor.lastrowid

    @staticmethod
    def get_all_contacts() -> list:
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts ORDER BY sort_order, id")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def delete_contact(contact_id: int):
        """刪除人員"""
        with DBConnection() as conn:
            conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

    @staticmethod
    def update_contact(contact_id: int, name: str, phone_ext: str):
        """更新人員名稱與分機/電話"""
        with DBConnection() as conn:
            conn.execute(
                "UPDATE contacts SET name = ?, phone_ext = ? WHERE id = ?",
                (name, phone_ext, contact_id)
            )

    @staticmethod
    def move_contact(contact_id: int, direction: int):
        """手動排序：direction -1 上移、+1 下移"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM contacts ORDER BY sort_order, id")
            ids = [r["id"] for r in cursor.fetchall()]
            if contact_id not in ids:
                return
            idx = ids.index(contact_id)
            target = idx + direction
            if target < 0 or target >= len(ids):
                return
            ids[idx], ids[target] = ids[target], ids[idx]
            for i, cid in enumerate(ids):
                conn.execute("UPDATE contacts SET sort_order = ? WHERE id = ?", (i + 1, cid))

    # ===============================
    # 工作日誌 (Worklogs) 操作
    # ===============================
    @staticmethod
    def add_worklog(data: dict) -> int:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = tuple(data.values())
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"INSERT INTO worklogs ({columns}) VALUES ({placeholders})", values)
            return cursor.lastrowid

    @staticmethod
    def update_worklog(log_id: int, data: dict):
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = tuple(data.values()) + (log_id,)
        with DBConnection() as conn:
            conn.execute(f"UPDATE worklogs SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def delete_worklogs(log_ids: list):
        if not log_ids: return
        placeholders = ','.join(['?'] * len(log_ids))
        with DBConnection() as conn:
            conn.execute(f"DELETE FROM worklogs WHERE id IN ({placeholders})", tuple(log_ids))

    @staticmethod
    def get_min_worklog_year():
        """回傳資料庫最早的 work_date 年份；無任何紀錄時回傳 None。"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(substr(work_date, 1, 4)) FROM worklogs")
            raw = cursor.fetchone()[0]
        return int(raw) if raw else None

    @staticmethod
    def get_worklogs_by_month(year: str, month: str, status: str = None) -> list:
        like_pattern = f"{year}-{month.zfill(2)}-%"
        params = [like_pattern]
        status_clause = ""
        if status:
            status_clause = " AND w.status = ?"
            params.append(status)
        with DBConnection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT w.*, p.name AS project_name, s.school_name 
                FROM worklogs w
                LEFT JOIN projects p ON w.project_id = p.id
                LEFT JOIN schools s ON w.school_id = s.id
                WHERE w.work_date LIKE ?{status_clause}
                ORDER BY w.work_date DESC, w.work_time DESC, w.created_at DESC
            """.format(status_clause=status_clause)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_status_summary(year: str, month: str) -> dict:
        """取得指定年月的狀態統計：{總計, 已處理, 待處理, 轉交}"""
        like_pattern = f"{year}-{month.zfill(2)}-%"
        result = {"總計": 0, "已處理": 0, "待處理": 0, "轉交": 0}
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, COUNT(*) AS cnt FROM worklogs WHERE work_date LIKE ? GROUP BY status",
                (like_pattern,)
            )
            rows = cursor.fetchall()
        for r in rows:
            if r["status"] in result:
                result[r["status"]] = r["cnt"]
            else:
                result["總計"] += r["cnt"]
        result["總計"] += sum(result[k] for k in ("已處理", "待處理", "轉交"))
        return result

    @staticmethod
    def get_project_summary(year: str, month: str) -> list:
        """取得指定年月各專案案件數: [{project_name, cnt}]，依件數遞減"""
        like_pattern = f"{year}-{month.zfill(2)}-%"
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(p.name, '未知專案') AS project_name, COUNT(*) AS cnt
                FROM worklogs w
                LEFT JOIN projects p ON w.project_id = p.id
                WHERE w.work_date LIKE ?
                GROUP BY p.name
                ORDER BY cnt DESC, project_name ASC
                """,
                (like_pattern,)
            )
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_daily_summary(year: str, month: str) -> list:
        """取得指定年月每日件數: [{work_date, cnt}]，依日期遞增"""
        like_pattern = f"{year}-{month.zfill(2)}-%"
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT work_date, COUNT(*) AS cnt
                FROM worklogs
                WHERE work_date LIKE ?
                GROUP BY work_date
                ORDER BY work_date ASC
                """,
                (like_pattern,)
            )
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_transfer_logs_by_month(year: str, month: str) -> list:
        """取得指定年月的轉交紀錄（status = 轉交）"""
        like_pattern = f"{year}-{month.zfill(2)}-%"
        with DBConnection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT w.*, p.name AS project_name, s.school_name
                FROM worklogs w
                LEFT JOIN projects p ON w.project_id = p.id
                LEFT JOIN schools s ON w.school_id = s.id
                WHERE w.status = '轉交' AND w.work_date LIKE ?
                ORDER BY w.work_date DESC, w.work_time DESC, w.created_at DESC
            """
            cursor.execute(query, (like_pattern,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def set_worklog_transfer_target(log_id: int, transfer_to: str):
        """更新工作日誌的轉交對象"""
        with DBConnection() as conn:
            conn.execute(
                "UPDATE worklogs SET transfer_to = ? WHERE id = ?",
                (transfer_to, log_id)
            )

    # ===============================
    # 客戶來信 (Emails) 操作
    # ===============================
    @staticmethod
    def upsert_email(data: dict) -> int:
        """依 message_uid 新增或更新信件，回傳 email id。"""
        uid = data.get("message_uid")
        with DBConnection() as conn:
            cursor = conn.cursor()
            existing = cursor.execute(
                "SELECT id FROM emails WHERE message_uid = ?", (uid,)
            ).fetchone()
            if existing:
                sets = {k: v for k, v in data.items() if k != "message_uid"}
                if sets:
                    set_clause = ", ".join(f"{k} = ?" for k in sets)
                    values = tuple(sets.values()) + (existing["id"],)
                    cursor.execute(f"UPDATE emails SET {set_clause} WHERE id = ?", values)
                return existing["id"]
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cursor.execute(
                f"INSERT INTO emails ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )
            return cursor.lastrowid

    @staticmethod
    def mark_thread_internal_reply(thread_keys: list):
        """將指定執行緒的客戶信件標記為「同事已回覆」"""
        if not thread_keys:
            return
        placeholders = ",".join(["?"] * len(thread_keys))
        with DBConnection() as conn:
            conn.execute(
                f"UPDATE emails SET is_internal_reply = 1 WHERE thread_key IN ({placeholders})",
                tuple(thread_keys),
            )

    @staticmethod
    def mark_email_replied(email_id: int, replied_at: str):
        with DBConnection() as conn:
            conn.execute(
                "UPDATE emails SET replied = 1, replied_at = ? WHERE id = ?",
                (replied_at, email_id),
            )

    @staticmethod
    def set_email_worklog(email_id: int, worklog_id: int):
        with DBConnection() as conn:
            conn.execute(
                "UPDATE emails SET worklog_id = ? WHERE id = ?", (worklog_id, email_id)
            )

    @staticmethod
    def get_emails(search: str = None, filter_mode: str = "全部", limit: int = 500) -> list:
        """取得客戶來信清單。

        filter_mode：全部 / 待處理 / 已回覆 / 同事已回覆 / 已轉工作日誌
        """
        params = []
        where = ["1=1"]
        if search:
            kw = f"%{search}%"
            where.append(
                "(sender_name LIKE ? OR sender_email LIKE ? OR subject LIKE ? OR body LIKE ?)"
            )
            params += [kw, kw, kw, kw]
        if filter_mode == "待處理":
            where.append("replied = 0 AND worklog_id IS NULL")
        elif filter_mode == "已回覆":
            where.append("replied = 1")
        elif filter_mode == "同事已回覆":
            where.append("is_internal_reply = 1")
        elif filter_mode == "已轉工作日誌":
            where.append("worklog_id IS NOT NULL")
        where_sql = " AND ".join(where)
        with DBConnection() as conn:
            cursor = conn.cursor()
            query = f"""
                SELECT e.*, w.issue_content AS worklog_issue
                FROM emails e
                LEFT JOIN worklogs w ON w.id = e.worklog_id
                WHERE {where_sql}
                ORDER BY e.received_at DESC, e.id DESC
                LIMIT ?
            """
            cursor.execute(query, params + [limit])
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_email_by_id(email_id: int):
        with DBConnection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_email_count() -> int:
        with DBConnection() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM emails").fetchone()
            return row["c"] if row else 0

    @staticmethod
    def get_existing_email_uids() -> set:
        with DBConnection() as conn:
            rows = conn.execute("SELECT message_uid FROM emails").fetchall()
            return {r["message_uid"] for r in rows}

    # ---- 過濾名單 (blocklist) ----
    @staticmethod
    def add_email_blocklist(sender_email: str, sender_name: str = None) -> bool:
        """把寄件人加入過濾名單，回傳是否為「新增」（重複加入回傳 False）。"""
        if not sender_email:
            return False
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO email_blocklist (sender_email, sender_name, blocked_at) "
                "VALUES (?, ?, datetime('now', 'localtime'))",
                (sender_email.strip(), (sender_name or "").strip() or None),
            )
            return cursor.rowcount > 0

    @staticmethod
    def remove_email_blocklist(sender_email: str):
        """從過濾名單復原寄件人（下次同步會重新抓取）。"""
        with DBConnection() as conn:
            conn.execute("DELETE FROM email_blocklist WHERE sender_email = ?", (sender_email,))

    @staticmethod
    def get_email_blocklist() -> list:
        """取得全部過濾名單（由新到舊）。"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, sender_email, sender_name, blocked_at FROM email_blocklist ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def delete_emails_by_sender(sender_email: str) -> int:
        """清除指定寄件人的所有來信，回傳刪除筆數。"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM emails WHERE sender_email = ?", (sender_email,))
            return cursor.rowcount

    # ===============================
    # 資料庫搜尋 (SQL) 操作
    # ===============================
    @staticmethod
    def get_db_schema() -> list:
        """取得所有資料表及其欄位名稱（含 SQLite 內部資料表）: [{table, columns: [..]}]"""
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' ORDER BY name"
            )
            tables = [row["name"] for row in cursor.fetchall()]
            result = []
            for table in tables:
                cursor.execute(f'PRAGMA table_info("{table}")')
                columns = [row["name"] for row in cursor.fetchall()]
                result.append({"table": table, "columns": columns})
            return result

    @staticmethod
    def execute_sql(sql: str) -> dict:
        """執行使用者輸入的 SQL。

        回傳 dict：
            SELECT 類 -> {is_select: True, columns: [...], rows: [[..]], rowcount: n}
            其他類   -> {is_select: False, columns: None, rows: [], rowcount: n}
        """
        with DBConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            if cursor.description is not None:
                columns = [desc[0] for desc in cursor.description]
                rows = [list(row) for row in cursor.fetchall()]
                return {"is_select": True, "columns": columns, "rows": rows, "rowcount": len(rows)}
            return {"is_select": False, "columns": None, "rows": [], "rowcount": cursor.rowcount}