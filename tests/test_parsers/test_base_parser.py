import sys
import os
CWD = os.getcwd()
sys.path.insert(0, CWD)
import fitz
import json
import pytest
import base64
from src.type_parser.parser import ImprovedPdfParser
from src.parsers_matcher.matcher import ParsersMatcher
from src.parsers.base_parser import DocumentStructureValidator
from src.models.message import *

write_mode = False

def test_parse_pdfs():
    input_dir = os.path.join(CWD, "tests/PDFs")
    output_dir = os.path.join(CWD, "tests/messages_doc")
    
    # Собираем все PDF-файлы во входной директории
    json_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    if write_mode:
        # ----- РЕЖИМ ЗАПИСИ ЭТАЛОНОВ -----
        for json_file in json_files:
            input_path = os.path.join(input_dir, json_file)

            collector = MessageCollector()
            result = ImprovedPdfParser(fitz.open(input_path)).parse_document();
            matcher = ParsersMatcher(result)
            sections = matcher.match(collector)
            DocumentStructureValidator(sections, collector).validate()
            

            # Формируем имя выходного JSON-файла
            output_filename = os.path.splitext(json_file)[0] + ".json"
            output_path = os.path.join(output_dir, output_filename)

            os.makedirs(output_dir, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(collector, f, default=result.universal_serializer, ensure_ascii=False, indent=2)

        assert False, "Тест запущен в режиме ЗАПИСИ эталонов. Файлы записаны. Переключитесь в режим проверки."
    
    else:
        # ----- РЕЖИМ ПРОВЕРКИ -----
        errors = []

        for json_file in json_files:
            print('testing', json_file)
            input_path = os.path.join(input_dir, json_file)
            output_filename = os.path.splitext(json_file)[0] + ".json"
            output_path = os.path.join(output_dir, output_filename)

            if not os.path.exists(output_path):
                errors.append(f"Ожидаемый файл {output_path} не найден. Возможно, нужно запустить режим записи.")
                continue

            # Парсим
            collector = MessageCollector()
            result = ImprovedPdfParser(fitz.open(input_path)).parse_document();
            matcher = ParsersMatcher(result)
            sections = matcher.match(collector)
            DocumentStructureValidator(sections, collector).validate()

            # Загружаем эталон
            with open(output_path, 'r', encoding='utf-8') as f:
                expected = json.load(f)

            converted = collector

            # Сравниваем
            if json.dumps(converted, default=result.universal_serializer, sort_keys=True, ensure_ascii=False, indent=2) != json.dumps(expected, sort_keys=True, ensure_ascii=False, indent=2):
                errors.append(f"Несовпадение для {json_file}")
                # Для отладки сохраняем полученный результат и эталон в отдельную папку
                debug_dir = os.path.join(CWD, "tests/test_parser")
                os.makedirs(debug_dir, exist_ok=True)

                output_converted = os.path.join(debug_dir, os.path.splitext(json_file)[0] + "_converted.json")
                output_expected = os.path.join(debug_dir, os.path.splitext(json_file)[0] + "_expected.json")

                with open(output_converted, 'w', encoding='utf-8') as f:
                    json.dump(converted, f, default=result.universal_serializer, ensure_ascii=False, indent=2)
                with open(output_expected, 'w', encoding='utf-8') as f:
                    json.dump(expected, f, default=result.universal_serializer, ensure_ascii=False, indent=2)

        assert not errors, "\n".join(errors)