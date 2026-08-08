# 檔案：src/core/data_sync.py
# 功能：系統設定的 JSON 匯出 / 差異比對匯入（專案、全庫學校、專案學校關聯、轉交人員）
#
# 匯出格式 (v2)：
#   {
#     "version": 2,
#     "projects": [{"name", "url", "schools": [校名, ...]}],  # 每個專案帶學校名稱
#     "schools":   [{"name", "code"}],                        # 全庫唯一的學校清單
#     "contacts":  [{"name", "phone_ext"}],
#   }
# 讀取舊版 (v1) 檔案時會自動轉換成 v2 格式。
import json
from datetime import datetime
from src.db.repository import Repository

EXPORT_VERSION = 2


# ==========================================
# 匯出
# ==========================================
def export_data() -> dict:
    """收集目前資料庫中的專案、全庫學校、專案學校關聯、轉交人員，回傳可序列化的字典"""
    projects = Repository.get_all_projects()

    data = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "projects": [],
        "schools": [
            {"name": s["school_name"], "code": s["school_code"] or ""}
            for s in Repository.get_all_schools()
        ],
        "contacts": [
            {"name": c["name"], "phone_ext": c["phone_ext"] or ""}
            for c in Repository.get_all_contacts()
        ],
    }

    for p in projects:
        data["projects"].append({
            "name": p["name"],
            "url": p["url"] or "",
            "schools": [s["school_name"] for s in Repository.get_schools_by_project(p["id"])],
        })
    return data


def save_export(filepath: str) -> dict:
    """匯出至 JSON 檔案，回傳資料內容"""
    data = export_data()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


# ==========================================
# 匯入 / 相容轉換
# ==========================================
def _normalize_import_data(data: dict) -> dict:
    """將匯入資料正規化為 v2 格式（相容舊版 v1）"""
    projects = data.get("projects") or []
    schools = data.get("schools") or []
    contacts = data.get("contacts") or []
    version = data.get("version", 1)

    if version == 1:
        # 舊版：schools 為每專案一列的 [{project, name, code}]
        # 轉為「全庫唯一學校清單 + 每專案帶 schools 名稱」
        by_key = {}
        project_school_names = {}
        for s in schools:
            pname = (s.get("project") or "").strip()
            sname = (s.get("name") or "").strip()
            scode = (s.get("code") or "").strip()
            if not sname:
                continue
            by_key.setdefault((sname, scode), {"name": sname, "code": scode})
            if pname:
                project_school_names.setdefault(pname, [])
                if sname not in project_school_names[pname]:
                    project_school_names[pname].append(sname)

        new_projects = []
        for p in projects:
            pname = (p.get("name") or "").strip()
            if not pname:
                continue
            new_projects.append({
                "name": pname,
                "url": p.get("url") or "",
                "schools": project_school_names.get(pname, []),
            })
        projects = new_projects
        schools = [{"name": v["name"], "code": v["code"]} for v in by_key.values()]

    return {
        "version": 2,
        "exported_at": data.get("exported_at", ""),
        "projects": projects,
        "schools": schools,
        "contacts": contacts,
    }


def load_import(filepath: str) -> dict:
    """讀取匯入的 JSON 檔案（自動轉換為 v2 格式）"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("檔案格式錯誤：根節點必須是物件。")
    return _normalize_import_data(data)


# ==========================================
# 差異比對
# ==========================================
def compute_diff(data: dict) -> dict:
    """與目前資料庫比對，分類出新增 / 衝突 / 相同三種項目"""
    data = _normalize_import_data(data)
    existing_projects = {p["name"]: p for p in Repository.get_all_projects()}
    existing_schools = {}
    for s in Repository.get_all_schools():
        existing_schools.setdefault((s["school_name"], s["school_code"] or ""), s)
    existing_contacts = {c["name"]: c for c in Repository.get_all_contacts()}

    result = {
        "projects": {"new": [], "conflict": [], "same": []},
        "schools": {"new": [], "conflict": [], "same": []},
        "project_schools": {"new": [], "conflict": [], "same": []},
        "contacts": {"new": [], "conflict": [], "same": []},
    }

    # 全庫學校（依 名稱+代碼 比對）
    for isc in data.get("schools", []):
        sname = (isc.get("name") or "").strip()
        if not sname:
            continue
        scode = (isc.get("code") or "").strip()
        es = existing_schools.get((sname, scode))
        if es is None:
            result["schools"]["new"].append({"name": sname, "code": scode})
        elif (es.get("school_code") or "") != scode:
            result["schools"]["conflict"].append({
                "imported": {"name": sname, "code": scode},
                "existing": {"name": sname, "code": es.get("school_code") or ""},
            })
        else:
            result["schools"]["same"].append({"name": sname, "code": scode})

    # 專案 + 專案學校關聯
    for ip in data.get("projects", []):
        pname = (ip.get("name") or "").strip()
        if not pname:
            continue
        ep = existing_projects.get(pname)
        if ep is None:
            result["projects"]["new"].append({"name": pname, "url": ip.get("url") or ""})
        elif (ep.get("url") or "") != (ip.get("url") or ""):
            result["projects"]["conflict"].append({
                "imported": {"name": pname, "url": ip.get("url") or ""},
                "existing": {"name": pname, "url": ep.get("url") or ""},
            })
        else:
            result["projects"]["same"].append({"name": pname, "url": ip.get("url") or ""})

        # 專案學校關聯：僅列出「專案已存在或將建立、但尚未關聯」的學校（不處理解除）
        current_names = set()
        if ep is not None:
            current_names = {s["school_name"] for s in Repository.get_schools_by_project(ep["id"])}
        for n in ip.get("schools") or []:
            n = (n or "").strip()
            if not n or n in current_names:
                if n:
                    result["project_schools"]["same"].append({"project": pname, "name": n})
                continue
            match = next(
                (isc for isc in data.get("schools", []) if (isc.get("name") or "").strip() == n),
                None,
            )
            if match is None:
                continue
            result["project_schools"]["new"].append({
                "project": pname,
                "name": n,
                "code": (match.get("code") or "").strip(),
            })

    # 轉交人員
    for ic in data.get("contacts", []):
        cname = (ic.get("name") or "").strip()
        if not cname:
            continue
        ec = existing_contacts.get(cname)
        if ec is None:
            result["contacts"]["new"].append({"name": cname, "phone_ext": ic.get("phone_ext") or ""})
        elif (ec.get("phone_ext") or "") != (ic.get("phone_ext") or ""):
            result["contacts"]["conflict"].append({
                "imported": {"name": cname, "phone_ext": ic.get("phone_ext") or ""},
                "existing": {"name": cname, "phone_ext": ec.get("phone_ext") or ""},
            })
        else:
            result["contacts"]["same"].append({"name": cname, "phone_ext": ic.get("phone_ext") or ""})

    return result


# ==========================================
# 執行匯入（data 為使用者勾選後的項目）
# ==========================================
def apply_import(data: dict, include_new: bool, overwrite_conflicts: bool) -> tuple:
    """執行匯入，回傳 (新增筆數, 更新筆數)"""
    added = 0
    updated = 0

    projects = Repository.get_all_projects()
    pid_by_name = {p["name"]: p["id"] for p in projects}
    schools_by_key = {}
    for s in Repository.get_all_schools():
        schools_by_key.setdefault((s["school_name"], s["school_code"] or ""), s["id"])

    # 1. 專案（先匯入，讓學校關聯可掛上新的專案）
    for ip in data.get("projects", []):
        name = (ip.get("name") or "").strip()
        if not name:
            continue
        if name in pid_by_name:
            if overwrite_conflicts:
                Repository.update_project(pid_by_name[name], name, ip.get("url") or None)
                updated += 1
        elif include_new:
            pid_by_name[name] = Repository.add_project(name, ip.get("url") or None)
            added += 1

    # 2. 全庫學校（依 名稱+代碼 去重）
    for isc in data.get("schools", []):
        sname = (isc.get("name") or "").strip()
        if not sname:
            continue
        scode = (isc.get("code") or "").strip() or None
        key = (sname, scode or "")
        if key in schools_by_key:
            if overwrite_conflicts:
                Repository.update_school(schools_by_key[key], sname, scode)
                updated += 1
        elif include_new:
            schools_by_key[key] = Repository.add_school(sname, scode)
            added += 1

    # 3. 專案學校關聯（將勾選的新關聯加入專案）
    if include_new:
        for rel in data.get("project_schools", []):
            pid = pid_by_name.get(rel.get("project") or "")
            sid = schools_by_key.get(
                ((rel.get("name") or "").strip(), (rel.get("code") or "").strip() or "")
            )
            if pid and sid:
                Repository.attach_school_to_project(pid, sid)
                added += 1

    # 4. 轉交人員
    contacts = Repository.get_all_contacts()
    cid_by_name = {c["name"]: c["id"] for c in contacts}
    for ic in data.get("contacts", []):
        cname = (ic.get("name") or "").strip()
        if not cname:
            continue
        if cname in cid_by_name:
            if overwrite_conflicts:
                Repository.update_contact(cid_by_name[cname], cname, ic.get("phone_ext") or None)
                updated += 1
        elif include_new:
            cid_by_name[cname] = Repository.add_contact(cname, ic.get("phone_ext") or None)
            added += 1

    return added, updated
