# 檔案：src/ui/components/batch.py
# 分批渲染工具：一次建立太多 CTk 元件會讓視窗卡頓，
# 改成每批少量元件用 after() 續建，畫面保持流暢。


def batch_render(parent, items, builder, batch=6, delay=8, is_stale=None):
    """分批把 items 交給 builder 建立元件。

    參數：
        parent   - 元件容器（需有 after() 方法）
        items    - 要渲染的資料序列
        builder  - callable(item)，負責建立並加入容器的元件
        batch    - 每批建立的數量
        delay    - 每批之間的延遲（毫秒）
        is_stale - callable() → bool；回傳 True 時立即中止後續批次
                   （例如使用者又觸發了新的刷新）
    """
    total = len(items)
    if total == 0:
        return

    def step(start):
        if is_stale is not None and is_stale():
            return
        end = min(start + batch, total)
        for item in items[start:end]:
            try:
                builder(item)
            except Exception:
                continue  # 單筆資料異常時跳過，避免整個列表或程式崩潰
        if end < total:
            parent.after(delay, lambda: step(end))

    step(0)
