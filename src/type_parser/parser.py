from itertools import groupby
from typing import Tuple

import fitz
from pymupdf import Document
from src.models.structured_document import *
from src.type_parser.utils import *

class ImprovedPdfParser:
    def collect_tables(self, doc: Document) -> list[list[TableInfo]]:
        all_pages: list[list[TableInfo]] = []
        for i, page in enumerate(doc):
            page_tables: list[TableInfo] = []
            for tab in page.find_tables():
                try:
                    header = tab.header
                    columns = []
                    ys = set()
                    for j in range(len(header.cells)):
                        x0, y0, x1, y1 = header.cells[j]
                        columns.append(ColumnInfo(x0, x1))
                    for row in tab.rows:
                        x0, y0, x1, y1 = row.bbox
                        ys.add(y0)
                        ys.add(y1)
                    page_tables.append(
                        TableInfo(
                            i,
                            columns,
                            sorted(ys)
                        )
                    )
                except TypeError:
                    pass
            all_pages.append(page_tables)
        return all_pages

    def collect_lines(self, pages: dict) -> list[LineBlock]:
        line_blocks: list[LineBlock] = []
        threshold = 2.5
        for page_num, page in enumerate(pages):
            blocks = []
            for block in page.get("blocks", []):
                if block.get("image"):
                    blocks.append(ImageBlock.from_image(block))
                    continue
                for line in block.get("lines", []):
                    blocks.extend(TextBlock.from_span(span) for span in line.get("spans", []) if span.get("text", "").strip())
            
            blocks.sort(key=lambda b: b.bbox.y0)
            grouped_blocks = []
            current_line = [blocks[0]]
            
            for i in range(1, len(blocks)):
                if abs(blocks[i].bbox.y0 - current_line[-1].bbox.y0) <= threshold:
                    current_line.append(blocks[i])
                else:
                    current_line.sort(key=lambda b: b.bbox.x0)
                    grouped_blocks.append(current_line)
                    current_line = [blocks[i]]
            
            current_line.sort(key=lambda b: b.bbox.x0)
            grouped_blocks.append(current_line)

            result = []
            for line in grouped_blocks:
                result.append(self.split_line_into_columns(LineBlock(page_num, line)))

            line_blocks.extend(result)
        return line_blocks

    def get_current_table(self, page: int, bbox: Bbox):
        top = bbox.y0
        bottom = bbox.y1
        for table in self.tables[page]:
            if table.horizontal_lines[0] <= (top + bottom) / 2 and table.horizontal_lines[-1] >= (top + bottom) / 2:
                return table
        
        width = self.pages[page]["width"]
        height = self.pages[page]["height"]
        return TableInfo(
            page,
            [ColumnInfo(0, width)],
            [0, height]
        )
    
    def split_line_into_columns(self, line: LineBlock) -> LineBlock:
        if get_line_type(line) == LineType.FIGURE:
            return line
        line.blocks = [b for b in line.blocks if hasattr(b, 'text')]
        bbox = line.bbox
        table = self.get_current_table(line.page, bbox)
        blocks_iter = iter(line.blocks)
        current_b = next(blocks_iter, None)
        blocks: list[TextBlock] = []

        default_style = line.blocks[0].style if line.blocks else Style()
        for col in table.columns:
            col_group = []

            while current_b and current_b.bbox.x1 <= col.left_border:
                current_b = next(blocks_iter, None)

            while current_b and current_b.bbox.x0 < col.right_border:
                col_group.append(current_b)
                current_b = next(blocks_iter, None)

            if col_group:
                text = " ".join(b.text.strip() for b in col_group)
                merged_style = get_dominant_style(col_group)
                new_bbox = Bbox(
                    x0=min(b.bbox.x0 for b in col_group),
                    y0=min(b.bbox.y0 for b in col_group),
                    x1=max(b.bbox.x1 for b in col_group),
                    y1=max(b.bbox.y1 for b in col_group)
                )
                blocks.append(TextBlock(new_bbox, text, merged_style))
            else:
                res_bbox = Bbox(col.left_border, col.right_border, line.bbox.y0, line.bbox.y1)
                blocks.append(TextBlock(res_bbox, "", default_style))

        return LineBlock(page=line.page, blocks=blocks)
    
    def get_heading_level(self, heading: ParagraphBlock, tol: float = 1.5):
        pstyle = heading.main_style
        for i, existing in enumerate(self.heading_styles):
            if existing.text_alignment == pstyle.text_alignment and existing.style == pstyle.style:
                indent_ok = pstyle.text_alignment == TextAllignment.CENTER or abs(existing.left_indent - pstyle.left_indent) <= tol
                spacing_ok = abs(existing.spacing - pstyle.spacing) <= tol
                
                if indent_ok and spacing_ok:
                    return i + 1
        self.heading_styles.append(pstyle)
        return len(self.heading_styles)
    
    def is_heading_candidate(self, paragraph: ParagraphBlock):
        text = paragraph.text
        if self.toc:
            if self.toc.entries.get(text.lower()):
                return True
            else:
                return False
        else:
            return False
    
    def get_paragraph_type(self, block: Block):
        if not isinstance(block, ParagraphBlock):
            return None
        if self.is_heading_candidate(block):
            return ParagraphType.HEADING
        if TOC_CAPTION_RE.match(block.text):
            return ParagraphType.TOC_CAPTION
        if TABLE_CAPTION_RE.match(block.text):
            return ParagraphType.TABLE_CAPTION
        if FIGURE_CAPTION_RE.match(block.text):
            return ParagraphType.FIGURE_CAPTION
        if TABLE_CONTINUATION_RE.match(block.text):
            return ParagraphType.TABLE_CONTINUATION_CAPTION
        return ParagraphType.NORMAL
    
    def inc(self):
        self.current_line += 1
    
    def __init__(self, doc: Document):
        self.tables = self.collect_tables(doc)
        self.pages = [page.get_text("dict", sort=True) for page in doc]
        self.line_blocks = self.collect_lines(self.pages)
        self.current_line = 0
        self.toc: TocBlock = None
        self.parse_func = {
            LineType.TEXT: self.parse_paragraph,
            LineType.TABLE: self.parse_table,
            LineType.FIGURE: self.parse_figure
        }
        self.paragraph_func = {
            ParagraphType.NORMAL: lambda x: x,
            ParagraphType.FIGURE_CAPTION: self.get_figure_caption,
            ParagraphType.TABLE_CAPTION: self.get_table_caption,
            ParagraphType.HEADING: self.parse_section,
            ParagraphType.TOC_CAPTION: self.parse_toc
        }
        self.heading_styles: list[ParagraphStyle] = []

    def get_figure_caption(self, paragraph: ParagraphBlock):
        match = FIGURE_CAPTION_RE.match(paragraph.text)
        if match:
            data = match.groupdict()
            return FigureCaption(
                title=data['title'].strip(),
                num=int(data['num']),
                figure_ref=None 
            )
        return None

    def get_table_caption(self, paragraph: ParagraphBlock) -> TableCaption:
        match = TABLE_CAPTION_RE.match(paragraph.text)
        if match:
            data = match.groupdict()
            return TableCaption(
                title=data['title'].strip(),
                num=int(data['num']),
                table_ref=None 
            )
        return None

    def parse_document(self):
        title = self.parse_title()
        subblocks = []

        while self.current_line < len(self.line_blocks):
            line_block = self.line_blocks[self.current_line]
            line_type = get_line_type(line_block)
            if (line_type == LineType.PAGE_NUMBER):
                self.inc()
                continue
            parsed_block = self.parse_func[line_type]()
            if isinstance(parsed_block, ParagraphBlock):
                paragraph_type = self.get_paragraph_type(parsed_block)
                parsed_block = self.paragraph_func[paragraph_type](parsed_block)
                if isinstance(parsed_block, TocBlock) and not self.toc:
                    self.toc = parsed_block
                    continue
            if parsed_block:
                subblocks.append(parsed_block)
        
        return DocumentBlock(
            title = title,
            toc = self.toc,
            subblocks = subblocks
        )


    def parse_title(self) -> TitleBlock:
        page = 0
        subblocks = []

        while page == 0:
            line_block = self.line_blocks[self.current_line]
            line_type = get_line_type(line_block)
            if (line_type == LineType.PAGE_NUMBER):
                self.inc()
                continue
            parsed_block = self.parse_func[line_type]()
            if parsed_block:
                subblocks.append(parsed_block)
            page = self.line_blocks[self.current_line].page

        return TitleBlock(
            subblocks
        )


    def parse_paragraph(self):
        paragraph_blocks = []
        page_width: float = None
        while self.current_line < len(self.line_blocks):
            line_block = self.line_blocks[self.current_line]
            if not page_width:
                page_width = self.pages[line_block.page]["width"]
            line_type = get_line_type(line_block)
            if (line_type == LineType.PAGE_NUMBER):
                self.inc()
                continue
            if (line_type != LineType.TEXT):
                break
            text_block = line_block.blocks[0]
            if not is_same_paragraph(paragraph_blocks, text_block):
                break
            paragraph_blocks.append(text_block)
            self.inc()
        
        return ParagraphBlock(paragraph_blocks, 0, page_width)


    def parse_table_row(self, table: TableInfo) -> TableRow:
        line_blocks: list[LineBlock] = []
        while self.current_line < len(self.line_blocks):
            line_block = self.line_blocks[self.current_line]
            line_type = get_line_type(line_block)
            if line_type != LineType.TABLE:
                break
            if line_blocks:
                prev = line_blocks[-1]
                if prev.page != line_block.page:
                    break
                prev_middle = (prev.bbox.y0 + prev.bbox.y1) / 2
                cur_middle = (line_block.bbox.y0 + line_block.bbox.y1) / 2
                if has_between(table.horizontal_lines, prev_middle, cur_middle):
                    break
            line_blocks.append(line_block)
            self.inc()
        
        return TableRow(
            line_blocks,
            table.columns
        )


    def parse_table(self):
        rows = []
        try: 
            while self.current_line < len(self.line_blocks):
                block_start = self.current_line
                line_block = self.line_blocks[self.current_line]
                line_type = get_line_type(line_block)
                table = self.get_current_table(line_block.page, line_block.bbox)
                if (line_type == LineType.PAGE_NUMBER):
                    self.inc()
                    continue
                if (line_type == LineType.TEXT):
                    paragraph = self.parse_paragraph()
                    paragraph_type = self.get_paragraph_type(paragraph)
                    if paragraph_type == ParagraphType.TABLE_CONTINUATION_CAPTION:
                        continue
                    self.current_line = block_start
                    break
                row = self.parse_table_row(table)
                if not row:
                    break
                rows.append(row)
        except IndexError:
            pass

        return TableBlock(
            rows = rows
        )


    def parse_section(self, title: ParagraphBlock) -> tuple[SectionBlock, ParagraphBlock]:
        level = self.get_heading_level(title)
        subblocks = []

        while self.current_line < len(self.line_blocks):
            block_start = self.current_line
            line_block = self.line_blocks[self.current_line]
            line_type = get_line_type(line_block)
            if (line_type == LineType.PAGE_NUMBER):
                self.inc()
                continue
            parsed_block = self.parse_func[line_type]()
            if isinstance(parsed_block, ParagraphBlock):
                paragraph_type = self.get_paragraph_type(parsed_block)
                if paragraph_type == ParagraphType.HEADING and self.get_heading_level(parsed_block) <= level:
                    self.current_line = block_start
                    break
                parsed_block = self.paragraph_func[paragraph_type](parsed_block)
            if parsed_block:
                subblocks.append(parsed_block)

        section = SectionBlock(
            title = title,
            level = level,
            subblocks = subblocks
        )
        if self.toc and self.toc.entries.get(title.text):
            self.toc.entries[title.text].block = section
        return section
    
    def parse_toc(self, paragraph) -> TocBlock:
        entries: dict[str, TocEntry] = dict()
        while self.current_line < len(self.line_blocks):
            block_start = self.current_line
            line_block = self.line_blocks[self.current_line]
            line_type = get_line_type(line_block)
            if (line_type == LineType.PAGE_NUMBER):
                self.inc()
                continue
            if line_type != LineType.TEXT:
                break
            paragraph = self.parse_paragraph()
            match = TOC_BLOCK_RE.match(paragraph.text)
            if match:
                title = match.group("title").strip()
                page_num = int(match.group("page"))
                entry = TocEntry(
                        title=title,
                        page=page_num       
                    )
                entries[title.lower()] = entry
            else:
                self.current_line = block_start
                break
        
        return TocBlock(entries)


    def parse_figure(self) -> FigureBlock:
        line_block = self.line_blocks[self.current_line]
        figure = line_block.blocks[0]
        self.inc()
        return FigureBlock(figure.image)