import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from src.models.structured_document import *
from src.models.message import *
from src.parsers_matcher.matcher import FlatBlocks, Parser
import re

def parse_title_page(lines: List[str], is_magister: bool, messages: MessageCollector) -> None:
    """
    Парсит титульный лист отчета и собирает ошибки/предупреждения.
    """
    if not lines:
        messages.add_error(0, "Титульный лист пуст.")
        return

    # Объединяем все строки для поиска элементов, которые могли быть перенесены
    full_text = " ".join(lines).lower()

    # 1. Проверка шапки и университета
    if "министерство науки и высшего образования" not in full_text:
        messages.add_error(0, "Отсутствует 'Министерство науки и высшего образования Российской Федерации'")
    if "университет итмо" not in full_text and "исследовательский университет итмо" not in full_text:
        messages.add_error(0, "Отсутствует упоминание 'Университет ИТМО'")
    if "программной инженерии и компьютерной техники" not in full_text:
        messages.add_error(0, "Отсутствует или неверно указан факультет (ожидается ПИиКТ)")

    # 2. Проверка направления подготовки
    if "направление подготовки" not in full_text:
        messages.add_error(0, "Отсутствует строка 'Направление подготовки (специальность)'")

    # 3. Проверка заголовка
    if "о т ч е т" not in full_text and "отчет" not in full_text:
        messages.add_error(0, "Отсутствует заголовок 'О Т Ч Е Т'")

    # 4. Проверка соответствия типа работы уровню образования
    if is_magister:
        if "научно-исследовательской" not in full_text:
            messages.add_error(0, "Для магистратуры ожидается 'о научно-исследовательской работе'")
    else:
        if "учебной" not in full_text and "ознакомительной" not in full_text and "производственной" not in full_text:
            messages.add_error(0,
                               "Для бакалавриата ожидается 'об учебной', 'ознакомительной' или 'производственной' практике")

    # Регулярное выражение для поиска группы (Латинская/Кириллическая буква + 4 цифры, например P3433)
    group_pattern = re.compile(r'([A-Za-zА-Яа-я])\s*(\d{4})')

    found_student = False
    found_group = False
    found_supervisor = False
    found_date = False
    found_city = False

    # Построчный анализ для поиска динамических данных
    for i, line in enumerate(lines):
        block_id = i + 1  # Индексация строк с 1 для удобства чтения
        text_lower = line.lower()

        if "обучающийся" in text_lower or "студент" in text_lower:
            found_student = True

        # Поиск группы и проверка курса
        group_match = group_pattern.search(text_lower)
        if group_match:
            found_group = True
            group_letter = group_match.group(1)
            group_digits = group_match.group(2)
            first_digit = group_digits[
                0]  # Первая цифра обычно указывает на уровень (3 - бакалавриат, 4 - магистратура)
            full_group = f"{group_letter}{group_digits}"

            if is_magister and first_digit == '3':
                messages.add_warning(block_id,
                                     f"Номер группы ({full_group}) характерен для бакалавриата, хотя проверяется магистратура")
            elif not is_magister and first_digit == '4':
                messages.add_warning(block_id,
                                     f"Номер группы ({full_group}) характерен для магистратуры, хотя проверяется бакалавриат")

        if "руководитель" in text_lower:
            found_supervisor = True

        if "дата" in text_lower:
            found_date = True

        if "санкт-петербург" in text_lower:
            found_city = True

    # 5. Проверка наличия обязательных блоков, не найденных при построчном обходе
    if not found_student:
        messages.add_error(0, "Не найден блок 'Обучающийся'")
    if not found_group:
        messages.add_error(0, "Не найден номер учебной группы в формате Буква+4 цифры (например, P3433)")
    if not found_supervisor:
        messages.add_error(0, "Не найден блок 'Руководитель практики'")
    if not found_date:
        messages.add_warning(0, "Отсутствует дата (ожидалось слово 'Дата')")
    if not found_city:
        messages.add_error(0, "Отсутствует город 'Санкт-Петербург' в конце титульного листа")

def parse_oglav(entries: Dict[str, Any], is_mag: bool, messages: MessageCollector) -> None:
    """Проверка оглавления."""
    # TODO: реализовать
    pass

def parse_introduction(text: str, is_mag: bool, messages: MessageCollector) -> None:
    """Проверка введения."""
    # TODO: реализовать
    pass


def analyze_report(text: str, is_mag: bool) -> Dict[str, float]:
    """
    Анализирует текст отчета по ключевым критериям, основанным на "Методичке".
    Возвращает словарь с оценками по каждому критерию (0.0 - 1.0) и итоговой оценкой.

    Args:
        text (str): Текст отчета для анализа.

    Returns:
        Dict[str, float]: Словарь с результатами анализа.
            Ключи: 'structure_score', 'process_description_score', 'code_placement_score',
                   'analysis_score', 'plagiarism_risk_score', 'final_score'
    """

    # Приводим текст к нижнему регистру для упрощения анализа
    lower_text = text.lower()

    # 1. КРИТЕРИЙ: Структура (Наличие обязательных разделов)
    structure_score = 0.0
    required_sections = ['введение', 'заключение', 'приложен']
    # Ищем разделы в содержании или по заголовкам в тексте
    found_sections = [section for section in required_sections if section in lower_text]
    structure_score = len(found_sections) / len(required_sections)

    # 2. КРИТЕРИЙ: Описание процесса (Ключевой критерий)
    process_description_score = 0.0
    # Ищем слова, указывающие на описание процесса и решения
    process_keywords = [
        'создал', 'разметил', 'реализовал', 'выбрал', 'потому', 'так', 'как',
        'целью', 'для', 'чтобы', 'алгоритм', 'методология', 'последовательно',
        'сначала', 'затем', 'после', 'выбран', 'позволил', 'согласовано', 'предоставлено', 'составлены'
    ]
    # Ищем слова, указывающие на простое перечисление результата (анти-критерий)
    result_keywords = ['итоге', 'реализовано', 'написал', 'изучил', 'выбрал', 'составил', 'создал', 'разработал']

    process_matches = sum(1 for keyword in process_keywords if keyword in lower_text)
    result_matches = sum(1 for keyword in result_keywords if keyword in lower_text)

    # Эвристика: если много "процессных" слов и мало "результатных" - хорошо
    total_indicators = process_matches + result_matches
    if total_indicators > 0:
        process_description_score = process_matches / total_indicators
    else:
        # Если нет ни тех, ни других, считаем нейтральным (0.5), но с штрафом в общем анализе
        process_description_score = 0.5

    # 3. КРИТЕРИЙ: Корректное размещение кода (Код в приложениях, а не в теле)
    code_placement_score = 1.0  # Изначально предполагаем лучший вариант
    # Простые регулярные выражения для поиска блоков кода (листингов)
    # Это могут быть участки в кавычках-фиксированной ширины или с отступами
    code_indicators = [
        r'.*?```',  # Маркдаун-блоки кода
        r'def\s+\w+.*?:\n(?:\s+.+\n)+',  # Простое определение функции Python
        r'np\.[a-zA-Z]',
        r'public\s+class.*?\{.*?\}',  # Пример для Java (очень грубо)
    ]

    total_code_blocks = 0
    # Считаем, сколько раз встречается слово "приложен" (приложение)
    appendix_refs = len(re.findall(r'приложен', lower_text))

    for pattern in code_indicators:
        blocks = re.findall(pattern, text, re.DOTALL)
        total_code_blocks += len(blocks)

    # Эвристика: если в тексте есть блоки кода, но нет ссылок на приложения - плохо
    if total_code_blocks > 0 and appendix_refs == 0:
        code_placement_score = 0.1  # Суровый штраф
    elif total_code_blocks > 0 and appendix_refs > 5:
        # Если код есть и есть ссылки на приложения, оценка средняя (возможно, код частично вынесен)
        code_placement_score = 0.8
    elif total_code_blocks > 0:
        # Если код есть и есть ссылки на приложения, оценка средняя (возможно, код частично вынесен)
        code_placement_score = 0.4
    # Если кода нет вообще или он полностью вынесен (total_code_blocks==0), score остается 1.0

    # 4. КРИТЕРИЙ: Наличие анализа данных/результатов
    analysis_score = 0.0
    analysis_keywords = [
        'анализ', 'результат', 'вывод', 'таблица', 'график', 'сравнен',
        'метрика', 'эффективность', 'обоснован'
    ]
    analysis_matches = sum(1 for keyword in analysis_keywords if keyword in lower_text)
    # Нормализуем оценку, чтобы она не была слишком высокой из-за частых слов
    analysis_score = min(analysis_matches / 5.0, 1.0)  # Максимум 1.0, даже если слов очень много
    # 5. КРИТЕРИЙ: Риск плагиата/водности (косвенный признак)
    plagiarism_risk_score = 1.0  # Изначально низкий риск
    # Признаки возможного плагиата/проблем с кодировкой
    if re.search(r'[ÂâÃã©®]', text):
        plagiarism_risk_score = 0.2  # Сильный индикатор копирования из внешнего источника

    # Признаки водности: много общих фраз, мало специфических терминов
    water_words = ['является', 'будет', 'иметь', 'следующий', 'данный', 'очень', 'большой']
    specific_words = ['датасет', 'метод', 'алгоритм', 'модуль', 'функция', 'код', 'реализация', 'сравнение']

    water_count = sum(1 for word in water_words if word in lower_text)
    specific_count = sum(1 for word in specific_words if word in lower_text)

    total_significant_words = water_count + specific_count
    if total_significant_words > 0:
        water_ratio = water_count / total_significant_words
        # Штрафуем за высокую долю "водных" слов
        plagiarism_risk_score = min(plagiarism_risk_score, 1.0 - water_ratio * 0.7)

    # ### ФИНАЛЬНАЯ ОЦЕНКА ###
    # Веса критериев можно настраивать. Самый высокий вес у описания процесса.
    weights = {
        'structure': 0.1,
        'process_description': 0.40,
        'code_placement': 0.40,
        'analysis': 0.40 if is_mag else 0.1,
        'plagiarism_risk': 0.05
    }

    final_score = (
        structure_score * weights['structure'] +
        process_description_score * weights['process_description'] +
        code_placement_score * weights['code_placement'] +
        analysis_score * weights['analysis'] +
        plagiarism_risk_score * weights['plagiarism_risk']
    )/ (weights['structure'] + weights['process_description'] + weights['code_placement'] + weights['analysis'] + weights['plagiarism_risk'])

    return {
        'structure_score': round(structure_score, 2),
        'process_description_score': round(process_description_score, 2),
        'code_placement_score': round(code_placement_score, 2),
        'analysis_score': round(analysis_score, 2),
        'plagiarism_risk_score': round(plagiarism_risk_score, 2),
        'final_score': round(final_score, 2)
    }

def parse_body(text: str, is_mag: bool, messages: MessageCollector) -> None:
    """Проверка основной части."""
    report = analyze_report(text, is_mag);
    print(report)
    if report['final_score'] < 0.75:
        messages.add_error(0, 'основная часть оценена на 3')
    elif report['final_score'] < 0.90:
        messages.add_warning(0, 'основная часть оценена на 4')
    else:
        messages.add_warning(0, 'основная часть оценена на 5')
    pass


def parse_conclusion(text: str, is_mag: bool, messages: MessageCollector) -> None:
    """Проверка заключения."""
    # TODO: реализовать
    pass

def parse_references(text: str, is_mag: bool, messages: MessageCollector) -> None:
    """Проверка списка литературы."""
    # TODO: реализовать
    pass

class DocumentStructureValidator:
    """Валидатор и преобразователь структуры документа."""
    
    def __init__(self, flat_blocks: List[FlatBlocks], messages: MessageCollector):
        self.flat_blocks = flat_blocks
        self.messages = messages
        self.is_mag = False
    
    @staticmethod
    def _get_flat_blocks_text(flat_blocks: FlatBlocks) -> str:
        """Извлекает весь текст из блоков внутри FlatBlocks."""
        texts = []
        for block in flat_blocks.blocks:
            # Для секций и параграфов текст хранится в metainfo.text
            if block.metainfo.text:
                texts.append(block.metainfo.text)
            # Для таблиц, рисунков можно добавить caption, но по условию не требуется
        return "\n".join(texts)
    
    def _remove_blocks_after_parser(self, target_parser: Parser, include_target: bool = False) -> None:
        """
        Удаляет все блоки после первого встреченного блока с парсером target_parser.
        Если include_target=True, то удаляет и сам найденный блок.
        """
        for idx, fb in enumerate(self.flat_blocks):
            if fb.parser == target_parser:
                # Обрезаем список: оставляем всё до idx (включительно или исключительно)
                del_idx = idx if include_target else idx + 1
                self.flat_blocks = self.flat_blocks[:del_idx]
                break
    
    def _find_parser_positions(self, target_parser: Parser) -> List[int]:
        """Возвращает список индексов FlatBlocks с заданным парсером."""
        return [i for i, fb in enumerate(self.flat_blocks) if fb.parser == target_parser]
    
    def _get_single_parser_block(self, target_parser: Parser, expected_position: Optional[int] = None) -> Optional[FlatBlocks]:
        """
        Ищет блок с парсером target_parser.
        Если expected_position задан, проверяет, что блок находится на этой позиции.
        Если блок не найден, добавляет ошибку и возвращает None.
        Если найдено несколько блоков, добавляет ошибку и возвращает None.
        Если блок найден ровно один, возвращает его (и если позиция не совпадает, но блок есть, всё равно возвращает).
        """
        positions = self._find_parser_positions(target_parser)
        if not positions:
            self.messages.add_error(0, f"Не найден блок с парсером {target_parser}")
            return None
        if len(positions) > 1:
            self.messages.add_error(0, f"Найдено несколько блоков с парсером {target_parser}: {positions}")
            return None
        idx = positions[0]
        if expected_position is not None and idx != expected_position:
            self.messages.add_error(0, f"Блок {target_parser} находится на позиции {idx}, ожидалась {expected_position}")
        return self.flat_blocks[idx]
    
    def _collect_all_body_texts(self, body_parser: Parser) -> str:
        """Собирает текст из всех блоков с парсером body_parser (обычно это несколько FlatBlocks)."""
        texts = []
        for fb in self.flat_blocks:
            if fb.parser == body_parser:
                texts.append(self._get_flat_blocks_text(fb))
        return "\n\n".join(texts)  # разделяем двойным переводом строки
    
    def validate(self) -> None:
        """Основная логика проверки и преобразования."""
        # 3. Проверка минимального количества блоков (титул + оглавление)
        if len(self.flat_blocks) < 2:
            self.messages.add_error(0, f"Недостаточно блоков в документе: {len(self.flat_blocks)} (ожидается минимум 2)")
            return
        
        # 4. Определение магистерская ли работа
        title_blocks = self.flat_blocks[0].blocks
        if not title_blocks:
            self.messages.add_error(0, "Титульный блок не содержит метаинформации")
            return
        self.is_mag = title_blocks[0].metainfo.extra.get("ismag", False)
        
        # 5. Проверка титульника
        lines = title_blocks[0].metainfo.extra.get("lines", [])
        parse_title_page(lines, self.is_mag, self.messages)
        
        # 6. Проверка оглавления
        if len(self.flat_blocks) < 2 or not self.flat_blocks[1].blocks:
            self.messages.add_error(0, "Отсутствует блок оглавления")
            return
        entries = self.flat_blocks[1].blocks[0].metainfo.extra.get("entries", {})
        parse_oglav(entries, self.is_mag, self.messages)
        
        # 7. Удалить все блоки после REFERENCES (если есть)
        self._remove_blocks_after_parser(Parser.REFERENCES, include_target=False)
        
        # 8. Удалить APPENDIX (8 или 9) и всё после них
        # Ищем первый APPENDIX_A или APPENDIX_B
        appendix_parsers = [Parser.APPENDIX_A, Parser.APPENDIX_B]
        for parser in appendix_parsers:
            positions = self._find_parser_positions(parser)
            if positions:
                # Удаляем с первого найденного приложения включительно и всё после
                del_idx = positions[0]
                self.flat_blocks = self.flat_blocks[:del_idx]
                break
        
        # Теперь после удалений определяем ожидаемые парсеры в зависимости от типа работы
        if self.is_mag:
            intro_parser = Parser.MAG_INTRODUCTION
            body_parser = Parser.MAG_BODY
            concl_parser = Parser.MAG_CONCLUSION
            references_parser = Parser.REFERENCES
        else:
            intro_parser = Parser.INTRODUCTION
            body_parser = Parser.BODY
            concl_parser = Parser.CONCLUSION
            references_parser = Parser.REFERENCES
        
        # 9-10. Введение: должно быть третьим по счёту (индекс 2) после титула и оглавления
        # Проверяем, что на позиции 2 находится нужный парсер
        expected_intro_index = 2
        intro_block = None
        if len(self.flat_blocks) > expected_intro_index and self.flat_blocks[expected_intro_index].parser == intro_parser:
            intro_block = self.flat_blocks[expected_intro_index]
        else:
            # Ищем в других местах
            intro_block = self._get_single_parser_block(intro_parser, expected_position=expected_intro_index)
        
        if intro_block is None:
            self.messages.add_error(0, f"Введение ({intro_parser}) не найдено")
        else:
            intro_text = self._get_flat_blocks_text(intro_block)
            parse_introduction(intro_text, self.is_mag, self.messages)
        
        # 11. Собрать все блоки BODY (их может быть несколько) и отдать текст
        body_text = self._collect_all_body_texts(body_parser)
        if not body_text.strip():
            self.messages.add_error(0, f"Основная часть ({body_parser}) пуста или отсутствует")
        else:
            parse_body(body_text, self.is_mag, self.messages)
        
        
        references_positions = self._find_parser_positions(references_parser)
        if not references_positions:
            self.messages.add_warning(0, f"Список использованной литературы не найден")
        elif len(references_positions) > 1:
            self.messages.add_error(0, f"Найдено несколько списков литературы: {references_positions}")
            return
        elif references_positions[0] != len(self.flat_blocks) - 1:
            self.messages.add_error(0, f"Список литературы не в конце документа")
        
        references_text = self._collect_all_body_texts(references_parser)
        if references_text.strip():
            parse_references(references_text, self.is_mag, self.messages)
        
        # 12-13. Заключение: должно быть последним блоком (после удалений)
        # Ищем единственное заключение в конце
        concl_positions = self._find_parser_positions(concl_parser)
        if not concl_positions:
            self.messages.add_error(0, f"Заключение ({concl_parser}) не найдено")
            return
        if len(concl_positions) > 1:
            self.messages.add_error(0, f"Найдено несколько заключений: {concl_positions}")
            return
        concl_idx = concl_positions[0]
        if concl_idx != len(self.flat_blocks) - 1 and not (concl_idx == len(self.flat_blocks) - 2 and references_positions):
            self.messages.add_error(0, f"Заключение находится не в конце документа (позиция {concl_idx}, последний индекс {len(self.flat_blocks)-1})")
        concl_block = self.flat_blocks[concl_idx]
        concl_text = self._get_flat_blocks_text(concl_block)
        parse_conclusion(concl_text, self.is_mag, self.messages)