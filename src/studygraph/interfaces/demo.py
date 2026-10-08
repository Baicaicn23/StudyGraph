"""演示数据播种：预置学科知识库、复习笔记与几条典型误区。

    uv run studygraph-demo                # 写入默认数据库
    uv run studygraph-demo --db demo.db   # 写到指定数据库
    uv run studygraph-demo --reset        # 先清空演示库再写入

内容全部为**自编教学材料**（定义 / 公式 / 例子 / 易错点 / 口语说法对照），
不涉及任何教材版权。让演示一开始就有「真材实料」，而不是空库。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from ..application.learning_service import LearningService
from ..config import Settings, get_settings
from ..infrastructure.embeddings import get_embedder
from ..infrastructure.knowledge import KnowledgeStore
from ..infrastructure.learning_repository import SqliteLearningRepository

# 学科 -> [(标题, 正文)]。正文含：定义、要点、例子、易错点、口语说法对照。
DEMO_NOTES: dict[str, list[tuple[str, str]]] = {
    "高等数学-微积分": [
        (
            "极限与连续",
            "【定义】函数在 x→a 时的极限是当 x 无限接近 a 时函数值趋近的数。"
            "【要点】极限存在不要求在 a 点有定义。"
            "【例子】lim(x→2)(x²-4)/(x-2)=4。"
            "【易错点】把「可去间断点」当成「极限不存在」。"
            "【口语说法对照】「越靠近越接近那个数」→ 极限；"
            "「中间有个洞但两边接得上」→ 可去间断点。",
        ),
        (
            "导数的定义与几何意义",
            "【定义】导数是函数在某点的瞬时变化率，等于差商的极限。"
            "【几何意义】曲线在该点切线的斜率。"
            "【例子】f(x)=x² 在 x=3 处导数为 6。"
            "【易错点】把「导数存在」和「函数连续」混为一谈——可导一定连续，连续不一定可导。"
            "【口语说法对照】「曲线在这一点的陡不陡」→ 切线斜率；「变化快慢」→ 导数。",
        ),
        (
            "定积分与不定积分的区别",
            "【定义】不定积分是求原函数，结果是一个函数族（要加常数 C）；"
            "定积分是求区间上的累积量，结果是一个数值。"
            "【例子】∫2x dx = x²+C（函数）；∫₀¹2x dx = 1（数值）。"
            "【易错点】把定积分的结果写成带 C 的函数，或把不定积分当成数值。"
            "【口语说法对照】「带 C 的那个」→ 不定积分；「算出来一个数」→ 定积分。",
        ),
    ],
    "线性代数": [
        (
            "矩阵与行列式",
            "【定义】矩阵是数排成的矩形表；行列式是由方阵算出的一个数。"
            "【要点】只有方阵才有行列式；行列式为 0 表示矩阵不可逆。"
            "【例子】二阶行列式 |a b; c d| = ad-bc。"
            "【易错点】把矩阵和行列式当成同一种东西——矩阵是「表」，行列式是「数」。",
        ),
        (
            "特征值与特征向量",
            "【定义】对矩阵 A，若存在非零向量 v 使 Av=λv，则 λ 是特征值，v 是对应特征向量。"
            "【几何意义】特征向量方向在变换后不变，只被拉伸 λ 倍。"
            "【例子】对角矩阵的特征值就是对角线元素。"
            "【易错点】把「特征向量」和「基向量」搞混——特征向量是特殊的、方向不变的向量，不一定是坐标轴方向。",
        ),
        (
            "矩阵的秩",
            "【定义】矩阵的秩等于其行阶梯形中非零行的数目，也等于最大线性无关行(列)向量的个数。"
            "【要点】秩衡量矩阵携带的「独立信息量」。"
            "【易错点】以为秩就是行数或列数——只有当行(列)全部线性无关时才是。",
        ),
    ],
    "大学物理": [
        (
            "牛顿第二定律",
            "【定义】物体加速度与合外力成正比、与质量成反比：F=ma。"
            "【例子】2kg 物体受 6N 合力，加速度为 3m/s²。"
            "【易错点】F 是合力，不是某一个力；质量必须用 kg、加速度用 m/s²。",
        ),
        (
            "动能定理",
            "【定义】合外力做的功等于动能的变化量：W合=ΔEk=½mv²-½mv₀²。"
            "【例子】从静止加速到 v，合功 = ½mv²。"
            "【易错点】和动量定理混用——动能与速度平方相关，动量与速度一次方相关。",
        ),
        (
            "简谐运动",
            "【定义】回复力与位移成正比且方向相反的运动，x=Acos(ωt+φ)。"
            "【要点】周期 T=2π√(m/k)，与振幅无关。"
            "【易错点】以为振幅越大周期越长——简谐运动的周期与振幅无关。",
        ),
    ],
    "数据结构": [
        (
            "数组与链表",
            "【对比】数组随机访问 O(1)、插入删除 O(n)；链表插入删除 O(1)、随机访问 O(n)。"
            "【例子】频繁按下标读取用数组；频繁在头部插删用链表。"
            "【易错点】以为链表「查找快」——链表查找要逐个走，是 O(n)。",
        ),
        (
            "二叉搜索树",
            "【定义】左子树所有键值小于根，右子树所有键值大于根。"
            "【复杂度】平均查找/插入 O(log n)，但最坏退化成链表 O(n)。"
            "【易错点】以为最坏也是 O(log n)；平衡树（AVL/红黑树）才保证 O(log n)。",
        ),
        (
            "栈与队列",
            "【定义】栈是后进先出(LIFO)；队列是先进先出(FIFO)。"
            "【例子】函数调用栈、撤销操作 → 栈；打印队列、消息队列 → 队列。"
            "【易错点】把两者顺序记反。",
        ),
    ],
    "大学英语四级": [
        (
            "作文三段式结构",
            "【结构】开头点题亮观点 → 主体两到三个论点加例子 → 结尾总结升华。"
            "【要点】每段一个中心句，段落之间用连接词过渡。"
            "【常见错误】全文一段到底、没有中心句。",
        ),
        (
            "常用连接词",
            "【递进】besides, moreover, furthermore；【转折】however, nevertheless；"
            "【因果】therefore, consequently, as a result；【举例】for instance, such as。"
            "【常见错误】however 与 but 重复连用。",
        ),
        (
            "听力高频场景词",
            "【校园】registration, deadline, assignment, lecture；"
            "【出行】departure, reservation, transfer；【求职】interview, resume, salary。"
            "【技巧】先看题干关键词，再带着问题听。",
        ),
    ],
}

# 典型误区（带学科），用于演示「从错题出题」。
DEMO_MISTAKES: list[dict[str, str]] = [
    {
        "library": "线性代数",
        "question": "什么是特征值？",
        "note": "我把特征向量和基向量搞混了，以为特征向量一定是坐标轴方向。",
    },
    {
        "library": "高等数学-微积分",
        "question": "定积分和不定积分有什么区别？",
        "note": "我把结果类型搞混了：一个是数值，一个是函数族。",
    },
    {
        "library": "数据结构",
        "question": "二叉搜索树的查找复杂度是多少？",
        "note": "我以为最坏情况也是 O(log n)。",
    },
]


def seed(settings: Settings, *, user_id: str = "local") -> dict[str, object]:
    knowledge = KnowledgeStore(settings.database_path, embedder=get_embedder(settings))
    repository = SqliteLearningRepository(settings.database_path)
    learning = LearningService(knowledge, repository)

    note_count = 0
    for library, notes in DEMO_NOTES.items():
        for title, content in notes:
            knowledge.add_note(library, title, content)
            note_count += 1

    mistake_count = 0
    for mistake in DEMO_MISTAKES:
        learning.add_feedback(user_id=user_id, **mistake)
        mistake_count += 1

    return {
        "libraries": list(DEMO_NOTES),
        "notes": note_count,
        "mistakes": mistake_count,
        "database": settings.database_path,
    }


def _reset_database(path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        target = Path(f"{path}{suffix}")
        if target.exists():
            target.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studygraph-demo", description="播种演示数据")
    parser.add_argument("--db", default=None, help="数据库路径（默认读环境变量）")
    parser.add_argument("--user", default="local", help="错题归属的用户标识")
    parser.add_argument("--reset", action="store_true", help="先删除数据库再播种")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.db:
        settings = replace(settings, database_path=args.db)
    if args.reset:
        _reset_database(settings.database_path)

    result = seed(settings, user_id=args.user)
    print("演示数据已写入：")
    print(f"  数据库：{result['database']}")
    print(f"  学科知识库：{'、'.join(result['libraries'])}")  # type: ignore[arg-type]
    print(f"  复习笔记：{result['notes']} 份")
    print(f"  典型误区：{result['mistakes']} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
