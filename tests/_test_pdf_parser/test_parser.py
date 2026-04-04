'''
import sys
import os
CWD = os.getcwd()
sys.path.insert(0, CWD)

import json
import pytest
import base64
from src.pdf_parser.parser import PDFParser

write_mode = False

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('utf-8')
        return json.JSONEncoder.default(self, obj)

def test_parse_pdfs():
    parser = PDFParser()
    input_dir = os.path.join(CWD, "tests/PDFs")
    output_dir = os.path.join(CWD, "tests/raw_docs")
    
    # Собираем все PDF-файлы во входной директории
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    if write_mode:
        # ----- РЕЖИМ ЗАПИСИ ЭТАЛОНОВ -----
        for pdf_file in pdf_files:
            input_path = os.path.join(input_dir, pdf_file)
            doc = parser.parse(input_path)
            
            # Формируем имя выходного JSON-файла
            output_filename = os.path.splitext(pdf_file)[0] + ".json"
            output_path = os.path.join(output_dir, output_filename)
            
            # Создаём папку outputs, если её нет
            os.makedirs(output_dir, exist_ok=True)
            
            # Записываем результат с кастомным кодировщиком
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(doc, f, cls=CustomJSONEncoder, ensure_ascii=False, indent=2)
        
        # Принудительно падаем, чтобы явно указать, что тест работал в режиме записи
        assert False, "Тест запущен в режиме ЗАПИСИ эталонов. Файлы записаны в outputs. Переключитесь в режим проверки."
    
    else:
        # ----- РЕЖИМ ПРОВЕРКИ -----
        errors = []
        
        for pdf_file in pdf_files:
            print('testing', pdf_file)
            input_path = os.path.join(input_dir, pdf_file)
            output_filename = os.path.splitext(pdf_file)[0] + ".json"
            output_path = os.path.join(output_dir, output_filename)
            
            # Проверяем, существует ли эталонный JSON
            if not os.path.exists(output_path):
                errors.append(f"Ожидаемый файл {output_path} не найден. Возможно, нужно запустить режим записи.")
                continue
            
            # Парсим PDF
            doc = parser.parse(input_path)
            
            # Загружаем эталонный JSON
            with open(output_path, 'r', encoding='utf-8') as f:
                expected = json.load(f)
            
            # Рекурсивно преобразуем bytes в base64-строки для сравнения с эталоном
            def convert_bytes(obj):
                if isinstance(obj, bytes):
                    return base64.b64encode(obj).decode('utf-8')
                elif isinstance(obj, dict):
                    return {k: convert_bytes(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_bytes(item) for item in obj]
                else:
                    return obj
            
            converted = convert_bytes(doc)
            
            # Сравниваем
            if json.dumps(converted) != json.dumps(expected):
                errors.append(f"Несовпадение для {pdf_file}")
                # Запишим в файл разницу
                output_filename_converted = os.path.splitext(pdf_file)[0] + "_converted.json"
                output_path_converted = os.path.join(os.path.join(CWD, "tests/test_pdf_parser"), output_filename_converted)
                output_filename_expected = os.path.splitext(pdf_file)[0] + "_expected.json"
                output_path_expected = os.path.join(os.path.join(CWD, "tests/test_pdf_parser"), output_filename_expected)
                with open(output_path_converted, 'w', encoding='utf-8') as f:
                    json.dump(converted, f, cls=CustomJSONEncoder, ensure_ascii=False, indent=2)
                with open(output_path_expected, 'w', encoding='utf-8') as f:
                    json.dump(expected, f, cls=CustomJSONEncoder, ensure_ascii=False, indent=2)
        assert not errors, "\n".join(errors)
'''