from flask import Flask, render_template, request, send_file
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import io
import math

app = Flask(__name__)

# Anzahl A4-Seiten pro Format
SHEET_MAP = {
    "A4": 1,
    "A3": 4,
    "A2": 8,
    "A1": 16,
}


@app.route("/")
def index():
    return render_template("index.html")


def compute_grid(num_sheets, image_ratio):
    candidates = []

    for cols in range(1, num_sheets + 1):
        if num_sheets % cols == 0:
            rows = num_sheets // cols
            grid_ratio = cols / rows
            score = abs(math.log((grid_ratio + 0.0001) / (image_ratio + 0.0001)))
            candidates.append((score, cols, rows))

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1], candidates[0][2]


def fit_image(image_width, image_height, target_width, target_height):
    scale = min(target_width / image_width, target_height / image_height)
    return int(image_width * scale), int(image_height * scale)


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

    # 🔥 WICHTIG: Bild verkleinern → verhindert Timeout
    max_size = 2000
    img.thumbnail((max_size, max_size))

    cols, rows = compute_grid(sheets, img.width / img.height)

    # A4 Größe
    dpi = 150
    page_w, page_h = A4
    page_w_px = int(page_w / 72 * dpi)
    page_h_px = int(page_h / 72 * dpi)

    tile_w = page_w_px
    tile_h = page_h_px

    poster_w = cols * tile_w
    poster_h = rows * tile_h

    new_w, new_h = fit_image(img.width, img.height, poster_w, poster_h)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    poster = Image.new("RGB", (poster_w, poster_h), "white")
    offset_x = (poster_w - new_w) // 2
    offset_y = (poster_h - new_h) // 2
    poster.paste(img, (offset_x, offset_y))

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for r in range(rows):
        for c_idx in range(cols):
            left = c_idx * tile_w
            top = r * tile_h
            right = left + tile_w
            bottom = top + tile_h

            tile = poster.crop((left, top, right, bottom))

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
