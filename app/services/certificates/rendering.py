"""
Renders a filled certificate PDF: an admin-uploaded template (or a wrapped
image, see wrap_image_as_pdf) with text/signature fields drawn on top at the
positions the admissions committee placed them at (via the — future —
drag-and-drop editor; this module only consumes the resulting coordinates).

Long values (PV-A-1 flagged long names as an open question) are handled by
shrinking the font until the text fits within `max_field_width`, down to
MIN_FONT_SIZE, rather than truncating or overflowing the layout.
"""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

MIN_FONT_SIZE = 8

# The base-14 PDF fonts (Helvetica etc.) only cover WinAnsi/Latin glyphs, so
# Cyrillic text (student names, dates, ...) would render as boxes. DejaVu Sans
# is a free, permissively-licensed font with full Cyrillic coverage, vendored
# here so certificate rendering doesn't depend on fonts being present on the
# host it runs on.
DEFAULT_FONT = "DejaVuSans"
_FONT_PATH = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
if DEFAULT_FONT not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(DEFAULT_FONT, str(_FONT_PATH)))


def wrap_image_as_pdf(image_bytes: bytes) -> bytes:
    """Wrap an uploaded image (PNG/JPG) template into a single-page PDF sized
    to the image, so rendering only ever has to deal with PDF templates."""
    image = ImageReader(BytesIO(image_bytes))
    width, height = image.getSize()
    buffer = BytesIO()
    canvas = rl_canvas.Canvas(buffer, pagesize=(width, height))
    canvas.drawImage(image, 0, 0, width=width, height=height)
    canvas.save()
    return buffer.getvalue()


def _fit_font_size(
    canvas: rl_canvas.Canvas,
    text: str,
    max_width: float,
    base_size: float,
    font_name: str = DEFAULT_FONT,
    min_size: float = MIN_FONT_SIZE,
) -> float:
    size = base_size
    while size > min_size and canvas.stringWidth(text, font_name, size) > max_width:
        size -= 1
    return size


def render_certificate(
    template_path: Path | str,
    fields: list[dict],
    field_values: dict[str, str],
    signature_path: Path | str | None = None,
    signature_position: dict | None = None,
    max_field_width: float = 400.0,
) -> bytes:
    """
    `fields`: [{"key", "page" (default 0), "x", "y", "font_size" (default 24)}]
    `field_values`: {key: rendered string} — keys with no matching field (or no
    value) are silently skipped, so a template need not define every field.
    `signature_position`: {"page", "x", "y", "width", "height"}.
    """
    reader = PdfReader(str(template_path))
    writer = PdfWriter(clone_from=reader)

    fields_by_page: dict[int, list[dict]] = {}
    for field in fields:
        fields_by_page.setdefault(field.get("page", 0), []).append(field)

    for page_index, page in enumerate(writer.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        overlay_buffer = BytesIO()
        canvas = rl_canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        drew_anything = False

        for field in fields_by_page.get(page_index, []):
            value = field_values.get(field.get("key", ""))
            if not value:
                continue
            font_size = _fit_font_size(canvas, value, max_field_width, field.get("font_size", 24))
            canvas.setFont(DEFAULT_FONT, font_size)
            canvas.drawString(field["x"], field["y"], value)
            drew_anything = True

        if (
            signature_path is not None
            and signature_position is not None
            and signature_position.get("page", 0) == page_index
        ):
            canvas.drawImage(
                str(signature_path),
                signature_position["x"],
                signature_position["y"],
                width=signature_position.get("width", 150),
                height=signature_position.get("height", 60),
                mask="auto",
            )
            drew_anything = True

        canvas.save()
        if drew_anything:
            overlay_buffer.seek(0)
            overlay_page = PdfReader(overlay_buffer).pages[0]
            page.merge_page(overlay_page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
