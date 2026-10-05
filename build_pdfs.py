"""
Generates beautiful, professional PDF documents from the 3 Showcase Assessment markdown files
using reportlab.
"""

import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, Preformatted
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(46, letter[1] - 32, "GST Reconciliation Tool | Candidate Showcase Assessment")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(46, letter[1] - 36, letter[0] - 46, letter[1] - 36)

        # Footer (all pages)
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 46, 28, footer_text)
        self.drawString(46, 28, "Confidential — For 20-Minute Interview & Showcase Assessment")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(46, 38, letter[0] - 46, 38)

        self.restoreState()


def get_custom_styles():
    styles = getSampleStyleSheet()
    
    # Custom color palette
    c_primary = colors.HexColor("#0f172a")     # Slate 900
    c_emerald = colors.HexColor("#059669")     # Emerald 600
    c_dark_green = colors.HexColor("#065f46")  # Emerald 800
    c_text = colors.HexColor("#1e293b")        # Slate 800
    c_muted = colors.HexColor("#64748b")       # Slate 500

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=c_primary,
        spaceAfter=4
    )

    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=14.5,
        textColor=c_dark_green,
        spaceBefore=10,
        spaceAfter=3,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=c_primary,
        spaceBefore=7,
        spaceAfter=2,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'DocH3',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=c_primary,
        spaceBefore=5,
        spaceAfter=2,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.0,
        leading=10.5,
        textColor=c_text,
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.0,
        leading=10.5,
        textColor=c_text,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2
    )

    callout_style = ParagraphStyle(
        'DocCallout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.0,
        leading=10.5,
        textColor=c_dark_green
    )

    code_style = ParagraphStyle(
        'DocCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.8,
        leading=8.5,
        textColor=colors.HexColor("#0f172a")
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        textColor=c_text
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=c_primary
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=colors.white
    )

    return {
        'title': title_style,
        'h1': h1_style,
        'h2': h2_style,
        'h3': h3_style,
        'body': body_style,
        'bullet': bullet_style,
        'callout': callout_style,
        'code': code_style,
        'table_cell': table_cell_style,
        'table_cell_bold': table_cell_bold,
        'table_header': table_header_style
    }


def parse_markdown_to_flowables(md_text: str, styles: dict):
    lines = md_text.splitlines()
    flowables = []
    
    i = 0
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []

    def flush_table():
        nonlocal table_lines, in_table
        if not table_lines:
            return
        
        # Parse table lines
        rows = []
        for line in table_lines:
            if re.match(r'^\s*\|?\s*:?-+:?\s*\|', line):
                # separator line
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            rows.append(cells)
        
        if rows:
            table_data = []
            num_cols = max(len(r) for r in rows)
            
            for row_idx, r in enumerate(rows):
                row_cells = []
                # pad cells if needed
                while len(r) < num_cols:
                    r.append("")
                
                is_header = (row_idx == 0)
                for c in r:
                    # Clean markdown bold/code tags
                    c_clean = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c)
                    c_clean = re.sub(r'`(.*?)`', r'<font face="Courier">\1</font>', c_clean)
                    c_clean = c_clean.replace("₹", "Rs. ")
                    
                    if is_header:
                        p = Paragraph(c_clean, styles['table_header'])
                    elif row_idx % 2 == 1:
                        p = Paragraph(c_clean, styles['table_cell_bold'] if c.startswith('**') else styles['table_cell'])
                    else:
                        p = Paragraph(c_clean, styles['table_cell_bold'] if c.startswith('**') else styles['table_cell'])
                    row_cells.append(p)
                table_data.append(row_cells)

            # Available width = 8.5 * 72 - 2 * 46 = 520 pt
            avail_width = 520.0
            col_width = avail_width / num_cols
            col_widths = [col_width] * num_cols

            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#065f46")),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ]))
            flowables.append(Spacer(1, 3))
            flowables.append(t)
            flowables.append(Spacer(1, 4))

        table_lines = []
        in_table = False

    def flush_code():
        nonlocal code_lines, in_code_block
        if not code_lines:
            return
        code_text = "\n".join(code_lines).replace("₹", "Rs. ")
        
        # Render code box as a single-cell table with background
        p_code = Preformatted(code_text, styles['code'])
        code_table = Table([[p_code]], colWidths=[520])
        code_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        flowables.append(Spacer(1, 3))
        flowables.append(code_table)
        flowables.append(Spacer(1, 4))
        code_lines = []
        in_code_block = False

    while i < len(lines):
        line = lines[i]

        # Handle code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                flush_code()
            else:
                if in_table:
                    flush_table()
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Handle tables
        if line.strip().startswith("|") and line.strip().endswith("|"):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            i += 1
            continue
        elif in_table:
            flush_table()

        # Handle horizontal rule
        if line.strip() in ("---", "***", "___"):
            flowables.append(Spacer(1, 2))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5, spaceBefore=3))
            i += 1
            continue

        # Handle blockquotes
        if line.strip().startswith(">"):
            quote_text = line.strip().lstrip("> ").strip()
            # collect multiline quote
            while i + 1 < len(lines) and lines[i+1].strip().startswith(">"):
                i += 1
                quote_text += " " + lines[i].strip().lstrip("> ").strip()
            
            quote_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', quote_text)
            quote_text = quote_text.replace("₹", "Rs. ")
            p = Paragraph(quote_text, styles['callout'])
            q_table = Table([[p]], colWidths=[520])
            q_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ecfdf5")),
                ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor("#059669")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#d1fae5")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            flowables.append(Spacer(1, 3))
            flowables.append(q_table)
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Clean markdown formatting helpers
        formatted_line = line.strip()
        formatted_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', formatted_line)
        formatted_line = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted_line)
        formatted_line = re.sub(r'`(.*?)`', r'<font face="Courier" color="#0f172a">\1</font>', formatted_line)
        formatted_line = formatted_line.replace("& ", "&amp; ")
        formatted_line = formatted_line.replace("₹", "Rs. ")
        formatted_line = formatted_line.replace("→", "-&gt;")
        formatted_line = formatted_line.replace("←", "&lt;-")

        # Headings
        if line.startswith("# "):
            flowables.append(Paragraph(formatted_line.lstrip("# "), styles['title']))
        elif line.startswith("## "):
            flowables.append(Paragraph(formatted_line.lstrip("# "), styles['h1']))
        elif line.startswith("### "):
            flowables.append(Paragraph(formatted_line.lstrip("# "), styles['h2']))
        elif line.startswith("#### "):
            flowables.append(Paragraph(formatted_line.lstrip("# "), styles['h3']))
        elif line.strip().startswith("- ") or line.strip().startswith("* "):
            bullet_text = "&bull; " + formatted_line.lstrip("-* ").strip()
            flowables.append(Paragraph(bullet_text, styles['bullet']))
        elif re.match(r'^\d+\.\s', line.strip()):
            match = re.match(r'^(\d+\.)\s*(.*)$', line.strip())
            num_label = match.group(1)
            num_text = f"<b>{num_label}</b> " + formatted_line[len(num_label):].strip()
            flowables.append(Paragraph(num_text, styles['bullet']))
        else:
            flowables.append(Paragraph(formatted_line, styles['body']))

        i += 1

    if in_table:
        flush_table()
    if in_code_block:
        flush_code()

    return flowables


def build_pdf_from_md(md_path: str, pdf_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=46,
        rightMargin=46,
        topMargin=46,
        bottomMargin=46
    )

    styles = get_custom_styles()
    flowables = parse_markdown_to_flowables(md_content, styles)
    doc.build(flowables, canvasmaker=NumberedCanvas)
    print(f"Successfully generated: {pdf_path}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tasks = [
        ("Task_A_Solution_I_Built.md", "Task_A_Solution_I_Built.pdf"),
        ("Task_B_Solution_Scoping.md", "Task_B_Solution_Scoping.pdf"),
        ("Task_C_Fix_or_Failure.md", "Task_C_Fix_or_Failure.pdf"),
    ]

    for md_file, pdf_file in tasks:
        md_p = os.path.join(base_dir, md_file)
        pdf_p = os.path.join(base_dir, pdf_file)
        if os.path.exists(md_p):
            build_pdf_from_md(md_p, pdf_p)
        else:
            print(f"File not found: {md_p}")
