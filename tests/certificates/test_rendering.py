from io import BytesIO
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas as rl_canvas

from app.services.certificates.rendering import render_certificate, wrap_image_as_pdf


def _make_blank_pdf(tmp_path: Path, width: float = 600, height: float = 400, pages: int = 1) -> Path:
    path = tmp_path / "template.pdf"
    canvas = rl_canvas.Canvas(str(path), pagesize=(width, height))
    for _ in range(pages):
        canvas.showPage()
    canvas.save()
    return path


class TestWrapImageAsPdf:
    def test_produces_single_page_pdf_sized_to_image(self):
        image = Image.new("RGB", (200, 100), color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")

        pdf_bytes = wrap_image_as_pdf(buffer.getvalue())

        reader = PdfReader(BytesIO(pdf_bytes))
        assert len(reader.pages) == 1
        page = reader.pages[0]
        assert round(float(page.mediabox.width)) == 200
        assert round(float(page.mediabox.height)) == 100


class TestRenderCertificate:
    def test_draws_field_values_onto_the_template(self, tmp_path):
        template_path = _make_blank_pdf(tmp_path)
        fields = [
            {"key": "full_name_short", "page": 0, "x": 50, "y": 300, "font_size": 20},
            {"key": "score", "page": 0, "x": 50, "y": 250, "font_size": 20},
        ]
        values = {"full_name_short": "Петров П. П.", "score": "84.5"}

        result = render_certificate(template_path, fields, values)

        reader = PdfReader(BytesIO(result))
        text = reader.pages[0].extract_text()
        assert "Петров П. П." in text
        assert "84.5" in text

    def test_skips_fields_with_no_value(self, tmp_path):
        template_path = _make_blank_pdf(tmp_path)
        fields = [{"key": "missing_field", "page": 0, "x": 50, "y": 300}]

        # Should not raise even though "missing_field" has no matching value.
        result = render_certificate(template_path, fields, {})
        assert len(PdfReader(BytesIO(result)).pages) == 1

    def test_long_value_shrinks_font_to_fit(self, tmp_path):
        template_path = _make_blank_pdf(tmp_path)
        long_name = "Оченьдлинноеимяоченьдлиннаяфамилияоченьдлинноеотчество" * 3
        fields = [{"key": "full_name_short", "page": 0, "x": 10, "y": 300, "font_size": 40}]

        # Should not raise despite the text being far wider than the page at font_size=40.
        result = render_certificate(template_path, fields, {"full_name_short": long_name}, max_field_width=400)
        reader = PdfReader(BytesIO(result))
        assert long_name in reader.pages[0].extract_text().replace("\n", "")

    def test_only_targets_the_correct_page(self, tmp_path):
        template_path = _make_blank_pdf(tmp_path, pages=2)
        fields = [{"key": "score", "page": 1, "x": 50, "y": 200, "font_size": 20}]

        result = render_certificate(template_path, fields, {"score": "100"})

        reader = PdfReader(BytesIO(result))
        assert "100" not in reader.pages[0].extract_text()
        assert "100" in reader.pages[1].extract_text()

    def test_renders_signature_image(self, tmp_path):
        template_path = _make_blank_pdf(tmp_path)
        signature_path = tmp_path / "sig.png"
        Image.new("RGB", (100, 50), color="black").save(signature_path)

        result = render_certificate(
            template_path,
            fields=[],
            field_values={},
            signature_path=signature_path,
            signature_position={"page": 0, "x": 10, "y": 10, "width": 100, "height": 50},
        )

        reader = PdfReader(BytesIO(result))
        assert len(reader.pages) == 1
        # A rendered image isn't extractable as text; just confirm the page has
        # image xobjects now (the overlay was actually merged in).
        resources = reader.pages[0].get("/Resources")
        assert resources is not None
