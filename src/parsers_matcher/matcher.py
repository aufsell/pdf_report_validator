import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from src.models.structured_document import *
from src.models.message import *


def contains_fuzzy(full_text: str, pattern: str) -> bool:
    # Очистка и нормализация один раз
    def normalize(text):
        words = []
        for word in text.split():
            cleaned = ''.join(ch for ch in word.lower() if ch.isalpha() or ch == '-')
            if cleaned:
                words.append(cleaned)
        return words
    
    full_words = normalize(full_text)
    pat_words = normalize(pattern)
    
    if not pat_words:
        return True
    if len(pat_words) > len(full_words):
        return False
    
    # Предвычисляем основы для длинных слов (кеш)
    def base(word):
        return word[:-2] if len(word) > 4 else word
    
    pat_bases = [base(w) for w in pat_words]
    
    for start in range(len(full_words) - len(pat_words) + 1):
        match = True
        for i, pat_word in enumerate(pat_words):
            full_word = full_words[start + i]
            # Быстрое сравнение
            if full_word == pat_word:
                continue
            if len(pat_word) <= 4 or len(full_word) <= 4:
                if not full_word.startswith(pat_word) and not pat_word.startswith(full_word):
                    match = False
                    break
            else:
                if base(full_word) != pat_bases[i]:
                    match = False
                    break
        if match:
            return True
    return False

class Parser(Enum):
    NONE = 0
    INTRODUCTION = 1
    BODY = 2
    CONCLUSION = 6
    
    REFERENCES = 7
    
    APPENDIX_A = 8
    APPENDIX_B = 9
    
    MAG_INTRODUCTION = 101
    MAG_BODY = 102
    MAG_CONCLUSION = 106

class BlockType(Enum):
    TITLE = 1
    TOC = 2
    SECTION = 3
    PARAGRAPH = 4
    TABLE = 5
    FIGURE = 6
    NONE = 0

@dataclass
class BlockMetainfo:
    """Метаинформация блока в плоском представлении."""
    level: int = 0                # уровень заголовка (для SECTION)
    text: str = ""                # текстовое содержимое (для SECTION, PARAGRAPH)
    style: str = ""               # стиль (для PARAGRAPH)
    caption: str = ""             # подпись (для TABLE, FIGURE)
    extra: Dict[str, Any] = field(default_factory=dict)  # дополнительные данные

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
    HEADER_TO_PARSER_MAG = {
        "Введение": Parser.MAG_INTRODUCTION,
        
        
        "Заключение": Parser.MAG_CONCLUSION,
        
        "Список литературы": Parser.REFERENCES,
        "Список источников литературы": Parser.REFERENCES,
        "Список источников": Parser.REFERENCES,
        "Список использованных источников": Parser.REFERENCES,
        
        "Приложение": Parser.APPENDIX_A,
        
        "Приложение 1": Parser.APPENDIX_A,
        "Приложение 2": Parser.APPENDIX_B,
        
        "Приложение А": Parser.APPENDIX_A,
        "Приложение Б": Parser.APPENDIX_B,
    }

    HEADER_TO_PARSER_BACH = {
        "Введение": Parser.INTRODUCTION,
        
        
        
        "Заключение": Parser.CONCLUSION,
        
        "Список литературы": Parser.REFERENCES,
        "Список источников литературы": Parser.REFERENCES,
        "Список источников": Parser.REFERENCES,
        "Список использованных источников": Parser.REFERENCES,
        
        "Приложение": Parser.APPENDIX_A,
        
        "Приложение 1": Parser.APPENDIX_A,
        "Приложение 2": Parser.APPENDIX_B,
        
        "Приложение А": Parser.APPENDIX_A,
        "Приложение Б": Parser.APPENDIX_B,
    }

    def __init__(self, documentBlock: DocumentBlock):
        self.doc = documentBlock
        self.flat_blocks = []          # временное хранилище (info, block_obj)
        self.block_counter = 0
        self.ismag = False

    def _add_block(self, block_type: BlockType, block_obj: Any, metainfo: Optional[BlockMetainfo] = None):
        """Добавляет блок в плоское представление с возможностью указать метаинформацию."""
        if metainfo is None:
            metainfo = BlockMetainfo()
        info = FlatBlockInfo(
            id=self.block_counter,
            type=block_type,
            metainfo=metainfo
        )
        self.flat_blocks.append((info, block_obj))
        self.block_counter += 1

    def _extract_metainfo_for_section(self, section_block) -> BlockMetainfo:
        """Извлекает метаинформацию из раздела (заголовок + уровень)."""
        level = getattr(section_block, 'level', 0)
        title_text = ""
        if hasattr(section_block, 'title'):
            title = section_block.title
            if hasattr(title, 'text'):
                title_text = title.text.strip()
            elif isinstance(title, str):
                title_text = title.strip()
        return BlockMetainfo(level=level, text=title_text)

    def _extract_metainfo_for_paragraph(self, paragraph_block) -> BlockMetainfo:
        """Извлекает метаинформацию из параграфа (стиль, текст)."""
        style = getattr(paragraph_block, 'main_style', '')
        text = getattr(paragraph_block, 'text', '')
        return BlockMetainfo(style=style, text=text)

    def _extract_metainfo_for_table(self, table_block) -> BlockMetainfo:
        """Извлекает метаинформацию из таблицы (подпись, кол-во строк)."""
        caption = getattr(table_block, 'caption', '')
        rows = getattr(table_block, 'rows', [])
        extra = {'rows_count': len(rows)}
        return BlockMetainfo(caption=caption, extra=extra)

    def _extract_metainfo_for_figure(self, figure_block) -> BlockMetainfo:
        """Извлекает метаинформацию из рисунка (подпись, путь)."""
        caption = getattr(figure_block, 'caption', '')
        image = getattr(figure_block, 'image', '')
        extra = {'image_path': image}
        return BlockMetainfo(caption=caption, extra=extra)

    def _process_section(self, section: SectionBlock, parent_parser: Optional[Parser] = None) -> List[FlatBlocks]:
        """
        Рекурсивно обрабатывает раздел и все его вложенные разделы.
        Возвращает список FlatBlocks: первый элемент – сам раздел,
        затем FlatBlocks всех вложенных разделов (в порядке обхода).
        """
        # 1. Определяем парсер для этого раздела по его заголовку
        title_text = ""
        if hasattr(section, 'title'):
            title = section.title
            if hasattr(title, 'text'):
                title_text = title.text.strip()
            elif isinstance(title, str):
                title_text = title.strip()
        parser = self._get_parser_for_header(title_text)

        # 2. Создаём временный список блоков для текущего раздела
        current_blocks = []  # список (FlatBlockInfo, block_obj)
        block_counter = 0

        def add_block(block_type: BlockType, block_obj: Any, metainfo: Optional[BlockMetainfo] = None):
            nonlocal block_counter
            if metainfo is None:
                metainfo = BlockMetainfo()
            info = FlatBlockInfo(id=block_counter, type=block_type, metainfo=metainfo)
            current_blocks.append((info, block_obj))
            block_counter += 1

        # 3. Добавляем заголовок раздела
        if section.title is not None:
            metainfo = self._extract_metainfo_for_section(section)
            add_block(BlockType.SECTION, section.title, metainfo)

        # 4. Рекурсивно обходим содержимое раздела
        result = []  # список FlatBlocks для этого раздела и вложенных

        for sub in section.subblocks:
            if hasattr(sub, 'title') and hasattr(sub, 'level'):
                # Это вложенный раздел – обрабатываем его рекурсивно
                sub_flat_blocks = self._process_section(sub, parent_parser=parser)
                # Сначала добавляем накопленные блоки текущего раздела до вложенного раздела
                if current_blocks:
                    result.append(FlatBlocks(parser=parser, blocks=[info for info, _ in current_blocks]))
                    current_blocks.clear()
                # Затем добавляем все FlatBlocks вложенного раздела (включая его самого)
                result.extend(sub_flat_blocks)
            else:
                # Обычный блок (параграф, таблица, рисунок) – добавляем в текущий раздел
                if hasattr(sub, 'main_style') and hasattr(sub, 'text'):
                    metainfo = self._extract_metainfo_for_paragraph(sub)
                    add_block(BlockType.PARAGRAPH, sub, metainfo)
                elif hasattr(sub, 'image'):
                    metainfo = self._extract_metainfo_for_figure(sub)
                    add_block(BlockType.FIGURE, sub, metainfo)
                elif hasattr(sub, 'rows'):
                    metainfo = self._extract_metainfo_for_table(sub)
                    add_block(BlockType.TABLE, sub, metainfo)
                else:
                    add_block(BlockType.NONE, sub)

        # 5. После обработки всех подблоков добавляем оставшиеся блоки текущего раздела
        if current_blocks:
            result.insert(0, FlatBlocks(parser=parser, blocks=[info for info, _ in current_blocks]))

        return result

    def _process_subblock(self, sub: Block, current_parser: Parser):
        """Рекурсивно обрабатывает подблоки: разделы, параграфы, таблицы, рисунки."""
        # Если блок является разделом (имеет title и level)
        if hasattr(sub, 'title') and hasattr(sub, 'level'):
            metainfo = self._extract_metainfo_for_section(sub)
            self._add_block(BlockType.SECTION, sub, metainfo)
            for inner in getattr(sub, 'subblocks', []):
                self._process_subblock(inner, current_parser)
        # Параграф
        elif hasattr(sub, 'main_style') and hasattr(sub, 'text'):
            metainfo = self._extract_metainfo_for_paragraph(sub)
            self._add_block(BlockType.PARAGRAPH, sub, metainfo)
        # Рисунок
        elif hasattr(sub, 'image'):
            metainfo = self._extract_metainfo_for_figure(sub)
            self._add_block(BlockType.FIGURE, sub, metainfo)
        # Таблица
        elif hasattr(sub, 'rows'):
            metainfo = self._extract_metainfo_for_table(sub)
            self._add_block(BlockType.TABLE, sub, metainfo)
        else:
            # Неизвестный тип – сохраняем как есть, метаинформация пустая
            self._add_block(BlockType.NONE, sub)

    def _normalize_header(self, header: str) -> str:
        """Удаляет точку в конце и лишние пробелы для сопоставления."""
        header = header.strip()
        if header.endswith('.'):
            header = header[:-1].strip()
        return header

    def _is_similar_phrase(self, phrase1: str, phrase2: str) -> bool:
        """
        Проверяет, похожи ли две фразы с точностью до окончаний слов.
        Возвращает True, если все слова более короткой фразы совпадают
        (с учётом возможных различий в падежах/числах) с началом более длинной фразы.
        """
        def clean_word(word: str) -> str:
            # Оставляем только буквы (включая ё) и дефис
            return ''.join(ch for ch in word.lower().replace('c', 'с') if ch.isalpha() or ch == '-')

        words1 = [clean_word(w) for w in phrase1.split() if clean_word(w)]
        words2 = [clean_word(w) for w in phrase2.split() if clean_word(w)]

        def word_similar(w1: str, w2: str) -> bool:
            if w1 == w2:
                return True
            # Для коротких слов (≤4 букв) сравниваем начало более длинного
            if len(w1) <= 4 or len(w2) <= 4:
                return w1.startswith(w2) or w2.startswith(w1)
            # Для длинных отбрасываем последние 2 символа и сравниваем основы
            return w1[:-2] == w2[:-2]

        min_len = min(len(words1), len(words2))
        return all(word_similar(words1[i], words2[i]) for i in range(min_len))


    def _get_parser_for_header(self, header: str) -> Parser:
        clean = self._normalize_header(header)   # нормализация (приведение регистра, удаление лишнего)

        # 1. Точное совпадение (быстрый путь)
        if self.ismag and clean in self.HEADER_TO_PARSER_MAG:
            return self.HEADER_TO_PARSER_MAG[clean]
        if not self.ismag and clean in self.HEADER_TO_PARSER_BACH:
            return self.HEADER_TO_PARSER_BACH[clean]

        # 2. Нечёткое совпадение (похожие заголовки)
        target_dict = self.HEADER_TO_PARSER_MAG if self.ismag else self.HEADER_TO_PARSER_BACH
        for key, parser in target_dict.items():
            if self._is_similar_phrase(header, key):
                return parser

        return Parser.MAG_BODY if self.ismag else Parser.BODY

    def _extract_metainfo_for_title_block(self, title_block) -> (BlockMetainfo, bool):
        texts = []
        if hasattr(title_block, 'subblocks'):
            for sub in title_block.subblocks:
                if hasattr(sub, 'text'):
                    texts.append(sub.text)
        full_text = "\n".join(texts)
        ismag = contains_fuzzy(full_text, "Научно-исследовательская работа") and contains_fuzzy(full_text, "производственной, технологической практике ");
        return BlockMetainfo(text=full_text, extra={'lines': texts, 'ismag': ismag}), ismag

    def _extract_metainfo_for_toc_block(self, toc_block) -> BlockMetainfo:
        entries = {}
        if hasattr(toc_block, 'entries'):
            entries = toc_block.entries
        return BlockMetainfo(extra={'entries': entries})

    def match(self, messages: MessageCollector) -> List[FlatBlocks]:
        """Обходит структуру документа и возвращает список FlatBlocks."""
        result = []
        self.ismag = False

        # Титульный лист
        if self.doc.title is not None:
            metainfo, self.ismag = self._extract_metainfo_for_title_block(self.doc.title)
            self._add_block(BlockType.TITLE, self.doc.title, metainfo)
            blocks_for_title = [info for info, _ in self.flat_blocks]
            result.append(FlatBlocks(parser=Parser.NONE, blocks=blocks_for_title))
            self.flat_blocks.clear()
        else:
            messages.add_error(0, 'Нет титульного листа')
            return result

        # Оглавление
        if self.doc.toc is not None:
            metainfo = self._extract_metainfo_for_toc_block(self.doc.toc)
            self._add_block(BlockType.TOC, self.doc.toc, metainfo)
            blocks_for_toc = [info for info, _ in self.flat_blocks]
            result.append(FlatBlocks(parser=Parser.NONE, blocks=blocks_for_toc))
            self.flat_blocks.clear()
        else:
            messages.add_error(0, 'Нет оглавления')
            return result

        # Основные разделы
        for section in self.doc.subblocks:
            if hasattr(section, 'title') and hasattr(section, 'level'):
                section_flat_blocks = self._process_section(section)
                result.extend(section_flat_blocks)
            else:
                # Если нет заголовка – просто игнорируем или обрабатываем как часть предыдущего?
                # По умолчанию пропускаем.
                continue

        # Оставшиеся блоки (если есть после основных разделов)
        if self.flat_blocks:
            blocks_rest = [info for info, _ in self.flat_blocks]
            result.append(FlatBlocks(parser=Parser.NONE, blocks=blocks_rest))

        return result



