"""
docx_service/styles.py
────────────────────────────────────────────────────────────────
Enterprise Document Styling Engine.

Defines the complete visual identity for all generated Word
documents: color palette, typography, heading styles, table
styles, paragraph styles, and section numbering.

All colors use RGBColor from python-docx.
"""

from __future__ import annotations

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml


# ══════════════════════════════════════════════════════════════
#  COLOR PALETTE
# ══════════════════════════════════════════════════════════════

# Primary
NAVY        = RGBColor(0x1B, 0x2A, 0x4A)   # Deep navy — headings, cover
ACCENT_BLUE = RGBColor(0x2E, 0x86, 0xC1)   # Accent — links, borders
DARK_GRAY   = RGBColor(0x2C, 0x3E, 0x50)   # Body text
MID_GRAY    = RGBColor(0x7F, 0x8C, 0x8D)   # Secondary text
LIGHT_GRAY  = RGBColor(0xEC, 0xF0, 0xF1)   # Table alt rows, backgrounds
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)

# Table header
TABLE_HEADER_BG  = "1B2A4A"  # hex for XML shading
TABLE_ALT_ROW_BG = "F2F3F4"  # hex for XML shading

# Cover
COVER_ACCENT = RGBColor(0x2E, 0x86, 0xC1)

# Code block
CODE_BG = "EAECEE"
CODE_FG = RGBColor(0x1A, 0x1A, 0x2E)


# ══════════════════════════════════════════════════════════════
#  FONT NAMES
# ══════════════════════════════════════════════════════════════

FONT_HEADING = "Calibri Light"
FONT_BODY    = "Calibri"
FONT_CODE    = "Consolas"


# ══════════════════════════════════════════════════════════════
#  HEADING SIZES
# ══════════════════════════════════════════════════════════════

HEADING_SIZES = {
    1: Pt(24),
    2: Pt(18),
    3: Pt(14),
    4: Pt(12),
}


# ══════════════════════════════════════════════════════════════
#  APPLY STYLES TO DOCUMENT
# ══════════════════════════════════════════════════════════════

def apply_enterprise_styles(doc: Document) -> None:
    """
    Configure all styles on the given Document to match
    enterprise-grade formatting.
    """

    # ── Default font ──────────────────────────────────────────
    style = doc.styles["Normal"]
    font = style.font
    font.name = FONT_BODY
    font.size = Pt(11)
    font.color.rgb = DARK_GRAY

    pf = style.paragraph_format
    pf.space_after = Pt(6)
    pf.space_before = Pt(2)
    pf.line_spacing = 1.15

    # ── Heading 1 ─────────────────────────────────────────────
    _configure_heading(doc, 1, HEADING_SIZES[1], NAVY, space_before=Pt(24), space_after=Pt(12))

    # ── Heading 2 ─────────────────────────────────────────────
    _configure_heading(doc, 2, HEADING_SIZES[2], ACCENT_BLUE, space_before=Pt(18), space_after=Pt(8))

    # ── Heading 3 ─────────────────────────────────────────────
    _configure_heading(doc, 3, HEADING_SIZES[3], DARK_GRAY, space_before=Pt(12), space_after=Pt(6))

    # ── Heading 4 ─────────────────────────────────────────────
    _configure_heading(doc, 4, HEADING_SIZES[4], MID_GRAY, space_before=Pt(10), space_after=Pt(4))

    # ── Enterprise Bullet ─────────────────────────────────────
    if "EnterpriseBullet" not in [s.name for s in doc.styles]:
        from docx.enum.style import WD_STYLE_TYPE
        ent_bullet = doc.styles.add_style("EnterpriseBullet", WD_STYLE_TYPE.PARAGRAPH)
        
        # Inherit Word-native numbering from List Bullet
        if "List Bullet" in [s.name for s in doc.styles]:
            ent_bullet.base_style = doc.styles["List Bullet"]
            
        # Do NOT set ent_bullet.font.name! 
        # Setting the style font overwrites the bullet symbol font (e.g. Symbol/Wingdings) 
        # and turns standard bullets into square boxes (□).
        # We only configure spacing and indentation.
        
        pf = ent_bullet.paragraph_format
        pf.space_after = Pt(4)
        pf.space_before = Pt(2)
        pf.line_spacing = 1.15
        pf.left_indent = Inches(0.25)
        
    # ── Enterprise Number ─────────────────────────────────────
    if "EnterpriseNumber" not in [s.name for s in doc.styles]:
        ent_num = doc.styles.add_style("EnterpriseNumber", WD_STYLE_TYPE.PARAGRAPH)
        if "List Number" in [s.name for s in doc.styles]:
            ent_num.base_style = doc.styles["List Number"]
            
        pf = ent_num.paragraph_format
        pf.space_after = Pt(4)
        pf.space_before = Pt(2)
        pf.line_spacing = 1.15
        pf.left_indent = Inches(0.25)


def _configure_heading(
    doc: Document,
    level: int,
    size: Pt,
    color: RGBColor,
    space_before: Pt = Pt(12),
    space_after: Pt = Pt(6),
):
    """Configure a heading style."""
    style_name = f"Heading {level}"
    if style_name not in [s.name for s in doc.styles]:
        return

    style = doc.styles[style_name]
    font = style.font
    font.name = FONT_HEADING
    font.size = size
    font.color.rgb = color
    font.bold = True

    pf = style.paragraph_format
    pf.space_before = space_before
    pf.space_after = space_after
    
    if level == 2:
        pf.keep_with_next = False
        pf.page_break_before = False
    else:
        pf.keep_with_next = True
        

    # Ensure Word treats this as an outline level so the TOC sees it
    pPr = pf._element
    outlineLvl = pPr.find(qn('w:outlineLvl'))
    if outlineLvl is None:
        outlineLvl = parse_xml(f'<w:outlineLvl {nsdecls("w")} w:val="{level-1}"/>')
        pPr.append(outlineLvl)
    else:
        outlineLvl.set(qn('w:val'), str(level-1))


# ══════════════════════════════════════════════════════════════
#  TABLE STYLING HELPERS
# ══════════════════════════════════════════════════════════════

def style_table_header(row):
    """
    Apply enterprise header styling to a table row.
    Navy background, white bold text.
    """
    for cell in row.cells:
        # Background
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shading = parse_xml(
            f'<w:shd {nsdecls("w")} '
            f'w:fill="{TABLE_HEADER_BG}" w:val="clear"/>'
        )
        tcPr.append(shading)

        # Font
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in paragraph.runs:
                run.font.bold = True
                run.font.color.rgb = WHITE
                run.font.name = FONT_BODY
                run.font.size = Pt(10)


def style_table_alt_rows(table):
    """
    Apply alternating row shading to a table.
    Skips the header row (row 0).
    """
    for i, row in enumerate(table.rows):
        if i == 0:
            continue  # header already styled

        if i % 2 == 0:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                shading = parse_xml(
                    f'<w:shd {nsdecls("w")} '
                    f'w:fill="{TABLE_ALT_ROW_BG}" w:val="clear"/>'
                )
                tcPr.append(shading)

        # Style text
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = FONT_BODY
                    run.font.size = Pt(10)
                    run.font.color.rgb = DARK_GRAY


def style_table_borders(table):
    """
    Set clean, light borders on entire table.
    """
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else parse_xml(
        f'<w:tblPr {nsdecls("w")}/>'
    )

    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="BDC3C7"/>'
        f'  <w:left w:val="single" w:sz="4" w:space="0" w:color="BDC3C7"/>'
        f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="BDC3C7"/>'
        f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="BDC3C7"/>'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="BDC3C7"/>'
        f'  <w:insideV w:val="single" w:sz="4" w:space="0" w:color="BDC3C7"/>'
        f'</w:tblBorders>'
    )

    # Remove existing borders if any
    existing = tblPr.find(qn('w:tblBorders'))
    if existing is not None:
        tblPr.remove(existing)

    tblPr.append(borders)


def format_enterprise_table(table):
    """
    Apply complete enterprise styling to a table:
    header, alt rows, and borders.
    """
    if len(table.rows) == 0:
        return

    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    style_table_header(table.rows[0])
    style_table_alt_rows(table)
    style_table_borders(table)
