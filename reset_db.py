# 檔案：reset_db.py
import os
from src.db.connection import init_db
from src.db.repository import Repository

def reset_and_seed():
    db_file = "worklog.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print("🗑️ 舊資料庫已清除。")
        
    # 1. 重新建立資料表
    init_db()
    
    # 2. 注入測試專案
    p1_id = Repository.add_project("教育局校務系統", "https://edu.example.com")
    p2_id = Repository.add_project("圖書館管理系統", "https://lib.example.com")
    
    # 3. 注入測試學校（全庫唯一）+ 關聯到專案
    s1_id = Repository.add_school("建國中學", "1001")
    s2_id = Repository.add_school("北一女中", "1002")
    s3_id = Repository.add_school("大安高工", "1003")
    s4_id = Repository.add_school("師大附中", "1004")
    Repository.attach_school_to_project(p1_id, s1_id)
    Repository.attach_school_to_project(p1_id, s2_id)
    Repository.attach_school_to_project(p2_id, s3_id)
    Repository.attach_school_to_project(p2_id, s4_id)
    
    print("✅ 基礎資料 (專案與學校) 注入完成！")

if __name__ == "__main__":
    reset_and_seed()
