from flask import Flask, render_template, request, send_file
from PIL import Image, ImageOps, ImageFilter, ImageDraw
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

BRAND_TEXT = "Erstellt mit dem Bild-zu-Poster-Service auf Katicas-Galerie.de"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/raster-kontur")
def raster_kontur():
    return render_template("raster_kontur.html")


def compute_grid(n):
    cols = int(math.sqrt(n))
    rows = math.ceil(n / cols)
    return cols, rows


def draw_cut_marks(pdf, page_w, page_h):
    mark = 18
    offset = 18
    pdf.setLineWidth(0.5)

    pdf.line(offset, offset, offset + mark, offset)
    pdf.line(offset, offset, offset, offset + mark)
    pdf.line(page_w - offset, offset, page_w - offset - mark, offset)
    pdf.line(page_w - offset, offset, page_w - offset, offset + mark)
    pdf.line(offset, page_h - offset, offset + mark, page_h - offset)
    pdf.line(offset, page_h - offset, offset, page_h - offset - mark)
    pdf.line(page_w - offset, page_h - offset, page_w - offset - mark, page_h - offset)
    pdf.line(page_w - offset, page_h - offset, page_w - offset, page_h - offset - mark)


def draw_page_label(pdf, fmt, page_number, total_pages, row, col, rows, cols, page_w):
    pdf.setFont("Helvetica", 8)
    text = f"{fmt} | Seite {page_number} von {total_pages} | Reihe {row + 1}/{rows}, Spalte {col + 1}/{cols}"
    pdf.drawCentredString(page_w / 2, 12, text)


def draw_branding(pdf, page_w):
    pdf.setFont("Helvetica", 7)
    pdf.drawString(20, 12, BRAND_TEXT)


def draw_assembly_hints(pdf, row, col, rows, cols, page_w, page_h):
    pdf.setFont("Helvetica", 7)

    if col < cols - 1:
        pdf.drawRightString(page_w - 24, page_h / 2, "rechts an nächste Seite kleben")

    if row < rows - 1:
        pdf.drawCentredString(page_w / 2, 24, "unten an nächste Reihe kleben")


def draw_overview_page(pdf, fmt, rows, cols, total_pages, page_w, page_h):
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(page_w / 2, page_h - 70, "Poster-Zusammenbau")

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        page_w / 2,
        page_h - 100,
        f"Format: {fmt} | {total_pages} A4-Seiten | {rows} Reihen x {cols} Spalten"
    )

    grid_w = page_w * 0.65
    grid_h = page_h * 0.42
    cell_w = grid_w / cols
    cell_h = grid_h / rows
    start_x = (page_w - grid_w) / 2
    start_y = page_h - 160 - grid_h

    pdf.setLineWidth(1)

    page_no = 1
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * cell_w
            y = start_y + (rows - 1 - r) * cell_h

            pdf.rect(x, y, cell_w, cell_h)
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawCentredString(x + cell_w / 2, y + cell_h / 2 - 5, str(page_no))

            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(x + cell_w / 2, y + 8, f"R{r + 1} / S{c + 1}")

            page_no += 1

    info_y = 130
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(70, info_y, "Druckhinweis:")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(70, info_y - 22, "Bitte beim Drucken „Tatsächliche Größe“ oder „100 %“ auswählen.")
    pdf.drawString(70, info_y - 40, "Nicht „An Seite anpassen“ verwenden.")
    pdf.drawString(70, info_y - 58, "Seiten von links nach rechts und oben nach unten zusammenkleben.")

    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(page_w / 2, 40, BRAND_TEXT)

    pdf.showPage()


@app.route("/create-pdf", methods=["POST"])
def create_pdf():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    fmt = request.form.get("format", "A4").upper()

    if fmt not in SHEET_MAP:
        return "Format ungültig", 400

    total_pages = SHEET_MAP[fmt]

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1500, 1500))

    cols, rows = compute_grid(total_pages)

    img_w, img_h = img.size
    tile_w = img_w // cols
    tile_h = img_h // rows

    page_w, page_h = A4

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    draw_overview_page(pdf, fmt, rows, cols, total_pages, page_w, page_h)

    page_number = 1

    for r in range(rows):
        for c_idx in range(cols):
            left = c_idx * tile_w
            top = r * tile_h
            right = img_w if c_idx == cols - 1 else left + tile_w
            bottom = img_h if r == rows - 1 else top + tile_h

            tile = img.crop((left, top, right, bottom))

            pdf.drawImage(
                ImageReader(tile),
                0,
                0,
                width=page_w,
                height=page_h
            )

            draw_cut_marks(pdf, page_w, page_h)
            draw_page_label(pdf, fmt, page_number, total_pages, r, c_idx, rows, cols, page_w)
            draw_assembly_hints(pdf, r, c_idx, rows, cols, page_w, page_h)
            draw_branding(pdf, page_w)

            pdf.showPage()
            page_number += 1

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"poster_{fmt}_katicas_galerie.pdf",
        mimetype="application/pdf"
    )


@app.route("/create-raster-kontur", methods=["POST"])
def create_raster_kontur():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    mode = request.form.get("mode", "grid")
    grid_size = int(request.form.get("grid_size", 50))

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))

    result = img.copy()

    if mode in ["contour", "both"]:
        gray = img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.invert(edges)
        edges = edges.point(lambda p: 255 if p > 200 else 0)
        result = edges.convert("RGB")

    if mode in ["grid", "both"]:
        draw = ImageDraw.Draw(result)
        width, height = result.size

        for x in range(0, width, grid_size):
            draw.line((x, 0, x, height), fill=(0, 0, 0), width=1)

        for y in range(0, height, grid_size):
            draw.line((0, y, width, y), fill=(0, 0, 0), width=1)

    output = io.BytesIO()
    result.save(output, format="PNG")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="raster_kontur_katicas_galerie.png",
        mimetype="image/png"
    )


if __name__ == "__main__":
    app.run()
