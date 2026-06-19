"""
docx_service/markdown_parser.py
────────────────────────────────────────────────────────────────
Markdown → Structured Blocks Parser.

Parses LLM-generated markdown into structured content blocks
that the DOCX builder can consume. Handles:
  - Headings (H1–H4)
  - Paragraphs with **bold** and *italic* inline formatting
  - Bullet lists and numbered lists
  - Markdown tables
  - Mermaid code blocks → extracted for rendering
  - Regular code blocks → monospace formatting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class BlockType(Enum):
    HEADING         = "heading"
    PARAGRAPH       = "paragraph"
    TABLE           = "table"
    BULLET_LIST     = "bullet_list"
    NUMBERED_LIST   = "numbered_list"
    MERMAID_DIAGRAM = "mermaid_diagram"
    CODE_BLOCK      = "code_block"
    HORIZONTAL_RULE = "horizontal_rule"


@dataclass
class ContentBlock:
    block_type: BlockType
    text: str = ""

    # Heading
    level: int = 0                          # 1–4

    # Table
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)

    # List
    items: List[str] = field(default_factory=list)

    # Code / Mermaid
    language: str = ""
    code: str = ""


# ══════════════════════════════════════════════════════════════
#  INLINE FORMATTING
# ══════════════════════════════════════════════════════════════

@dataclass
class InlineSegment:
    """A segment of text with formatting."""
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False


def parse_inline(text: str) -> List[InlineSegment]:
    """
    Parse inline formatting: **bold**, *italic*, `code`.

    Returns a list of InlineSegment objects.
    """
    segments: List[InlineSegment] = []

    # Pattern: bold, italic, inline code (order matters)
    pattern = re.compile(
        r'(\*\*(.+?)\*\*)'     # **bold**
        r'|(\*(.+?)\*)'        # *italic*
        r'|(`(.+?)`)'          # `code`
    )

    pos = 0
    for match in pattern.finditer(text):
        # Add text before match
        if match.start() > pos:
            plain = text[pos:match.start()]
            if plain:
                segments.append(InlineSegment(text=plain))

        if match.group(2):  # bold
            segments.append(InlineSegment(text=match.group(2), bold=True))
        elif match.group(4):  # italic
            segments.append(InlineSegment(text=match.group(4), italic=True))
        elif match.group(6):  # code
            segments.append(InlineSegment(text=match.group(6), code=True))

        pos = match.end()

    # Remaining text
    if pos < len(text):
        remaining = text[pos:]
        if remaining:
            segments.append(InlineSegment(text=remaining))

    # If no formatting found, return the whole text
    if not segments:
        segments.append(InlineSegment(text=text))

    return segments


# ══════════════════════════════════════════════════════════════
#  TABLE PARSER
# ══════════════════════════════════════════════════════════════

def _parse_table_row(line: str) -> List[str]:
    """Parse a markdown table row into cells."""
    # Strip leading/trailing pipes
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]

    return [cell.strip() for cell in line.split("|")]


def _is_separator_row(line: str) -> bool:
    """Check if a line is a table separator (|---|---|)."""
    cleaned = line.strip().replace("|", "").replace("-", "").replace(":", "").strip()
    return len(cleaned) == 0 and "-" in line


# ══════════════════════════════════════════════════════════════
#  MAIN PARSER
# ══════════════════════════════════════════════════════════════

def parse_markdown(text: str) -> List[ContentBlock]:
    """
    Parse markdown text into a list of ContentBlock objects.

    Handles headings, paragraphs, tables, lists, code blocks,
    and mermaid diagrams.
    """
    blocks: List[ContentBlock] = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── Empty line ────────────────────────────────────────
        if not stripped:
            i += 1
            continue

        # ── Horizontal rule ───────────────────────────────────
        if re.match(r'^[-*_]{3,}$', stripped):
            blocks.append(ContentBlock(
                block_type=BlockType.HORIZONTAL_RULE,
            ))
            i += 1
            continue

        # ── Code block (``` or ~~~) ───────────────────────────
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            language = stripped[3:].strip().lower()
            code_lines = []
            i += 1

            while i < len(lines):
                if lines[i].strip().startswith(fence):
                    i += 1
                    break
                code_lines.append(lines[i])
                i += 1

            code_text = "\n".join(code_lines)

            if language == "mermaid":
                blocks.append(ContentBlock(
                    block_type=BlockType.MERMAID_DIAGRAM,
                    code=code_text,
                    language="mermaid",
                ))
            else:
                blocks.append(ContentBlock(
                    block_type=BlockType.CODE_BLOCK,
                    code=code_text,
                    language=language or "text",
                ))
            continue

        # ── Heading ───────────────────────────────────────────
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text_content = heading_match.group(2).strip()
            blocks.append(ContentBlock(
                block_type=BlockType.HEADING,
                text=text_content,
                level=level,
            ))
            i += 1
            continue

        # ── Table ─────────────────────────────────────────────
        if "|" in stripped and not stripped.startswith("```"):
            table_lines = []
            while i < len(lines) and "|" in lines[i].strip():
                table_lines.append(lines[i].strip())
                i += 1

            if len(table_lines) >= 2:
                # Find header and separator
                headers = _parse_table_row(table_lines[0])

                data_start = 1
                if len(table_lines) > 1 and _is_separator_row(table_lines[1]):
                    data_start = 2

                rows = []
                for tl in table_lines[data_start:]:
                    if not _is_separator_row(tl):
                        rows.append(_parse_table_row(tl))

                blocks.append(ContentBlock(
                    block_type=BlockType.TABLE,
                    headers=headers,
                    rows=rows,
                ))
            else:
                # Single line with pipes — treat as paragraph
                blocks.append(ContentBlock(
                    block_type=BlockType.PARAGRAPH,
                    text=stripped,
                ))
            continue

        # ── Bullet list ───────────────────────────────────────
        if re.match(r'^[-*+]\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^\s*[-*+]\s+', lines[i]):
                item_text = re.sub(r'^\s*[-*+]\s+', '', lines[i]).strip()
                items.append(item_text)
                i += 1

            blocks.append(ContentBlock(
                block_type=BlockType.BULLET_LIST,
                items=items,
            ))
            continue

        # ── Numbered list ─────────────────────────────────────
        if re.match(r'^\d+\.\s+', stripped):
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i]).strip()
                items.append(item_text)
                i += 1

            blocks.append(ContentBlock(
                block_type=BlockType.NUMBERED_LIST,
                items=items,
            ))
            continue

        # ── Paragraph (default) ───────────────────────────────
        para_lines = []
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].strip().startswith("#")
            and not lines[i].strip().startswith("```")
            and not lines[i].strip().startswith("---")
            and not re.match(r'^\s*[-*+]\s+', lines[i])
            and not re.match(r'^\s*\d+\.\s+', lines[i])
            and not ("|" in lines[i] and lines[i].strip().startswith("|"))
        ):
            para_lines.append(lines[i].strip())
            i += 1

        if para_lines:
            blocks.append(ContentBlock(
                block_type=BlockType.PARAGRAPH,
                text=" ".join(para_lines),
            ))

    return blocks
