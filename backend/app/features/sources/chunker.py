# Markdown generator + smart chunker.
# Converts loaded documents to markdown, then splits into chunks
# that respect page boundaries and preserve tables as atomic units.


from app.core.config import settings
import re
from typing import List, Dict

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

PAGE_MARKER_RE = re.compile(
    r"<!--\s*page:(\d+)\s*-->",
    re.IGNORECASE,
)

MIN_CHUNK_SIZE = settings.MIN_CHUNK_SIZE

TABLE_ROW_RE = re.compile(r"^\s*\|.*\|.*$")
TABLE_DIVIDER_RE = re.compile(r"^\s*\|?[\s\-:]+\|[\s\-:|]+\|?\s*$")


def normalize_text(text: str) -> str:
    """Clean extracted text."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # collapse excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def generate_markdown(
    docs: List[Document],
    file_name: str,
) -> str:
    """
    Convert LangChain docs into markdown with page markers.
    """

    parts = []

    for doc in docs:
        text = normalize_text(doc.page_content)

        if not text:
            continue

        page_num = doc.metadata.get("page_number", 1)

        parts.append(
            f"<!-- page:{page_num} -->\n\n{text}"
        )

    return "\n\n---\n\n".join(parts)


def smart_chunk(
    markdown_text: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> List[Dict]:

    markdown_text = normalize_text(markdown_text)

    if not markdown_text:
        return []

    chunks: List[Dict] = []

    matches = PAGE_MARKER_RE.findall(markdown_text)

    # Website / YouTube / Notes
    if not matches:
        _chunk_section(
            text=markdown_text,
            page_number=1,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            result=chunks,
        )

    # PDF / DOCX with page markers
    else:
        segments = PAGE_MARKER_RE.split(markdown_text)

        if segments and segments[0].strip():
            _chunk_section(
                segments[0],
                1,
                chunk_size,
                chunk_overlap,
                chunks,
            )

        i = 1

        while i < len(segments) - 1:
            page_number = int(segments[i])

            content = segments[i + 1]

            if content.strip():
                _chunk_section(
                    content,
                    page_number,
                    chunk_size,
                    chunk_overlap,
                    chunks,
                )

            i += 2

    # Final cleanup
    filtered = []

    for chunk in chunks:
        text = chunk["text"].strip()

        if len(text) < MIN_CHUNK_SIZE:
            continue

        filtered.append(chunk)

    return filtered


def _chunk_section(
    text: str,
    page_number: int,
    chunk_size: int,
    chunk_overlap: int,
    result: list,
):
    """
    Split one section while preserving tables.
    """

    lines = text.split("\n")

    prose_buf = []
    table_buf = []

    in_table = False

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n# ",
            "\n## ",
            "\n### ",
            "\n#### ",
            "\n\n",
            "\n",
            ". ",
            "? ",
            "! ",
            "; ",
            ": ",
            " ",
        ],
    )

    def flush_prose():
        if not prose_buf:
            return

        prose_text = "\n".join(prose_buf).strip()

        prose_buf.clear()

        if not prose_text:
            return

        split_chunks = splitter.split_text(prose_text)

        for chunk_text in split_chunks:

            chunk_text = chunk_text.strip()

            if len(chunk_text) < MIN_CHUNK_SIZE:
                continue

            result.append(
                {
                    "text": chunk_text,
                    "page_number": page_number,
                    "is_table": False,
                }
            )

    def flush_table():
        if not table_buf:
            return

        table_text = "\n".join(table_buf).strip()

        table_buf.clear()

        if len(table_text) < MIN_CHUNK_SIZE:
            return

        result.append(
            {
                "text": table_text,
                "page_number": page_number,
                "is_table": True,
            }
        )

    for line in lines:

        is_table = (
            TABLE_ROW_RE.match(line)
            or TABLE_DIVIDER_RE.match(line)
        )

        if is_table:

            if not in_table:
                flush_prose()
                in_table = True

            table_buf.append(line)

        else:

            if in_table:
                flush_table()
                in_table = False

            prose_buf.append(line)

    if in_table:
        flush_table()
    else:
        flush_prose()