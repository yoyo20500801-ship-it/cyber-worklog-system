-- 1. 專案主表
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE,
    url VARCHAR(255),
    sort_order INTEGER DEFAULT 0
);

-- 2. 學校表 (全庫唯一，透過 project_schools 與專案多對多關聯)
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name VARCHAR(100) NOT NULL,
    school_code VARCHAR(20)
);

-- 2b. 專案 ↔ 學校關聯表 (多對多)
CREATE TABLE IF NOT EXISTS project_schools (
    project_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL,
    sort_order INTEGER DEFAULT 0,
    PRIMARY KEY (project_id, school_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

-- 3. 人員表 (與專案、學校關聯)
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    school_id INTEGER,
    name VARCHAR(50) NOT NULL,
    phone_ext VARCHAR(50),
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (school_id) REFERENCES schools(id)
);

-- 4. 工作日誌主表
CREATE TABLE IF NOT EXISTS worklogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_date DATE NOT NULL,
    work_time TIME,
    project_id INTEGER,
    school_id INTEGER,
    contact_person VARCHAR(100),
    phone_ext VARCHAR(50),              -- 新增：電話分機
    pii_info VARCHAR(255),              -- 新增：身分證/個資 (不匯出)
    issue_content TEXT NOT NULL,
    solution TEXT,
    status VARCHAR(20) DEFAULT '已處理', 
    transfer_to VARCHAR(50),
    finish_date DATE,
    finish_time TIME,
    issue_code VARCHAR(50),             
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (school_id) REFERENCES schools(id)
);

-- 5. 客戶來信表 (Gmail 抓取)
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_uid VARCHAR(100),               -- Gmail IMAP 郵件 UID (去重用)
    message_id VARCHAR(255),                -- Message-ID 標頭 (執行緒用)
    thread_key VARCHAR(255),                -- 執行緒根訊息 ID
    received_at TEXT,
    sender_email TEXT,
    sender_name TEXT,
    to_emails TEXT,                         -- 原始收件人 (回覆所有人用)
    cc_emails TEXT,                         -- 原始副本 (回覆所有人用)
    subject TEXT,
    body TEXT,
    is_internal_reply INTEGER DEFAULT 0,    -- 執行緒內有公司內部回覆
    replied INTEGER DEFAULT 0,              -- 已由本機使用者回覆
    replied_at TEXT,
    worklog_id INTEGER,                     -- 已轉成的工作日誌 id
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worklog_id) REFERENCES worklogs(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_message_uid ON emails(message_uid);
CREATE INDEX IF NOT EXISTS idx_emails_received_at ON emails(received_at);
CREATE INDEX IF NOT EXISTS idx_emails_thread_key ON emails(thread_key);
CREATE INDEX IF NOT EXISTS idx_emails_replied ON emails(replied);
CREATE INDEX IF NOT EXISTS idx_emails_worklog_id ON emails(worklog_id);

-- 工作日誌查詢加速索引（依年月/狀態/關聯欄位）
CREATE INDEX IF NOT EXISTS idx_worklogs_work_date ON worklogs(work_date);
CREATE INDEX IF NOT EXISTS idx_worklogs_status ON worklogs(status);
CREATE INDEX IF NOT EXISTS idx_worklogs_project_id ON worklogs(project_id);
CREATE INDEX IF NOT EXISTS idx_worklogs_school_id ON worklogs(school_id);
CREATE INDEX IF NOT EXISTS idx_worklogs_created_at ON worklogs(created_at);

-- 6. 客戶來信過濾名單 (被過濾的寄件人：同步時不再抓取，可復原)
CREATE TABLE IF NOT EXISTS email_blocklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_email TEXT NOT NULL UNIQUE,
    sender_name TEXT,
    blocked_at TEXT
);