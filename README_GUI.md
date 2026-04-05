# PDF Report Validator — десктоп-приложение

## Быстрый старт (готовый бинарник)

Скачайте последний релиз со [страницы Releases](https://github.com/DimaThenekov/pdf_report_validator/releases):

- **macOS** → `PDFReportValidator-macOS.zip` — распаковать, двойной клик по `PDFReportValidator`
- **Windows** → `PDFReportValidator-Windows.zip` — распаковать, двойной клик по `PDFReportValidator.exe`

Установка не нужна. Один файл — всё работает.

## Как пользоваться

1. Перетащите PDF-файлы в зону drag&drop (или нажмите «📂 Добавить файлы»)
2. Нажмите «▶ Проверить»
3. Справа появятся результаты: оценка (если есть) и список замечаний по каждому файлу

## Разработка (запуск из исходников)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 app/main.py
```

## Локальная сборка в бинарник

```bash
pip install pyinstaller
pyinstaller PDFReportValidator.spec --clean
./dist/PDFReportValidator           # Windows: dist\PDFReportValidator.exe
```

## Автоматическая сборка (GitHub Actions)

При создании тега вида `v1.0.0` автоматически запускается CI:
- Собираются бинарники для macOS и Windows
- Публикуются в GitHub Release

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Структура

- `app/main.py` — точка входа
- `app/gui.py` — UI на PyQt6 (drag&drop, отображение результатов)
- `PDFReportValidator.spec` — конфигурация pyinstaller
- `.github/workflows/release.yml` — CI/CD для сборки релизов
