"""ETF 名称解析(纯函数): 从行情接口返回的基金简称推导指数名标签。

行情接口只给基金简称(如「嘉实上证科创板芯片ETF」), 而本系统的展示/选择
需要的是指数名(如「科创芯片」)。动态添加标的时用启发式推导一个初始标签,
由用户在前端表单里修正 —— 推导结果只作默认值, 不做严格保证。
"""

from __future__ import annotations

# 常见基金公司前缀(仅用于展示标签剥离, 缺失不报错)
_FUND_HOUSES = (
    "华夏",
    "易方达",
    "嘉实",
    "南方",
    "华泰柏瑞",
    "国泰",
    "招商",
    "银华",
    "大成",
    "华宝",
    "鹏华",
    "广发",
    "富国",
    "汇添富",
    "天弘",
    "博时",
    "工银瑞信",
    "建信",
    "中银",
    "平安",
    "兴业",
    "浦银安盛",
    "景顺长城",
    "华安",
    "海富通",
    "中欧",
    "国联安",
    "万家",
    "永赢",
    "华泰证券",
)

# 尾部产品形态后缀(先匹配更长的, 避免 ETF 先于 ETF联接 被剥掉)
_SUFFIXES = ("ETF联接", "ETF", "联接基金", "联接", "指数基金", "指数", "LOF", "基金")


def derive_idx_name(name: str) -> str:
    """从基金简称推导指数名标签; 推不出有效结果时回退原名。

    两种行情命名格式都要处理:
      - 东财式(公司前缀): 「嘉实上证科创板芯片ETF」→「上证科创板芯片」
      - 腾讯式(公司后缀): 「有色金属ETF南方」→「有色金属」、「创业板ETF易方达」→「创业板」
    """
    s = (name or "").strip()
    if not s:
        return s
    for house in _FUND_HOUSES:
        if s.startswith(house) and len(s) > len(house):
            s = s[len(house) :]
            break
    changed = True
    while changed:
        changed = False
        for house in _FUND_HOUSES:
            if s.endswith(house) and len(s) > len(house):
                s = s[: -len(house)]
                changed = True
                break
        if changed:
            continue
        for suffix in _SUFFIXES:
            if s.endswith(suffix) and len(s) > len(suffix):
                s = s[: -len(suffix)]
                changed = True
                break
        if changed:
            continue
        # 份额类别后缀(如 "ETF联接A" 剥掉 A/C/E)
        if len(s) > 1 and s[-1].isascii() and s[-1].isalpha():
            s = s[:-1]
            changed = True
    s = s.strip()
    return s or name
