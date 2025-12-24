#!/usr/bin/env python3
"""Convert patent markdown documents to PDF for USPTO filing."""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

# CSS for professional patent document formatting
PATENT_CSS = """
@page {
    size: letter;
    margin: 1in;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 10pt;
        font-family: 'Times New Roman', Times, serif;
    }
}

body {
    font-family: 'Times New Roman', Times, serif;
    font-size: 12pt;
    line-height: 1.5;
    color: #000;
}

h1 {
    font-size: 16pt;
    font-weight: bold;
    text-align: center;
    margin-top: 24pt;
    margin-bottom: 12pt;
    page-break-after: avoid;
}

h2 {
    font-size: 14pt;
    font-weight: bold;
    margin-top: 18pt;
    margin-bottom: 10pt;
    page-break-after: avoid;
}

h3 {
    font-size: 12pt;
    font-weight: bold;
    margin-top: 14pt;
    margin-bottom: 8pt;
    page-break-after: avoid;
}

p {
    text-align: justify;
    margin-bottom: 10pt;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
    font-size: 11pt;
}

th, td {
    border: 1px solid #000;
    padding: 6pt 8pt;
    text-align: left;
}

th {
    background-color: #f0f0f0;
    font-weight: bold;
}

code, pre {
    font-family: 'Courier New', Courier, monospace;
    font-size: 10pt;
    background-color: #f5f5f5;
    padding: 2pt 4pt;
}

pre {
    padding: 10pt;
    margin: 12pt 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    border: 1px solid #ddd;
    page-break-inside: avoid;
}

hr {
    border: none;
    border-top: 1px solid #000;
    margin: 18pt 0;
}

ul, ol {
    margin-left: 20pt;
    margin-bottom: 10pt;
}

li {
    margin-bottom: 4pt;
}

.claim {
    margin-left: 0.5in;
    text-indent: -0.5in;
}

/* Page break controls */
h1, h2 {
    page-break-after: avoid;
}

pre, table, figure {
    page-break-inside: avoid;
}
"""

def convert_md_to_pdf(input_path: str, output_path: str):
    """Convert a markdown file to PDF."""
    # Read markdown content
    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert markdown to HTML
    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'toc']
    )

    # Wrap in full HTML document
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Patent Document</title>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # Convert to PDF
    HTML(string=full_html).write_pdf(
        output_path,
        stylesheets=[CSS(string=PATENT_CSS)]
    )
    print(f"Created: {output_path}")

def main():
    patent_dir = Path(__file__).parent

    # Convert main specification
    convert_md_to_pdf(
        patent_dir / "PROVISIONAL_PATENT_SPECIFICATION.md",
        patent_dir / "PROVISIONAL_PATENT_SPECIFICATION.pdf"
    )

    # Convert figures
    convert_md_to_pdf(
        patent_dir / "FIGURES.md",
        patent_dir / "FIGURES.pdf"
    )

    # Also convert invention disclosure (for records)
    convert_md_to_pdf(
        patent_dir / "INVENTION_DISCLOSURE.md",
        patent_dir / "INVENTION_DISCLOSURE.pdf"
    )

    # Convert filing guide (for reference)
    convert_md_to_pdf(
        patent_dir / "USPTO_FILING_GUIDE.md",
        patent_dir / "USPTO_FILING_GUIDE.pdf"
    )

    print("\n✅ All PDFs created successfully!")
    print("\nFiles for USPTO submission:")
    print("  1. PROVISIONAL_PATENT_SPECIFICATION.pdf (main document)")
    print("  2. FIGURES.pdf (drawings)")

if __name__ == "__main__":
    main()
