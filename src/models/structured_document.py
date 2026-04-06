import base64
from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import Enum
import json
import re
import unicodedata

@dataclass
class ColumnInfo:
    left_border: float
    right_border: float

@dataclass
class TableInfo:
    page: int
    columns: list[ColumnInfo]
    horizontal_lines: list[float]

@dataclass
class Bbox:
    x0: float
    x1: float
    y0: float
    y1: float

@dataclass(frozen=True)
class Style:
    font: str
    size: float
    color: int

    def __eq__(self, other):
        return (
            self.font == other.font and
            self.size == other.size and
            self.color == other.color
        )

@dataclass
class AnchorBlock:
    bbox: Bbox

@dataclass
class TextBlock(AnchorBlock):
    text: str
    style: Style

    @classmethod
    def from_span(cls, span: dict):
        x0, y0, x1, y1 = span["bbox"]
        bbox = Bbox(x0, x1, y0, y1)
        style = Style(
            font=span.get("font", ""),
            size=span.get("size", 0.0),
            color=span.get("color", 0),
        )
        text = span.get("text", "")
        text = clean_invisible_chars(text)
        return cls(bbox, text, style)

    def empty(self):
        return not self.text.strip()
    
    def compute_left_indent(self, left_border):
        return self.bbox.x0 - left_border
    
    def compute_right_indent(self, right_border):
        return right_border - self.bbox.x1


@dataclass
class ImageBlock(AnchorBlock):
    image: str
    @classmethod
    def from_image(cls, block: dict):
        bbox = block["bbox"]
        new_bbox = Bbox(bbox[0], bbox[2], bbox[1], bbox[3])
        image = block.get("image")
        image_str = base64.b64encode(image).decode('ascii')
        return cls(new_bbox, image_str)

@dataclass
class LineBlock(AnchorBlock):
    blocks: list[AnchorBlock]
    page: int
    def __init__(self, page, blocks: list[AnchorBlock]):
        self.blocks = blocks
        self.page = page
        y1 = max(b.bbox.y1 for b in blocks)
        first_block = blocks[0]
        last_block = blocks[-1]
        self.bbox = Bbox(first_block.bbox.x0, last_block.bbox.x1, first_block.bbox.y0, y1)
    def text(self):
        return "".join(block.text.strip() for block in self.blocks if hasattr(block, 'text')) 

#==================================================================================#

class Block:
    pass

class TextAllignment(Enum):
    LEFT = 1
    CENTER = 2
    RIGHT = 3
    WIDTH = 4

@dataclass
class ParagraphStyle:
    style: Style
    left_indent: float
    text_alignment: TextAllignment
    spacing: float

@dataclass
class ParagraphBlock(Block):
    main_style: ParagraphStyle = None
    text: str = None
    def __init__(self, lines: list[TextBlock], left_border: float, right_border: float):
        spacing = 0.0

        # Определяем полный текст абзаца
        lines_text: str = ""
        for line in lines:
            text = clean_invisible_chars(line.text)
            if not text:
                continue
            if lines_text.endswith(("-", "\xad")):
                lines_text = lines_text[:-1] + text
            else:
                lines_text += (" " if lines_text else "") + text

        self.text = lines_text

        # Определяем отступ первой строки
        if lines:
            first_line = lines[0]
            left_indent = max(0.0, first_line.bbox.x0 - left_border)

        # Определяем выравнивание
        text_allignment = detect_alignment(lines, left_border, right_border)

        # Вычисляем междустрочный интервал
        if len(lines) >= 2:
            ys = sorted(lb.bbox.y0 for lb in lines)
            diffs = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
            if diffs:
                spacing = sum(diffs) / len(diffs)

        # Определяем основной стиль абзаца
        style = get_dominant_style(lines)
        
        self.main_style = ParagraphStyle(
            style,
            left_indent,
            text_allignment,
            spacing
        )

@dataclass
class TableCell:
    subblocks: list[Block]
    def __init__(self, column: list[TextBlock], column_info: ColumnInfo):
        self.subblocks = []
        paragraphs = split_column_to_paragraphs(column)
        for paragraph in paragraphs:
            p = ParagraphBlock(
                paragraph,
                column_info.left_border,
                column_info.right_border
            )
            self.subblocks.append(p)

@dataclass
class TableRow:
    cells: list[TableCell]
    def __init__(self, lines: list[LineBlock], column_info: list[ColumnInfo]):
        columns = group_columns(lines)
        self.cells = [TableCell(column, column_info[i]) for i, column in enumerate(columns)]

@dataclass
class TableBlock(Block):
    rows: list[TableRow]

@dataclass
class SectionBlock(Block):
    title: ParagraphBlock
    level: int
    subblocks: list[Block]

@dataclass
class TocEntry:
    title: str
    page: int
    block_ref: SectionBlock = None

@dataclass
class TocBlock(Block):
    entries: dict[str, TocEntry]

@dataclass
class FigureBlock(Block):
    image: str

@dataclass
class TitleBlock(Block):
    subblocks: list[Block]

@dataclass
class DocumentBlock:
    title: TitleBlock
    toc: TocBlock
    subblocks: list[Block]
    @staticmethod
    def universal_serializer(obj):
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj):
            return {
                f.name: getattr(obj, f.name) 
                for f in fields(obj) 
                if not f.name.endswith('_ref')
            }
        return str(obj)
        
    def json_serialize(self):
        return json.dumps(
            self,
            default=self.universal_serializer,
            ensure_ascii=False, 
            indent=4
        )

#==================================================================================#

@dataclass
class TableCaption:
    title: str
    num: int
    table_ref: TableBlock = None 

@dataclass
class FigureCaption:
    title: str
    num: int
    figure_ref: FigureBlock = None  

#==================================================================================#

def get_dominant_style(blocks: list[TextBlock]) -> Style:
    if not blocks:
        return Style()
    style_weights = {}
    for b in blocks:
        weight = len(b.text)
        style_weights[b.style] = style_weights.get(b.style, 0) + weight
    return max(style_weights, key=style_weights.get)

def split_column_to_paragraphs(column: list[TextBlock]) -> list[list[TextBlock]]:
    result = []
    blocks_iter = iter(tb for tb in column if not tb.empty())
    first_tb = next(blocks_iter, None)
    if first_tb is None:
        return []

    current_paragraph = [first_tb]

    for tb in blocks_iter:
        if is_same_paragraph(current_paragraph, tb):
            current_paragraph.append(tb)
        else:
            result.append(current_paragraph)
            current_paragraph = [tb]

    result.append(current_paragraph)
    return result

def group_columns(line_blocks: list[LineBlock]) -> list[list[TextBlock]]:
    if not line_blocks:
        return []
    n_cols = len(line_blocks[0].blocks)
    cols = [[] for _ in range(n_cols)]
    for lb in line_blocks:
        for i, tb in enumerate(lb.blocks):
            cols[i].append(tb)
    return cols

def detect_alignment(
    lines: list[TextBlock],
    left_border: float,
    right_border: float,
    tol: float = 25,
) -> TextAllignment:
    if not lines:
        return TextAllignment.LEFT

    def all_almost_equal(vals: list[float]) -> bool:
        if len(vals) <= 1:
            return True
        base = vals[0]
        return all(abs(v - base) <= tol for v in vals[1:])

    lefts_all = [ln.compute_left_indent(left_border) for ln in lines]
    rights_all = [ln.compute_right_indent(right_border) for ln in lines]

    if len(lines) >= 2:
        body_left = lines[1:]              
        body_right = lines[:-1]            

        lefts_body = [ln.compute_left_indent(left_border) for ln in body_left]
        rights_body = [ln.compute_right_indent(right_border) for ln in body_right]

        left_equal = all_almost_equal(lefts_body)
        right_equal = all_almost_equal(rights_body)

        if left_equal and right_equal:
            return TextAllignment.WIDTH
        else:
            if left_equal:
                return TextAllignment.LEFT
            else:
                if right_equal:
                    return TextAllignment.RIGHT
    else:
        left_indent = lefts_all[0]
        right_indent = rights_all[0]

        if 2 * left_indent < right_indent:
            return TextAllignment.LEFT
        if 2 * right_indent < left_indent:
            return TextAllignment.RIGHT
        if left_indent > tol:
            return TextAllignment.CENTER
        else:
            return TextAllignment.WIDTH
        
    page_center = (left_border + right_border) / 2.0
    centers = []
    for l, r in zip(lefts_all, rights_all):
        line_left = left_border + l
        line_right = right_border - r
        centers.append((line_left + line_right) / 2.0)

    if all(abs(c - page_center) / (right_border - left_border) * 100 <= tol for c in centers):
        return TextAllignment.CENTER

    return TextAllignment.WIDTH


def is_list_start(text: str) -> bool:
    if not text:
        return False
    s = text.lstrip()
    list_pattern = r'^(' \
               r'\d+([\.\)]|(\.\d+)+\.?)|' \
               r'[a-zA-Zа-яА-Я][\.\)]|' \
               r'[\u2022\u2023\u25E6\u2043\u2219\u25CB\u25CF\u25A0\u25AA\-—\*]' \
               r')\s+'
    
    return bool(re.match(list_pattern, s))


def is_same_paragraph(prev_tbs: list[TextBlock], cur_tb: TextBlock, x_tol: float = 0.8, tol: float = 90.0):
    
    if not prev_tbs:
        return True
    last_tb = prev_tbs[-1]
    if last_tb.style != cur_tb.style:
        return False
    
    last_text = last_tb.text.strip()
    cur_text = cur_tb.text.strip()

    if is_list_start(cur_text):
        return False
    
    if cur_text and (cur_text[0].islower() or last_text.endswith("-")):
        return True
    
    body_for_left = prev_tbs[1:]
    body_for_right = prev_tbs[:-1]

    if not body_for_left:
        if re.search(r"\.\s*[\.\s]*\d+\s*$", last_text):
            return False
        if is_list_start(last_text):
            return cur_tb.bbox.x0 - last_tb.bbox.x0 > x_tol
        if cur_tb.bbox.x0 < last_tb.bbox.x0 - x_tol:
            if last_text.endswith("."):
                return False
            return True
        return False
    
    p_x0 = min(tb.bbox.x0 for tb in body_for_left)
    p_x1 = max(tb.bbox.x1 for tb in body_for_right)
    avg_left = sum(tb.bbox.x0 for tb in body_for_left) / len(body_for_left)
    avg_right = sum(tb.bbox.x1 for tb in body_for_right) / len(body_for_right)

    if abs(cur_tb.bbox.x0 - p_x0) >= x_tol:
        return False
    
    is_last_incomplete = (last_tb.bbox.x1 - last_tb.bbox.x0) / (avg_right - avg_left) * 100 <= tol

    return not is_last_incomplete

def clean_invisible_chars(text):
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] not in ['C'] or ch == '\xad')
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text
