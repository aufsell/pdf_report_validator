import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

# Допустим, что эти типы уже определены, но для полноты приведём их здесь
class Parser(Enum):
    NONE = 0
    INTRODUCTION = 1
    STAGE_DESCRIPTION = 2
    LECTURES = 3
    THESIS_TEMPLATE = 4
    TECHNICAL_TASK = 5
    CONCLUSION = 6
    REFERENCES = 7
    APPENDIX_A = 8
    APPENDIX_B = 9
    MAG_INTRODUCTION = 101
    DOMAIN_ANALYSIS = 102
    MODEL_DESIGN = 103
    MODEL_IMPLEMENTATION = 104
    TESTING_RESEARCH = 105
    MAG_CONCLUSION = 106

class BlockType(Enum):
    TITLE = 1
    TOC = 2
    SECTION = 3
    PARAGRAPH = 4
    TABLE = 5
    FIGURE = 6

@dataclass
class BlockMetainfo:
    # Здесь можно хранить любую дополнительную информацию
    # Например, для таблицы – количество строк, для рисунка – подпись и т.д.
    pass

@dataclass
class FlatBlockInfo:
    id: int
    type: BlockType
    metainfo: BlockMetainfo

@dataclass
class FlatBlocks:
    parser: Parser
    blocks: List[FlatBlockInfo]


class ParsersMatcher:
    """Сопоставляет заголовки документа с парсерами и разбивает блоки по разделам."""

    # Соответствие заголовков разделов парсерам (для магистров)
    HEADER_TO_PARSER_MAG = {
        "Введение": Parser.MAG_INTRODUCTION,
        "1. Анализ предметной области": Parser.DOMAIN_ANALYSIS,
        "2. Проектирование модели": Parser.MODEL_DESIGN,
        "3. Реализация модели": Parser.MODEL_IMPLEMENTATION,
        "4. Тестирование и исследование": Parser.TESTING_RESEARCH,
        "Заключение": Parser.MAG_CONCLUSION,
        "Список использованных источников": Parser.REFERENCES,
        "Приложение А. Исходный код программы (main.py)": Parser.APPENDIX_A,
        "Приложение Б. Отзыв руководителя": Parser.APPENDIX_B,
    }

    # Для бакалавров – аналогичный словарь (можно расширить)
    HEADER_TO_PARSER_BACH = {
        "Введение": Parser.INTRODUCTION,
        "Заключение": Parser.CONCLUSION,
        "Список использованных источников": Parser.REFERENCES,
        "Приложение А": Parser.APPENDIX_A,
        "Приложение Б": Parser.APPENDIX_B,
    }

    def __init__(self, json_str: str):
        self.doc = json.loads(json_str)
        self.flat_blocks = []          # будет заполняться при обходе
        self.block_counter = 0

    def _add_block(self, block_type: BlockType, block_obj: Any):
        """Добавляет блок в список flat_blocks с присвоением id."""
        info = FlatBlockInfo(
            id=self.block_counter,
            type=block_type,
            metainfo=BlockMetainfo()   # здесь можно заполнить метаданные
        )
        self.flat_blocks.append((info, block_obj))
        self.block_counter += 1

    def _process_section(self, section: Dict, parser: Parser):
        """
        Рекурсивно обрабатывает раздел: добавляет сам заголовок и все вложенные блоки.
        Возвращает список собранных блоков.
        """
        # Добавляем заголовок раздела
        title = section.get("title", {})
        if title:
            self._add_block(BlockType.SECTION, title)

        # Обрабатываем подблоки раздела
        for sub in section.get("subblocks", []):
            self._process_subblock(sub, parser)

    def _process_subblock(self, sub: Dict, current_parser: Parser):
        """
        Обрабатывает один подблок (может быть текстовым блоком, таблицей, рисунком,
        вложенным разделом и т.д.)
        """
        if "title" in sub and "level" in sub:
            # Это вложенный раздел (например, подраздел 1.1)
            # Для простоты мы добавляем его как обычный блок, но можно и рекурсивно
            self._add_block(BlockType.SECTION, sub)
            # Рекурсивно обрабатываем его содержимое
            for s in sub.get("subblocks", []):
                self._process_subblock(s, current_parser)
        elif "main_style" in sub and "text" in sub:
            # Это текстовый блок (параграф)
            self._add_block(BlockType.PARAGRAPH, sub)
        elif "image" in sub:
            # Рисунок
            self._add_block(BlockType.FIGURE, sub)
        elif "rows" in sub:
            # Таблица
            self._add_block(BlockType.TABLE, sub)
        else:
            # Неизвестный тип – сохраняем как есть
            self._add_block(BlockType.NONE, sub)

    def match(self) -> List[FlatBlocks]:
        """
        Основной метод: обходит структуру документа и формирует список разделов
        с привязанными к ним блоками.
        """
        result = []

        # Обработка титульного листа
        title_block = self.doc.get("title")
        if title_block:
            self._add_block(BlockType.TITLE, title_block)
            # Собираем все блоки, относящиеся к титульнику (их может быть несколько)
            # В нашем случае титульник — это один блок, но можно собрать подблоки
            # Выделяем их в отдельный FlatBlocks с парсером NONE
            blocks_for_title = [info for info, _ in self.flat_blocks if info.type == BlockType.TITLE]
            result.append(FlatBlocks(parser=Parser.NONE, blocks=blocks_for_title))
            self.flat_blocks.clear()  # очищаем, чтобы дальше собирать новые

        # Обработка оглавления
        toc_block = self.doc.get("toc")
        if toc_block:
            self._add_block(BlockType.TOC, toc_block)
            blocks_for_toc = [info for info, _ in self.flat_blocks if info.type == BlockType.TOC]
            result.append(FlatBlocks(parser=Parser.NONE, blocks=blocks_for_toc))
            self.flat_blocks.clear()

        # Обработка основных разделов (subblocks)
        for section in self.doc.get("subblocks", []):
            title_text = section.get("title", {}).get("text", "").strip()
            # Определяем парсер по заголовку
            parser = self._get_parser_for_header(title_text)
            # Обрабатываем раздел и собираем все его блоки
            self._process_section(section, parser)
            # Сохраняем собранные блоки для этого раздела
            blocks_for_section = [info for info, _ in self.flat_blocks]
            result.append(FlatBlocks(parser=parser, blocks=blocks_for_section))
            self.flat_blocks.clear()

        # Остальные блоки (если есть) – например, после последнего раздела
        if self.flat_blocks:
            blocks_rest = [info for info, _ in self.flat_blocks]
            result.append(FlatBlocks(parser=Parser.NONE, blocks=blocks_rest))

        return result

    def _get_parser_for_header(self, header: str) -> Parser:
        """
        Определяет парсер по тексту заголовка.
        Сначала пробуем магистерские, затем бакалаврские.
        """
        # Удаляем возможные номера и точки в конце
        clean_header = header.strip()
        if clean_header in self.HEADER_TO_PARSER_MAG:
            return self.HEADER_TO_PARSER_MAG[clean_header]
        if clean_header in self.HEADER_TO_PARSER_BACH:
            return self.HEADER_TO_PARSER_BACH[clean_header]
        return Parser.NONE


# Пример использования (при условии, что json_str — это сериализованный DocumentBlock)
# matcher = ParsersMatcher(json_str)
# sections = matcher.match()
# for sect in sections:
#     print(sect.parser, len(sect.blocks))