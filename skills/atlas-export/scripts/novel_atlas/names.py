"""名称归一化、泛称过滤和粗粒度相似度。"""

import re

# 这些别名指向的是"身份"而不是"某个人"，参与归并会误伤
GENERIC_ALIASES = {
    "师兄", "师姐", "师弟", "师妹", "师父", "师傅", "师叔", "师伯",
    "长老", "前辈", "道友", "老祖", "大人", "公子", "姑娘", "小姐",
    "掌门", "宗主", "陛下", "殿下", "阁下", "兄台", "老大",
}

# 序数称谓（二夫人、三娘、五小姐……）指向位份而非具体人，不能拿来归并；
# 颜色+衣着（蓝衣人、白衣少女、青衫老者……）只是当场的视觉描述，跨批次极易撞车
GENERIC_ALIAS_RE = re.compile(
    r"^[一二三四五六七八九十]+(夫人|太太|奶奶|娘|姨|小姐|公子|少爷|爷)$"
    r"|^(蓝|白|青|灰|黑|黄|绿|红)衣(人|青年|老者|少女|女子|汉子)$"
)

# 姓氏+氏（李氏、王氏）重名极多，不能只凭名字跨阵营合并
GENERIC_NAME_RE = re.compile(r"^[\u4e00-\u9fa5]{1,2}氏$")


def norm(s):
    """归一化名字用于匹配：去空格、去标点、全角转半角。"""
    s = (s or "").strip()
    s = s.replace("　", "").replace(" ", "")
    s = re.sub(r"[·・．.、，,（）()\[\]【】]", "", s)
    return s


def sim(a, b):
    """粗粒度相似度：完全包含或 2-gram Jaccard。"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
        return 0.75
    ga = {a[i:i + 2] for i in range(len(a) - 1)}
    gb = {b[i:i + 2] for i in range(len(b) - 1)}
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)
