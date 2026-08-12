import sqlite3
from pathlib import Path

# 定義專案根目錄與資料庫、Schema 的絕對路徑
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "worklog.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

# 資料版本號：任何寫入（INSERT/UPDATE/DELETE）成功提交後 +1，
# 供各視圖判斷「資料是否有變動」以決定是否要重新渲染。
_DATA_VERSION = 0


def bump_data_version():
    global _DATA_VERSION
    _DATA_VERSION += 1


def get_data_version():
    return _DATA_VERSION


class DBConnection:
    """SQLite 連線管理 (Context Manager)"""
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        # 建立連線
        self.conn = sqlite3.connect(self.db_path)
        
        # 1. 強制啟用 Foreign Key (SQLite 預設為關閉)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        
        # 2. 讓回傳的資料像 dict 一樣可以透過 key 存取 (如: row['name'])
        self.conn.row_factory = sqlite3.Row
        
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 發生例外錯誤時自動 Rollback
            self.conn.rollback()
        else:
            # 正常結束時自動 Commit
            self.conn.commit()
            # 本連線有任何寫入（total_changes > 0）→ 資料版本 +1
            if self.conn.total_changes:
                bump_data_version()
            
        # 關閉連線
        self.conn.close()

def _ensure_sort_order_column(conn, table: str):
    """舊版資料庫缺少 sort_order 欄位時，動態新增並回填順序"""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # 欄位已存在
    conn.execute(f"UPDATE {table} SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0")

def _migrate_schools_many_to_many(conn):
    """舊版結構 (schools.project_id) → 多對多 (project_schools) 遷移。

    步驟：
      1. 依 (school_name, school_code) 去重，保留最小 id
      2. 重映射 worklogs / contacts 的 school_id
      3. 由舊關聯回填 project_schools（各專案重新編排順序）
      4. 重建 schools 表移除 project_id / sort_order
    """
    cursor = conn.cursor()
    columns = [r["name"] for r in cursor.execute('PRAGMA table_info("schools")')]
    if "project_id" not in columns:
        return  # 已是新版結構

    print("🔧 偵測到舊版學校結構 (schools.project_id)，正在遷移為多對多…")

    # 遷移期間暫時關閉外鍵檢查（重建 schools 表需先 DROP）
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # 確保 project_schools 存在（新資料庫由 schema.sql 建立，舊資料庫在此建立）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_schools (
                project_id INTEGER NOT NULL,
                school_id INTEGER NOT NULL,
                sort_order INTEGER DEFAULT 0,
                PRIMARY KEY (project_id, school_id),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
            )
        """)

        # 1. 依 (school_name, school_code) 去重，保留最小 id
        cursor.execute("SELECT id, school_name, school_code FROM schools ORDER BY id")
        canonical = {}   # (name, code) -> 保留的 id
        id_map = {}      # 舊 id -> 保留的 id
        for rid, name, code in cursor.fetchall():
            key = (name, code or "")
            if key not in canonical:
                canonical[key] = rid
            id_map[rid] = canonical[key]

        # 2. 重映射 worklogs / contacts 的 school_id
        for table in ("worklogs", "contacts"):
            tcols = [r["name"] for r in cursor.execute(f'PRAGMA table_info("{table}")')]
            if "school_id" not in tcols:
                continue
            cursor.execute(f"SELECT id, school_id FROM {table} WHERE school_id IS NOT NULL")
            for rid, sid in cursor.fetchall():
                new_sid = id_map.get(sid)
                if new_sid is not None and new_sid != sid:
                    cursor.execute(
                        f"UPDATE {table} SET school_id = ? WHERE id = ?", (new_sid, rid)
                    )

        # 3. 由舊關聯回填 project_schools（各專案重新編排順序）
        cursor.execute(
            "SELECT DISTINCT project_id FROM schools WHERE project_id IS NOT NULL ORDER BY project_id"
        )
        for (pid,) in cursor.fetchall():
            cursor.execute(
                "SELECT id FROM schools WHERE project_id = ? ORDER BY sort_order, id", (pid,)
            )
            seen = set()
            order = 0
            for (sid,) in cursor.fetchall():
                cid = id_map.get(sid, sid)
                if cid in seen:
                    continue
                seen.add(cid)
                order += 1
                cursor.execute(
                    "INSERT OR IGNORE INTO project_schools (project_id, school_id, sort_order) "
                    "VALUES (?, ?, ?)",
                    (pid, cid, order),
                )

        # 4. 重建 schools 表（移除 project_id / sort_order）
        cursor.execute("""
            CREATE TABLE schools_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_name VARCHAR(100) NOT NULL,
                school_code VARCHAR(20)
            )
        """)
        kept_ids = set(canonical.values())
        cursor.execute("SELECT id, school_name, school_code FROM schools ORDER BY id")
        cursor.executemany(
            "INSERT INTO schools_new (id, school_name, school_code) VALUES (?, ?, ?)",
            [(rid, name, code) for rid, name, code in cursor.fetchall() if rid in kept_ids],
        )
        cursor.execute("DROP TABLE schools")
        cursor.execute("ALTER TABLE schools_new RENAME TO schools")
        cursor.execute(
            "UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM schools) "
            "WHERE name = 'schools'"
        )

        school_count = cursor.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
        rel_count = cursor.execute("SELECT COUNT(*) FROM project_schools").fetchone()[0]
        print(f"✅ 學校遷移完成：{len(id_map)} 筆 → {school_count} 間學校、{rel_count} 筆關聯")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

def _ensure_indexes(conn):
    """為既有資料庫補上效能索引（CREATE INDEX IF NOT EXISTS 無副作用）。"""
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_emails_thread_key ON emails(thread_key)",
        "CREATE INDEX IF NOT EXISTS idx_emails_replied ON emails(replied)",
        "CREATE INDEX IF NOT EXISTS idx_emails_worklog_id ON emails(worklog_id)",
        "CREATE INDEX IF NOT EXISTS idx_worklogs_work_date ON worklogs(work_date)",
        "CREATE INDEX IF NOT EXISTS idx_worklogs_status ON worklogs(status)",
        "CREATE INDEX IF NOT EXISTS idx_worklogs_project_id ON worklogs(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_worklogs_school_id ON worklogs(school_id)",
        "CREATE INDEX IF NOT EXISTS idx_worklogs_created_at ON worklogs(created_at)",
    ]
    for sql in statements:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 資料表尚未建立時忽略

def init_db():
    """初始化資料庫：執行 schema.sql 建立資料表，並處理舊版資料庫遷移"""
    with DBConnection() as conn:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema_script = f.read()
            conn.executescript(schema_script)
        # 舊版資料庫：多對多遷移（schools 不再有 sort_order，排除之）
        _migrate_schools_many_to_many(conn)
        # 相容舊版資料庫：補上 sort_order 欄位
        for table in ("projects", "contacts"):
            _ensure_sort_order_column(conn, table)
        # 補上效能索引（相容舊版資料庫）
        _ensure_indexes(conn)
    print("✅ 資料庫初始化完成！")