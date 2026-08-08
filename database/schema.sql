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