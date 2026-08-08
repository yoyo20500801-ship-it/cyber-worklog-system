# 檔案：src/utils/date_helper.py
from datetime import datetime


def selectable_years(earliest_year=None):
    """回傳年份下拉選項：從最早有資料的年份到目前年份（上限永不超過今年）。

    earliest_year 為資料庫最早的 work_date 年份；無資料時只有今年。
    例：2026 年新用戶 → ["2026"]；2027/01/01 開啟且資料庫已有 2026 資料 → ["2026", "2027"]。
    """
    now_year = datetime.now().year
    start = earliest_year or now_year
    start = max(min(start, now_year), 1)
    return [str(y) for y in range(start, now_year + 1)]


def to_roc_date(date_str):
    """將 'YYYY-MM-DD' 轉為民國年 'YYY/MM/DD'（2026-07-01 → 115/07/01）。

    空值回傳 ''；無法解析時原樣回傳。
    """
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    return f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
