import fitz  # PyMuPDF


def extract_text(pdf_path: str) -> str:
    """Extract all text content from a PDF file."""
    doc = fitz.open(pdf_path)
    text_parts = []
    for page_num, page in enumerate(doc, 1):
        page_text = page.get_text()
        if page_text.strip():
            text_parts.append(f"[Page {page_num}]\n{page_text.strip()}")
    doc.close()
    return "\n\n".join(text_parts)
