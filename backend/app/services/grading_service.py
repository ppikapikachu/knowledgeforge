"""快照判分服务。

判分依据 practice_paper_item.question_snapshot 中的 correct_answer
（组卷时的快照标准答案），不实时读取 question 表：
源题后续修改/下架不影响本次判分结果（数据一致性要求）。

判分规则（docs/14 §9）：
    - SINGLE_CHOICE：用户选项集合与正确集合完全一致（答案=选项键字符串）
    - MULTIPLE_CHOICE：集合完全一致，漏选/多选均判错（答案=选项键数组，去重、拒未知键）
    - TRUE_FALSE：标准化后比较 TRUE/FALSE（答案=布尔或可归一字符串）
    - SHORT_ANSWER：不自动判分，ungraded，不进正确率分母（答案=文本字符串）

答案按题型为不同 JSON 值（9.1）：单选=字符串、多选=字符串数组、判断=布尔（兼容字符串）、
简答=字符串。非法类型/未知选项键直接参数错误，不做静默截断或模糊猜测。
"""

from decimal import Decimal
from typing import Any, List, Optional

from app.core.exceptions import ValidationException

CHOICE_TYPES = ("SINGLE_CHOICE", "MULTIPLE_CHOICE")
SHORT_ANSWER_MAX_LENGTH = 5000


def normalize_choice_keys(answer: List[str]) -> str:
    """把用户答案数组规范成排序去重的大写选项键串，如 'A,B'。"""
    keys = {str(k).strip().upper() for k in (answer or []) if str(k).strip()}
    return ",".join(sorted(keys))


def normalize_bool_answer(value) -> str:
    """判断题答案标准化为 'TRUE'/'FALSE'。"""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    raw = str(value or "").strip().upper()
    if raw in ("TRUE", "T", "1", "对", "Y", "YES"):
        return "TRUE"
    if raw in ("FALSE", "F", "0", "错", "N", "NO"):
        return "FALSE"
    return raw


def _snapshot_option_keys(question_snapshot: dict) -> set:
    """从快照提取合法选项键集合（为空表示快照未带选项，跳过未知键校验）。"""
    keys = set()
    for opt in (question_snapshot or {}).get("options") or []:
        if isinstance(opt, dict):
            key = opt.get("option_key", opt.get("key"))
            if key:
                keys.add(str(key).strip().upper())
    return keys


def coerce_answer(question_snapshot: dict, answer: Any) -> str:
    """按题型把 JSON 答案规范化为判分用文本（9.1）。

    - 单选：字符串或单元素数组 → 大写选项键；必须是快照中存在的键
    - 多选：字符串数组（或兼容逗号分隔字符串）→ 排序去重键串；拒未知键
    - 判断：布尔 / 可归一字符串 → 'TRUE'/'FALSE'
    - 简答：字符串（或数组 join）→ 原文，限长 5000

    非法类型或未知选项键抛 ValidationException（40001），绝不静默降级。
    """
    q_type = (question_snapshot or {}).get("question_type", "")
    valid_keys = _snapshot_option_keys(question_snapshot)

    if q_type == "SINGLE_CHOICE":
        if isinstance(answer, str):
            key = answer.strip().upper()
        elif isinstance(answer, list) and len(answer) == 1:
            key = str(answer[0]).strip().upper()
        else:
            raise ValidationException("单选题答案必须是选项键字符串（如 \"A\"）")
        if not key:
            raise ValidationException("单选题答案不能为空")
        if valid_keys and key not in valid_keys:
            raise ValidationException(f"未知选项键: {key}")
        return key

    if q_type == "MULTIPLE_CHOICE":
        if isinstance(answer, str):
            raw_list = [k for k in answer.split(",") if k.strip()]
        elif isinstance(answer, list):
            raw_list = answer
        else:
            raise ValidationException("多选题答案必须是选项键字符串数组（如 [\"A\",\"B\"]）")
        keys = {str(k).strip().upper() for k in raw_list if str(k).strip()}
        if not keys:
            raise ValidationException("多选题答案不能为空")
        unknown = sorted(k for k in keys if valid_keys and k not in valid_keys)
        if unknown:
            raise ValidationException(f"未知选项键: {unknown}")
        return ",".join(sorted(keys))

    if q_type == "TRUE_FALSE":
        if isinstance(answer, bool):
            return "TRUE" if answer else "FALSE"
        if isinstance(answer, list) and len(answer) == 1:
            answer = answer[0]
        text = normalize_bool_answer(answer)
        if text not in ("TRUE", "FALSE"):
            raise ValidationException("判断题答案必须是布尔值或 TRUE/FALSE")
        return text

    # SHORT_ANSWER 及其他：文本
    if isinstance(answer, str):
        text = answer
    elif isinstance(answer, list):
        text = ",".join(str(a) for a in answer)
    elif answer is None:
        text = ""
    else:
        raise ValidationException("简答题答案必须是字符串")
    if len(text) > SHORT_ANSWER_MAX_LENGTH:
        raise ValidationException(f"简答题答案长度不能超过 {SHORT_ANSWER_MAX_LENGTH} 字符")
    return text


def judge(question_snapshot: dict, answer: Any) -> dict:
    """按快照标准答案判分（答案先按题型规范化，见 coerce_answer）。

    返回：
        {
          "is_correct": Optional[bool],   # None=未判分（简答）
          "grading_status": "graded" | "ungraded",
          "score": Optional[Decimal],      # 得分，未判分为 None
          "user_answer_text": str,         # 规范化后的用户答案文本
        }
    """
    q_type = (question_snapshot or {}).get("question_type", "")
    correct_raw = (question_snapshot or {}).get("correct_answer", "")
    full_score = Decimal(str((question_snapshot or {}).get("score", 5)))

    user_text = coerce_answer(question_snapshot, answer)

    if q_type in CHOICE_TYPES:
        correct_keys = {str(k).strip().upper() for k in str(correct_raw).split(",") if str(k).strip()}
        correct_text = ",".join(sorted(correct_keys))
        is_correct = user_text == correct_text  # 集合完全一致
        return {
            "is_correct": bool(is_correct),
            "grading_status": "graded",
            "score": full_score if is_correct else Decimal("0"),
            "user_answer_text": user_text,
        }

    if q_type == "TRUE_FALSE":
        correct_text = normalize_bool_answer(correct_raw)
        is_correct = user_text == correct_text and user_text in ("TRUE", "FALSE")
        return {
            "is_correct": bool(is_correct),
            "grading_status": "graded",
            "score": full_score if is_correct else Decimal("0"),
            "user_answer_text": user_text,
        }

    # SHORT_ANSWER 及其他：不自动判分
    return {
        "is_correct": None,
        "grading_status": "ungraded",
        "score": None,
        "user_answer_text": user_text,
    }
