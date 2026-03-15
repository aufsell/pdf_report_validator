from enum import Enum
import re

from src.models.structured_document import *

PAGE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")

TABLE_CONTINUATION_RE = re.compile(
    r"""
    ^                           # Начало строки
    Продолжение\s+таблицы\s+№   # Фиксированный текст с любыми пробелами
    \s*                         # Возможный пробел после знака №
    \d+                         # Номер таблицы (одна или более цифр)
    .*                          # Любые символы до конца (тире, название и т.д.)
    $                           # Конец строки
    """,
    re.IGNORECASE | re.VERBOSE
)

TOC_BLOCK_RE = re.compile(
    r""" ^
        \s*                               # начальные пробелы
        (?P<title>.+?)                    # заголовок (ленивый)
        \s*                               # пробелы перед точками
        (?:(?:[\.·•…]\s*){3,})?           # опционально: минимум 3 символа-точки, 
                                          # между которыми могут быть пробелы
        (?P<page>\d{1,4})                 # номер страницы
        \s*                               # хвостовые пробелы
        $
    """,
    re.VERBOSE,
)

TOC_CAPTION_RE = re.compile(
    r"""(?<!\S)        # слева не буква/цифра (начало или пробел/знак)
    (Содержание|Оглавление)
    (?!\S)             # справа не буква/цифра
    """,
    re.IGNORECASE | re.VERBOSE,
)

TABLE_CAPTION_RE = re.compile(
    r"""^
    Таблица                    # слово 'Таблица'
    \s*
    (?:№\s*)?                  # опциональное '№'
    (?P<num>\d+)               # номер (группа 'num')
    \s*[–-]\s*                 # тире (– или -)
    (?P<title>.+)              # остальной текст (группа 'title')
    $""",
    re.IGNORECASE | re.VERBOSE,
)

TABLE_CONTINUATION_RE = re.compile(
    r"""
    ^                           # Начало строки
    Продолжение\s+таблицы\s+№   # Фиксированный текст с любыми пробелами
    \s*                         # Возможный пробел после знака №
    \d+                         # Номер таблицы (одна или более цифр)
    .*                          # Любые символы до конца (тире, название и т.д.)
    $                           # Конец строки
    """,
    re.IGNORECASE | re.VERBOSE
)

FIGURE_CAPTION_RE = re.compile(
    r"""^
    (?:Рисунок|Скриншот)       # Рисунок или Скриншот
    \s*
    (?:№\s*)?                  # опциональное '№'
    (?P<num>\d+)               # ГРУППА: номер
    \s*[–-]\s*                 # тире
    (?P<title>.+)              # ГРУППА: название
    $""",
    re.IGNORECASE | re.VERBOSE,
)

class LineType(Enum):
    PAGE_NUMBER = 1
    TABLE = 2
    TEXT = 3
    FIGURE = 4

class ParagraphType(Enum):
    TOC_CAPTION = 1
    TABLE_CAPTION = 2
    FIGURE_CAPTION = 3
    TABLE_CONTINUATION_CAPTION = 4
    HEADING = 5
    NORMAL = 6

def get_line_type(line: LineBlock) -> LineType:
    if len(line.blocks) > 1:
        return LineType.TABLE
    if isinstance(line.blocks[0], ImageBlock):
        return LineType.FIGURE
    if PAGE_NUMBER_RE.match(line.text()):
        return LineType.PAGE_NUMBER
    return LineType.TEXT


def has_between(a: list[float], left: float, right: float) -> bool:
    from bisect import bisect_left
    i = bisect_left(a, left)
    return i < len(a) and a[i] <= right