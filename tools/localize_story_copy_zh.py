"""清理旧故事中会直接显示给用户的英文碎片。

原文、来源、内部标识保持不动；只替换叙事、角色卡和互动面板里的可见文案。
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_KEYS = {
    "orig", "url", "accession", "x_prov", "_note", "note",
    "case_id", "id", "kind", "next", "roles", "fact", "source_ref",
}

REPLACEMENTS = [
    ("Dexter Shoe Company / Berkshire Hathaway", "德克斯特鞋业与伯克希尔·哈撒韦"),
    ("Lehman Brothers Holdings Inc.", "雷曼兄弟控股公司"),
    ("Luckin Coffee Inc.", "瑞幸咖啡公司"),
    ("Nikola Corporation", "尼古拉公司"),
    ("Sunbeam Corporation", "新光公司"),
    ("Berkshire Hathaway Inc.", "伯克希尔·哈撒韦"),
    ("Berkshire FY1993", "伯克希尔 1993 财年"),
    ("Consolidated Statement of Financial Condition", "合并财务状况表"),
    ("Valukas", "瓦卢卡斯"),
    ("Vol.3", "第 3 卷"),
    ("EDGAR acc", "EDGAR 归档号"),
    ("acc.", "归档号"),
    ("Warren E. Buffett", "沃伦·巴菲特"),
    ("Harold Alfond", "哈罗德·阿尔方德"),
    ("Famous Footwear", "费默斯鞋店"),
    ("H. H. Brown", "布朗鞋业"),
    ("Lowell Shoe", "洛厄尔鞋业"),
    ("Erin M. Callan", "艾琳·卡兰"),
    ("Richard S. Fuld, Jr.", "理查德·富尔德"),
    ("Mark A. Russell", "马克·拉塞尔"),
    ("Trevor R. Milton", "特雷弗·米尔顿"),
    ("Russell A. Kersh", "拉塞尔·克什"),
    ("Albert J. Dunlap", "阿尔伯特·邓拉普"),
    ("Morgan Stanley", "摩根士丹利"),
    ("Frost & Sullivan", "弗若斯特沙利文"),
    ("Moderna", "莫德纳"),
    ("VectoIQ", "维克托智联"),
    ("China's fastest-growing coffee network", "中国增长最快的咖啡网络"),
    ("China's second largest and fastest-growing coffee network", "中国第二大、增长最快的咖啡网络"),
    ("disruptive model", "颠覆式模式"),
    ("Total solar revenue", "全部收入都来自太阳能业务"),
    ("Solar revenues $ 95 $ 482 $ (387) NM", "太阳能业务收入：9.5 万美元；上年 48.2 万美元；减少 38.7 万美元"),
    ("bill-and-hold", "售后代管"),
    ("bill and hold", "售后代管"),
    ("guaranteed sales", "保证销售"),
    ("early buy", "提前购货"),
    ("Sunbeam", "新光"),
    ("Lehman", "雷曼"),
    ("Luckin", "瑞幸"),
    ("Nikola Tre", "尼古拉 Tre"),
    ("Nikola", "尼古拉"),
    ("Dell", "戴尔"),
    ("Dexter", "德克斯特"),
    ("Dunlap", "邓拉普"),
    ("Callan", "卡兰"),
    ("Fuld", "富尔德"),
    ("Harold", "哈罗德"),
    ("Peter", "彼得"),
    ("CFO", "首席财务官"),
    ("CEO", "首席执行官"),
    ("原 首席执行官", "原首席执行官"),
    ("原 首席运营官", "原首席运营官"),
    ("原首席执行官 与", "原首席执行官与"),
    ("与 维克托智联", "与维克托智联"),
    ("老 伯克希尔", "老伯克希尔"),
    ("是 莫德纳 的", "是莫德纳的"),
    ("因为 新光 被", "因为新光被"),
    ("尼古拉 已经", "尼古拉已经"),
    ("五台 尼古拉 Tre", "五台尼古拉 Tre"),
    ("COO", "首席运营官"),
    ("App", "手机应用"),
    ("军方 PX", "军方商店"),
    ("income", "收益"),
]


def localize(value, key=""):
    if key in SKIP_KEYS or key.startswith("_"):
        return value
    if isinstance(value, str):
        for old, new in REPLACEMENTS:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [localize(item) for item in value]
    if isinstance(value, dict):
        return {k: localize(v, k) for k, v in value.items()}
    return value


def main() -> None:
    for path in sorted((ROOT / "content" / "stories").glob("*/case.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        localized = localize(data)
        path.write_text(json.dumps(localized, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"localized {path.parent.name}")


if __name__ == "__main__":
    main()
