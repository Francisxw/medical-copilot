"""医疗术语配置与语料构造。"""

from __future__ import annotations


MEDICAL_TERMS = {
    "diseases": [
        "高血压",
        "糖尿病",
        "冠心病",
        "肺炎",
        "支气管炎",
        "胃炎",
        "肝炎",
        "肾炎",
        "脑卒中",
        "肿瘤",
    ],
    "medications": [
        "阿司匹林",
        "胰岛素",
        "二甲双胍",
        "降压药",
        "抗生素",
        "维生素",
        "钙片",
        "感冒药",
    ],
    "symptoms": [
        "咳嗽",
        "发热",
        "头痛",
        "胸闷",
        "气短",
        "腹痛",
        "腹泻",
        "呕吐",
        "眩晕",
        "水肿",
    ],
    "examinations": [
        "血常规",
        "尿常规",
        "心电图",
        "胸片",
        "CT",
        "MRI",
        "B超",
        "胃镜",
        "肠镜",
    ],
    "units": ["mmol/L", "mg/L", "mmHg", "℃", "bpm"],
}


def build_medical_corpus() -> str:
    """构造用于 ASR 上下文偏置的医疗术语语料。"""
    ordered_terms: list[str] = []
    seen: set[str] = set()

    for terms in MEDICAL_TERMS.values():
        for term in terms:
            if term not in seen:
                ordered_terms.append(term)
                seen.add(term)

    return " ".join(ordered_terms)
