import os
import sys
import re
import traceback
from typing import List, Optional

# Чтобы импорты проекта работали (dev и pyinstaller)
if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
else:
    _base = os.getcwd()
sys.path.insert(0, _base)

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt
import fitz

from src.models.message import MessageCollector
from src.type_parser.parser import ImprovedPdfParser
from src.parsers_matcher.matcher import ParsersMatcher
from src.parsers.base_parser import DocumentStructureValidator

# Regex для извлечения оценки из текста сообщения
GRADE_RE = re.compile(r'основная часть оценена на (\d)')


# --- Модель списка файлов ---

class FileListModel(QtCore.QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._files: List[str] = []

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return os.path.basename(self._files[index.row()])

    def rowCount(self, index=None):
        return len(self._files)

    def add_files(self, files: List[str]):
        new = [f for f in files if f not in self._files]
        if not new:
            return
        start = len(self._files)
        self.beginInsertRows(QtCore.QModelIndex(), start, start + len(new) - 1)
        self._files.extend(new)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self._files = []
        self.endResetModel()

    def files(self) -> List[str]:
        return list(self._files)


# --- Зона drag-and-drop с подсказкой ---

class DropZone(QtWidgets.QLabel):
    """Область с подсказкой для перетаскивания PDF."""
    files_dropped = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(80)
        self._set_idle()

    def _set_idle(self):
        self.setText('📄 Перетащите PDF-файлы сюда')
        self.setStyleSheet(
            'QLabel { border: 2px dashed #aaa; border-radius: 8px;'
            ' color: #888; font-size: 14px; padding: 16px; }')

    def _set_hover(self):
        self.setStyleSheet(
            'QLabel { border: 2px dashed #4a90d9; border-radius: 8px;'
            ' background: #eef4ff; color: #4a90d9; font-size: 14px; padding: 16px; }')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hover()

    def dragLeaveEvent(self, event):
        self._set_idle()

    def dropEvent(self, event):
        self._set_idle()
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith('.pdf'):
                files.append(path)
        if files:
            self.files_dropped.emit(files)


# --- Вспомогательные функции ---

def extract_grade(collector: MessageCollector) -> Optional[str]:
    """Ищет сообщение с оценкой, возвращает '3'/'4'/'5' или None."""
    for msg in collector.get_all_messages():
        m = GRADE_RE.search(msg.text)
        if m:
            return m.group(1)
    return None


def format_messages(collector: MessageCollector) -> List[str]:
    """Возвращает только текст замечаний (без строки про оценку)."""
    lines = []
    for msg in collector.get_all_messages():
        if GRADE_RE.search(msg.text):
            continue  # оценка выводится отдельно
        lines.append(msg.text)
    return lines


def run_pipeline(path: str) -> tuple:
    """
    Запускает пайплайн для одного PDF.
    Возвращает (оценка, is_mag, список_замечаний, текст_ошибки_или_None).
    """
    try:
        collector = MessageCollector()
        doc = fitz.open(path)
        result = ImprovedPdfParser(doc).parse_document()
        matcher = ParsersMatcher(result)
        sections = matcher.match(collector)
        is_mag = matcher.ismag
        DocumentStructureValidator(sections, collector).validate()
        return extract_grade(collector), is_mag, format_messages(collector), None
    except Exception:
        return None, None, [], traceback.format_exc()


# --- Главное окно ---

class PdfCheckerWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PDF Report Validator')
        self.resize(960, 620)

        # --- Левая панель ---
        self.drop_zone = DropZone()
        self.add_btn = QtWidgets.QPushButton('📂 Добавить файлы')
        self.check_btn = QtWidgets.QPushButton('▶ Проверить')
        self.clear_btn = QtWidgets.QPushButton('🗑 Очистить')

        self.list_view = QtWidgets.QListView()
        self.model = FileListModel()
        self.list_view.setModel(self.model)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.check_btn)
        btn_row.addWidget(self.clear_btn)

        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.drop_zone)
        left.addLayout(btn_row)
        left.addWidget(self.list_view, 1)

        # --- Правая панель: результаты ---
        self.result_area = QtWidgets.QTextEdit()
        self.result_area.setReadOnly(True)

        main = QtWidgets.QHBoxLayout(self)
        main.addLayout(left, 2)
        main.addWidget(self.result_area, 3)

        # --- Сигналы ---
        self.drop_zone.files_dropped.connect(self.model.add_files)
        self.add_btn.clicked.connect(self.on_add)
        self.check_btn.clicked.connect(self.on_check)
        self.clear_btn.clicked.connect(self.on_clear)

        # --- Минимальный стиль ---
        self.setStyleSheet('''
            QPushButton {
                padding: 6px 14px; border-radius: 4px;
                border: 1px solid #ccc; background: #f7f7f7;
            }
            QPushButton:hover { background: #e8e8e8; }
            QListView { border: 1px solid #ddd; border-radius: 4px; }
            QTextEdit  { border: 1px solid #ddd; border-radius: 4px; }
        ''')

    # --- Обработчики ---

    def on_add(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, 'Выбрать PDF', filter='PDF (*.pdf)')
        pdfs = [p for p in paths if p.lower().endswith('.pdf')]
        if pdfs:
            self.model.add_files(pdfs)

    def on_clear(self):
        self.model.clear()
        self.result_area.clear()

    def on_check(self):
        files = self.model.files()
        if not files:
            self.result_area.setHtml(
                '<p style="color:#888">Добавьте PDF-файлы для проверки</p>')
            return

        self.result_area.clear()
        html_parts = []

        for f in files:
            name = os.path.basename(f)
            grade, is_mag, messages, error = run_pipeline(f)

            part = f'<h3 style="margin-bottom:4px">{name}</h3>'

            if error:
                # Файл не удалось обработать — не падаем
                part += ('<p style="color:#c0392b">⚠ Не удалось обработать файл</p>'
                         f'<pre style="font-size:11px;color:#999">{error[:300]}</pre>')
            else:
                # Тип работы
                if is_mag is not None:
                    work_type = 'Магистратура' if is_mag else 'Бакалавриат'
                    badge_color = '#8e44ad' if is_mag else '#2980b9'
                    part += (f'<span style="background:{badge_color};color:#fff;'
                             f'padding:2px 8px;border-radius:4px;font-size:12px">'
                             f'{work_type}</span> ')

                # Оценка (если есть)
                if grade:
                    color = {'5': '#27ae60', '4': '#f39c12', '3': '#c0392b'}.get(grade, '#333')
                    part += f'<p style="font-size:18px"><b style="color:{color}">Оценка: {grade}</b></p>'

                # Замечания (только текст, без типа)
                if messages:
                    part += '<ul style="margin:4px 0">'
                    for m in messages:
                        part += f'<li>{m}</li>'
                    part += '</ul>'
                else:
                    part += '<p style="color:#27ae60">✔ Замечаний нет</p>'

            part += '<hr>'
            html_parts.append(part)

        self.result_area.setHtml(''.join(html_parts))
