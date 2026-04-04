'''
import pytest

from src.models.raw_document import RawPDFDocument
from src.models.raw_document import TextBlock
from src.models.structured_document import StructuredDocument
from src.models.section import Section
from src.parsers.formatting_parser import FormattingParser


# ------------------------------------------------------------
# Фикстуры для создания тестовых данных
# ------------------------------------------------------------

@pytest.fixture
def sample_raw_doc():
    """Создаёт тестовый RawPDFDocument с координатами в пунктах (pt)."""
    page_width_pt = 595  # 210 мм
    page_height_pt = 842  # 297 мм
    blocks = [
        # Страница 1: основной текст
        TextBlock(
            text="Введение в научную работу",
            font_name="TimesNewRoman",
            font_size=14.0,
            bbox=(86, 700, 400, 720),  # x0,y0,x1,y1 в pt
            page_num=1
        ),
        TextBlock(
            text="Основной текст должен быть отформатирован правильно. " * 3,
            font_name="TimesNewRoman",
            font_size=13.0,
            bbox=(86, 600, 400, 620),
            page_num=1
        ),
        # Блок в верхнем колонтитуле (header)
        TextBlock(
            text="МИНИСТЕРСТВО НАУКИ",
            font_name="Arial",
            font_size=10.0,
            bbox=(86, 750, 400, 770),  # y0=750 > 0.86*842=715 -> header
            page_num=1
        ),
        # Страница 2: основной текст
        TextBlock(
            text="Продолжение текста на второй странице.",
            font_name="TimesNewRoman",
            font_size=12.0,
            bbox=(86, 500, 400, 520),
            page_num=2
        ),
        # Блок с номером страницы (footer)
        TextBlock(
            text="2",
            font_name="TimesNewRoman",
            font_size=11.0,
            bbox=(297, 50, 307, 65),  # y1=65 < 0.15*842=126 -> footer
            page_num=2
        ),
        # Страница 3: с неправильным шрифтом (основной текст)
        TextBlock(
            text="Этот текст набран Arial",
            font_name="Arial",
            font_size=13.0,
            bbox=(86, 400, 400, 420),
            page_num=3
        ),
        # Блок с номером страницы 3 (footer)
        TextBlock(
            text="3",
            font_name="TimesNewRoman",
            font_size=13.0,  # слишком большой для номера
            bbox=(297, 50, 307, 65),
            page_num=3
        ),
    ]
    metadata = {
        'page_dimensions': [(page_width_pt, page_height_pt)] * 3
    }
    return RawPDFDocument(pages=[1,2,3], blocks=blocks, metadata=metadata)

@pytest.fixture
def sample_structured_doc(sample_raw_doc):
    sections = [
        Section(title="Введение", start_page=1, end_page=1),  # document будет заполнен позже
        Section(title="Основная часть", start_page=2, end_page=3)
    ]
    doc = StructuredDocument(raw_document=sample_raw_doc, sections=sections)
    # Устанавливаем обратную ссылку
    for s in doc.sections:
        s.document = doc
    return doc

@pytest.fixture
def correct_raw_doc():
    """Документ, полностью соответствующий требованиям."""
    page_width_pt = 595
    page_height_pt = 842
    blocks = [
        # Страница 1: основной текст
        TextBlock(
            text="Введение в научную работу",
            font_name="TimesNewRoman",
            font_size=14.0,
            bbox=(86, 700, 400, 720),
            page_num=1
        ),
        TextBlock(
            text="Основной текст должен быть отформатирован правильно. " * 3,
            font_name="TimesNewRoman",
            font_size=13.0,
            bbox=(86, 600, 400, 620),
            page_num=1
        ),
        # Блок в верхнем колонтитуле (исключается)
        TextBlock(
            text="МИНИСТЕРСТВО НАУКИ",
            font_name="Arial",  # не будет проверяться
            font_size=10.0,
            bbox=(86, 750, 400, 770),
            page_num=1
        ),
        # Страница 2: основной текст
        TextBlock(
            text="Продолжение текста на второй странице.",
            font_name="TimesNewRoman",
            font_size=12.0,
            bbox=(86, 500, 400, 520),
            page_num=2
        ),
        # Блок с номером страницы (footer)
        TextBlock(
            text="2",
            font_name="TimesNewRoman",
            font_size=11.0,
            bbox=(297, 50, 307, 65),
            page_num=2
        ),
        # Страница 3: основной текст (без ошибок)
        TextBlock(
            text="Текст на третьей странице.",
            font_name="TimesNewRoman",
            font_size=13.0,
            bbox=(86, 400, 400, 420),
            page_num=3
        ),
        # Блок с номером страницы 3 (footer)
        TextBlock(
            text="3",
            font_name="TimesNewRoman",
            font_size=11.0,
            bbox=(297, 50, 307, 65),
            page_num=3
        ),
    ]
    metadata = {'page_dimensions': [(page_width_pt, page_height_pt)] * 3}
    return RawPDFDocument(pages=[1,2,3], blocks=blocks, metadata=metadata)

@pytest.fixture
def correct_structured_doc(correct_raw_doc):
    sections = [
        Section(title="Введение", start_page=1, end_page=1),
        Section(title="Основная часть", start_page=2, end_page=3)
    ]
    doc = StructuredDocument(raw_document=correct_raw_doc, sections=sections)
    for s in doc.sections:
        s.document = doc
    return doc

# ------------------------------------------------------------
# Тесты для FormattingParser
# ------------------------------------------------------------

class TestFormattingParser:

    def test_parser_creation(self):
        parser = FormattingParser()
        assert parser is not None

    def test_parse_document_all_correct(self, correct_structured_doc):
        """Документ полностью соответствует требованиям (без ошибок)."""
        parser = FormattingParser()
        config = {
            "font_name": "TimesNewRoman",
            "font_size_range": (12, 14),
            "margins_mm": {"top": 20, "bottom": 20, "left": 30, "right": 15},
            "check_page_numbers": True,
            "first_page_has_number": False,
            "page_number_position": "bottom_center",
            "page_number_font_size_range": (10, 12),
            "page_width_mm": 210,
            "page_height_mm": 297
        }
        # Используем весь документ (страницы 1-3)
        result = parser.parse(correct_structured_doc, config)
        assert len(result["errors"]) == 0
        # Предупреждений тоже быть не должно (кроме возможно номера на стр3 с большим размером – но это будет ошибка/предупреждение)
        # На странице 3 шрифт Arial – ошибка, так что ошибки будут.
        # Этот тест должен быть для документа без ошибок, поэтому создадим другой raw_doc.
        # Для простоты пропустим, тест будет ниже.

    def test_font_name_error(self, sample_structured_doc):
        """Обнаружение неправильного шрифта (Arial вместо TimesNewRoman)."""
        parser = FormattingParser()
        config = {
            "font_name": "TimesNewRoman",
            "font_size_range": (12, 14),
            "margins_mm": {"top": 20, "bottom": 20, "left": 30, "right": 15},
            "check_page_numbers": False,  # отключим для чистоты
        }
        result = parser.parse(sample_structured_doc, config)
        # Должна быть одна ошибка на странице 3 (блок с Arial)
        errors = result["errors"]
        assert len(errors) == 1
        assert errors[0]["page"] == 3
        assert "Arial" in errors[0]["message"]
        assert "TimesNewRoman" in errors[0]["message"]

    def test_font_size_error(self, sample_structured_doc):
        """Обнаружение неправильного размера шрифта (меньше 12 или больше 14)."""
        parser = FormattingParser()
        config = {
            "font_name": "TimesNewRoman",
            "font_size_range": (12, 14),
            "check_page_numbers": False,
        }
        # Модифицируем документ: добавим блок с размером 10 на странице 2
        sample_structured_doc.raw_document.blocks.append(
            TextBlock(text="Мелкий текст", font_name="TimesNewRoman", font_size=10.0,
                      bbox=(30, 300, 100, 320), page_num=2)
        )
        result = parser.parse(sample_structured_doc, config)
        # Ошибки: на странице 3 шрифт Arial (размер 13 – в норме, но шрифт не тот – уже ошибка)
        # и дополнительный блок с размером 10. Итого 2 ошибки.
        errors = result["errors"]
        # Одна ошибка из-за шрифта Arial (страница 3) + одна из-за размера 10 (страница 2) = 2
        assert len(errors) == 2
        # Проверим, что есть сообщение о размере 10
        size_error = any("10" in e["message"] for e in errors)
        assert size_error

    def test_margins_error(self, sample_structured_doc):
        """Проверка выхода текста за поля."""
        parser = FormattingParser()
        config = {
            "font_name": "TimesNewRoman",  # чтобы не мешали другие проверки
            "font_size_range": (12, 14),
            "margins_mm": {"top": 50, "bottom": 50, "left": 50, "right": 50},
            "page_width_mm": 210,
            "page_height_mm": 297,
            "check_page_numbers": False,
        }
        result = parser.parse(sample_structured_doc, config)
        # Проверим, что есть ошибки выхода за левое поле (x0=30 < 50) и за верхнее (y1=720 > 297-50=247)
        # В блоках страницы 1: x0=30 (меньше 50) – левое поле, y1=720 (больше 247) – верхнее.
        # На странице 1 также блок колонтитула (y1=770) – тоже выход за верхнее.
        # В общем, должно быть несколько ошибок. Упростим: проверим, что есть хотя бы одна ошибка о левом поле.
        errors = result["errors"]
        left_margin_errors = [e for e in errors if "левое поле" in e["message"]]
        assert len(left_margin_errors) > 0

    def test_page_number_missing(self, sample_structured_doc):
        """Отсутствие номера страницы (удалим блок с номером на стр2)."""
        parser = FormattingParser()
        # Удалим блок с номером страницы 2
        sample_structured_doc.raw_document.blocks = [
            b for b in sample_structured_doc.raw_document.blocks if not (b.page_num == 2 and b.text == "2")
        ]
        config = {
            "check_page_numbers": True,
            "first_page_has_number": False,
            "page_number_position": "bottom_center",
            "page_number_font_size_range": (10, 12),
            "page_height_mm": 297,
            "page_width_mm": 210,
        }
        result = parser.parse(sample_structured_doc, config)
        # Должна быть ошибка об отсутствии номера на странице 2 (и, возможно, на стр3? на стр3 есть номер "3")
        # first_page_has_number=False – страница 1 не проверяется.
        errors = result["errors"]
        assert any("Отсутствует номер страницы" in e["message"] and e["page"] == 2 for e in errors)

    def test_page_number_position_warning(self, sample_structured_doc):
        """Номер страницы расположен не по центру (сдвинем блок)."""
        parser = FormattingParser()
        # Изменим координаты блока с номером на стр2, чтобы он был не по центру
        for b in sample_structured_doc.raw_document.blocks:
            if b.page_num == 2 and b.text == "2":
                b.bbox = (10, 50, 20, 65)  # x центр ~15, далеко от центра 105
        config = {
            "check_page_numbers": True,
            "first_page_has_number": False,
            "page_number_position": "bottom_center",
            "page_number_font_size_range": (10, 12),
            "page_height_mm": 297,
            "page_width_mm": 210,
        }
        result = parser.parse(sample_structured_doc, config)
        # Должно быть предупреждение о расположении на странице 2
        warnings = result["warnings"]
        assert any("расположен не по центру" in w["message"] and w["page"] == 2 for w in warnings)

    def test_page_number_font_size_warning(self, sample_structured_doc):
        """Размер шрифта номера страницы вне допустимого диапазона."""
        parser = FormattingParser()
        config = {
            "check_page_numbers": True,
            "first_page_has_number": False,
            "page_number_position": "bottom_center",
            "page_number_font_size_range": (10, 12),
            "page_height_mm": 297,
            "page_width_mm": 210,
        }
        # На странице 3 размер номера 13 – он вызовет предупреждение
        result = parser.parse(sample_structured_doc, config)
        warnings = result["warnings"]
        # Также может быть ошибка шрифта на странице 3 (Arial), но мы её не проверяем здесь.
        # Найдём предупреждение о размере номера
        font_size_warnings = [w for w in warnings if "Размер шрифта номера страницы" in w["message"]]
        assert len(font_size_warnings) >= 1
        assert font_size_warnings[0]["page"] == 3

    def test_parse_section_only(self, sample_structured_doc):
        """Проверка, что парсер обрабатывает только страницы указанного раздела."""
        parser = FormattingParser()
        # Возьмём раздел "Введение" (страница 1)
        section = sample_structured_doc.sections[0]
        config = {
            "font_name": "TimesNewRoman",
            "font_size_range": (12, 14),
            "check_page_numbers": False,
        }
        result = parser.parse(section, config)
        # На странице 1 все блоки с правильным шрифтом, ошибок быть не должно
        assert len(result["errors"]) == 0

        # Теперь раздел "Основная часть" (страницы 2-3) – на странице 3 есть ошибка шрифта
        section2 = sample_structured_doc.sections[1]
        result2 = parser.parse(section2, config)
        errors = result2["errors"]
        assert len(errors) == 1
        assert errors[0]["page"] == 3

    def test_footer_exclusion(self, sample_structured_doc):
        """Проверка, что блоки в колонтитулах не проверяются на основной шрифт."""
        parser = FormattingParser()
        config = {
            "font_name": "TimesNewRoman",
            "font_size_range": (12, 14),
            "check_page_numbers": False,
        }
        result = parser.parse(sample_structured_doc, config)
        # На странице 1 есть блок колонтитула с Arial, но он должен быть исключён (is_footer_or_header)
        # Поэтому ошибка только на странице 3 (основной текст Arial)
        errors = result["errors"]
        # Убедимся, что нет ошибки от колонтитула
        footer_errors = [e for e in errors if e["page"] == 1 and "Arial" in e["message"]]
        assert len(footer_errors) == 0

    # Можно добавить тест для проверки абзацного отступа, но он пока заглушка.
    
'''