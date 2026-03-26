import re
from typing import Optional

def iter_lines(page_dict: dict):
    """Генератор: каждая строка титульного листа как dict {text, bbox, spans}."""
    d = page_dict
    for block in d.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            raw_text = "".join(s.get("text", "") for s in spans)
            text = re.sub(r"\s+", " ", raw_text).strip()
            if not text:
                continue
            yield {
                "text": text,
                "bbox": line.get("bbox"),
                "spans": spans,
                "block_bbox": block.get("bbox"),
            }

STUDENT_PATTERNS = [
    r"""обучающ\w*      # 'Обучающийся' / 'обучающаяся'
        \s+             # пробел(ы)
        (?P<name>[^,]+) # все до запятой = ФИО
        ,\s*№\s*        # ", № "
        (?P<group>[A-ЯЁA-Z0-9\-]+) # группа
    """,
]

SUPERVISOR_PATTERNS = [
    r"руководител[ья][^:]*:\s*(?P<full>.+)",
    r"научн\w*\s+руководител[ья][^:]*:\s*(?P<full>.+)",
    r"рук\.\s*практик[иья]\s*[:\-]?\s*(?P<full>.+)",
]

MAJOR_PATTERNS = [
    r"направлени[ея]\s*(подготовки)?\s*[:\-]?\s*(?P<major>.+)",
]

SPECIALIZATION_PATTERNS = [
    r"(специальност[ьи]|профиль)\s*[:\-]?\s*(?P<spec>.+)",
]

def match_student(text: str) -> dict | None:
    t = text.strip()
    low = t.lower()
    if "обучающ" not in low:
        return None
    for pat in STUDENT_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE | re.VERBOSE)
        if m:
            return {
                "student_group": m.group("group").strip(),
                "student_full_name": m.group("name").strip(),
            }
    return None


def match_supervisor(text: str) -> dict | None:
    t = text.strip()
    low = t.lower()
    if "руковод" not in low:
        return None
    for pat in SUPERVISOR_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            full = m.group("full").strip()
            return {"supervisor_full_name": full}
    return None


def match_major(text: str) -> dict | None:
    t = text.strip()
    low = t.lower()
    if "направлени" not in low:
        return None
    for pat in MAJOR_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            return {"major": m.group("major").strip()}
    return None


def match_specialization(text: str) -> dict | None:
    t = text.strip()
    low = t.lower()
    if "специальност" not in low and "профиль" not in low:
        return None
    for pat in SPECIALIZATION_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            return {"specialization": m.group("spec").strip()}
    return None


def detect_practice_type(group: Optional[str]) -> Optional[str]:
    """
    По номеру группы определяем тип практики:
    - если первая цифра номера = 3 → бакалавриат
    - если первая цифра номера = 4 → магистратура
    """
    if not group:
        return None

    digits = "".join(ch for ch in group if ch.isdigit())
    if not digits:
        return None

    first = digits[0]
    if first == "3":
        return "бакалавр"
    if first == "4":
        return "магистр"
    return None


def detect_university(line: dict) -> Optional[str]:
    """Строки 'Министерство...', 'Федеральное...', 'университет', можно объединять."""
    t = line["text"].strip()
    low = t.lower()
    if "университет" in low or "итмо" in low:
        return t
    return None


def detect_faculty(line: dict) -> Optional[str]:
    t = line["text"].strip()
    low = t.lower()
    if "факультет" in low:
        return t
    return None


def detect_year(line: dict) -> Optional[int]:
    t = line["text"]
    m = re.search(r"(20\d{2})", t)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None