"""Text extraction from soil test reports: embedded PDF text first, Tesseract OCR as fallback."""
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import get_settings

MIN_TEXT_CHARS = 40


def _ocr_image_bytes(data: bytes, suffix: str) -> str:
    cmd = get_settings().tesseract_cmd
    if not shutil.which(cmd):
        raise RuntimeError("Tesseract OCR is not installed on the server")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"page{suffix}"
        src.write_bytes(data)
        proc = subprocess.run([cmd, str(src), "stdout", "--psm", "6"], capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"OCR failed: {proc.stderr.decode(errors='ignore')[:200]}")
        return proc.stdout.decode("utf-8", errors="ignore")


def extract_text(data: bytes, content_type: str) -> tuple[str, str]:
    """Return (text, method) where method is 'pdf_text' or 'ocr'."""
    if content_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
        if len(text.strip()) >= MIN_TEXT_CHARS:
            return text, "pdf_text"
        # Scanned PDF: render pages and OCR them.
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        parts = []
        for i in range(min(len(pdf), 5)):
            img = pdf[i].render(scale=2.5).to_pil()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            parts.append(_ocr_image_bytes(buf.getvalue(), ".png"))
        return "\n".join(parts), "ocr"
    suffix = ".png" if content_type == "image/png" else ".jpg"
    return _ocr_image_bytes(data, suffix), "ocr"
