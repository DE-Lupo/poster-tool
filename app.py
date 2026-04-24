from flask import Flask, render_template, request, send_file
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import io
import math

app = Flask(__name__)

SHEET_MAP = {
    "A4": 1,
    "A3": 4,
    "A2": 8,
    "A1": 16,
}


@app.route("/")
def index():
    return render_template("index.html")


def compute_grid(n):
    cols = int(math.sqrt(n))
    rows = math.ceil(n / cols)
    return cols, rows


@app.route("/create-pdf", methods=["POST"])
def create_pdf():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    fmt = request.form.get("format", "A4").upper()

    if fmt not in SHEET_MAP:
        return "Format ungültig", 400

    sheets = SHEET_MAP[fmt]

    # Bild laden
    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    # 🔥 WICHTIG: stark verkleinern für Render
    img.thumbnail((1500, 1500))

    cols, rows = compute_grid(sheets)

    img_w, img_h = img.size
    tile_w = img_w // cols
    tile_h = img_h // rows

    page_w, page_h = A4

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for r in range(rows):
        for c_idx in range(cols):

            left = c_idx * tile_w
            top = r * tile_h
            right = left + tile_w
            bottom = top + tile_h

            tile = img.crop((left, top, right, bottom))

            c.drawImage(
                ImageReader(tile),
                0,
                0,
                width=page_w,
                height=page_h
            )

            c.showPage()

    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"poster_{fmt}.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run()
