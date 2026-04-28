from flask import Flask, render_template, request, send_file
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import io
import math
import zipfile

app = Flask(__name__)

SHEET_MAP = {
    "A4": 1,
    "A3": 2,
    "A2": 4,
    "A1": 8,
}

BRAND_TEXT = "Erstellt mit dem Bild-zu-Poster-Service auf Katicas-Galerie.de"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/raster-kontur")
def raster_kontur():
    return render_template("raster_kontur.html")


@app.route("/malen-nach-zahlen")
def malen_nach_zahlen():
    return render_template("malen_nach_zahlen.html")


@app.route("/farb-tool")
def farb_tool():
    return render_template("farb_tool.html")


@app.route("/farben-analysieren")
def farben_analysieren():
    return render_template("farben_analysieren.html")


@app.route("/perspektive")
def perspektive():
    return render_template("perspektive.html")


@app.route("/proportionen")
def proportionen():
    return render_template("proportionen.html")


def mm_to_pt(mm):
    return mm * 2.83465


def compute_grid(n):
    if n == 1:
        return 1, 1

    if n == 2:
        return 2, 1

    if n == 4:
        return 2, 2

    if n == 8:
        return 4, 2

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


def prepare_poster_image(img, cols, rows, margin_mm, overlap_mm):
    page_px_w = 1200
    page_px_h = int(page_px_w * (A4[1] / A4[0]))

    margin_pt = mm_to_pt(margin_mm)
    overlap_pt = mm_to_pt(overlap_mm)

    page_w, page_h = A4

    usable_pt_w = page_w - 2 * margin_pt
    usable_pt_h = page_h - 2 * margin_pt

    margin_px = int(page_px_w * (margin_pt / page_w))
    overlap_px = int(page_px_w * (overlap_pt / page_w))

    usable_px_w = page_px_w - 2 * margin_px
    usable_px_h = page_px_h - 2 * margin_px

    step_x = usable_px_w - overlap_px
    step_y = usable_px_h - overlap_px

    poster_w = step_x * (cols - 1) + usable_px_w
    poster_h = step_y * (rows - 1) + usable_px_h

    img_w, img_h = img.size

    scale = max(poster_w / img_w, poster_h / img_h)

    new_w = int(img_w * scale)
    new_h = int(img_h * scale)

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - poster_w) // 2
    top = (new_h - poster_h) // 2

    poster = resized.crop((left, top, left + poster_w, top + poster_h))

    return poster, usable_px_w, usable_px_h, step_x, step_y, margin_pt, overlap_pt, usable_pt_w, usable_pt_h


def draw_image_border(pdf, margin, usable_w, usable_h):
    pdf.setLineWidth(0.6)
    pdf.setDash(3, 2)
    pdf.rect(margin, margin, usable_w, usable_h)
    pdf.setDash()


def draw_overlap_guides(pdf, margin, usable_w, usable_h, overlap, row, col, rows, cols):
    if overlap <= 0:
        return

    pdf.setLineWidth(0.4)
    pdf.setDash(2, 2)
    pdf.setFont("Helvetica", 6)

    if col < cols - 1:
        x1 = margin + usable_w - overlap
        x2 = margin + usable_w
        y1 = margin
        y2 = margin + usable_h

        pdf.rect(x1, y1, overlap, usable_h)

        step = 10
        y = y1
        while y < y2:
            pdf.line(x1, y, x2, y + step)
            y += step

        pdf.drawCentredString(x1 + overlap / 2, margin + usable_h / 2, "Überlappung")

    if row < rows - 1:
        x1 = margin
        x2 = margin + usable_w
        y1 = margin
        y2 = margin + overlap

        pdf.rect(x1, y1, usable_w, overlap)

        step = 10
        x = x1
        while x < x2:
            pdf.line(x, y1, x + step, y2)
            x += step

        pdf.drawCentredString(margin + usable_w / 2, y1 + overlap / 2 - 2, "Überlappung")

    pdf.setDash()


@app.route("/create-pdf", methods=["POST"])
def create_pdf():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    fmt = request.form.get("format", "A4").upper()

    margin_mm = int(request.form.get("margin_mm", 5))
    overlap_mm = int(request.form.get("overlap_mm", 5))

    if fmt not in SHEET_MAP:
        return "Format ungültig", 400

    total_pages = SHEET_MAP[fmt]

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    cols, rows = compute_grid(total_pages)

    (
        poster_img,
        tile_px_w,
        tile_px_h,
        step_x,
        step_y,
        margin,
        overlap,
        usable_w,
        usable_h
    ) = prepare_poster_image(img, cols, rows, margin_mm, overlap_mm)

    page_w, page_h = A4

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    draw_overview_page(pdf, fmt, rows, cols, total_pages, page_w, page_h)

    page_number = 1

    for r in range(rows):
        for c_idx in range(cols):
            left = c_idx * step_x
            top = r * step_y
            right = left + tile_px_w
            bottom = top + tile_px_h

            tile = poster_img.crop((left, top, right, bottom))

            pdf.drawImage(
                ImageReader(tile),
                margin,
                margin,
                width=usable_w,
                height=usable_h
            )

            draw_image_border(pdf, margin, usable_w, usable_h)
            draw_overlap_guides(pdf, margin, usable_w, usable_h, overlap, r, c_idx, rows, cols)

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


def create_paint_by_numbers_template(img, color_count):
    img = img.convert("RGB")
    img.thumbnail((900, 900))

    quantized = img.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    palette_img = quantized.convert("RGB")

    colors = palette_img.getcolors(maxcolors=1000000)
    colors = sorted(colors, reverse=True)

    palette = []
    for count, color in colors[:color_count]:
        if color not in palette:
            palette.append(color)

    small = palette_img.resize((90, 90), Image.Resampling.BILINEAR)
    small = small.quantize(colors=color_count).convert("RGB")

    scale = 10
    w, h = small.size
    template = Image.new("RGB", (w * scale, h * scale), "white")
    draw = ImageDraw.Draw(template)

    try:
        font = ImageFont.truetype("arial.ttf", 8)
    except:
        font = ImageFont.load_default()

    color_to_number = {}
    for i, color in enumerate(palette):
        color_to_number[color] = i + 1

    for y in range(h):
        for x in range(w):
            color = small.getpixel((x, y))
            nearest = min(
                palette,
                key=lambda c: abs(c[0] - color[0]) + abs(c[1] - color[1]) + abs(c[2] - color[2])
            )

            number = color_to_number[nearest]

            x1 = x * scale
            y1 = y * scale
            x2 = x1 + scale
            y2 = y1 + scale

            draw.rectangle((x1, y1, x2, y2), outline=(180, 180, 180), fill="white")
            draw.text((x1 + 2, y1 + 1), str(number), fill=(0, 0, 0), font=font)

    return template, palette


def create_color_legend(palette):
    row_h = 50
    width = 500
    height = 80 + len(palette) * row_h

    legend = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(legend)

    try:
        title_font = ImageFont.truetype("arial.ttf", 24)
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        font = ImageFont.load_default()

    draw.text((20, 20), "Farblegende", fill=(0, 0, 0), font=title_font)

    y = 70
    for i, color in enumerate(palette, start=1):
        draw.rectangle((20, y, 60, y + 30), fill=color, outline=(0, 0, 0))
        draw.text((80, y + 6), f"{i}: RGB {color}", fill=(0, 0, 0), font=font)
        y += row_h

    return legend


@app.route("/create-malen-nach-zahlen", methods=["POST"])
def create_malen_nach_zahlen():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    color_count = int(request.form.get("color_count", 8))

    color_count = max(3, min(color_count, 16))

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)

    template, palette = create_paint_by_numbers_template(img, color_count)
    legend = create_color_legend(palette)

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        template_buffer = io.BytesIO()
        template.save(template_buffer, format="PNG")
        template_buffer.seek(0)
        zip_file.writestr("malen_nach_zahlen_vorlage.png", template_buffer.read())

        legend_buffer = io.BytesIO()
        legend.save(legend_buffer, format="PNG")
        legend_buffer.seek(0)
        zip_file.writestr("farblegende.png", legend_buffer.read())

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name="malen_nach_zahlen_katicas_galerie.zip",
        mimetype="application/zip"
    )


@app.route("/create-farb-tool", methods=["POST"])
def create_farb_tool():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    color_count = int(request.form.get("color_count", 8))
    style = request.form.get("style", "klar")

    color_count = max(3, min(color_count, 24))

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))

    if style == "weich":
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = img.filter(ImageFilter.SMOOTH)

    quantized = img.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    result = quantized.convert("RGB")

    if style == "klar":
        result = result.filter(ImageFilter.SHARPEN)

    output = io.BytesIO()
    result.save(output, format="PNG")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"farb_reduktion_{color_count}_farben_katicas_galerie.png",
        mimetype="image/png"
    )


@app.route("/create-perspektive", methods=["POST"])
def create_perspektive():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    density = int(request.form.get("density", 12))
    line_color = request.form.get("line_color", "black")

    density = max(6, min(density, 40))

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))

    result = img.copy()
    draw = ImageDraw.Draw(result)

    width, height = result.size
    center_x = width // 2
    center_y = height // 2

    if line_color == "white":
        color = (255, 255, 255)
    elif line_color == "blue":
        color = (22, 121, 214)
    else:
        color = (0, 0, 0)

    line_width = max(1, width // 900)

    radius = max(4, width // 180)
    draw.ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        fill=color
    )

    for i in range(density + 1):
        x = int(i * width / density)
        draw.line((x, 0, center_x, center_y), fill=color, width=line_width)
        draw.line((x, height, center_x, center_y), fill=color, width=line_width)

    for i in range(density + 1):
        y = int(i * height / density)
        draw.line((0, y, center_x, center_y), fill=color, width=line_width)
        draw.line((width, y, center_x, center_y), fill=color, width=line_width)

    draw.line((0, center_y, width, center_y), fill=color, width=line_width)

    output = io.BytesIO()
    result.save(output, format="PNG")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="perspektiv_raster_katicas_galerie.png",
        mimetype="image/png"
    )


@app.route("/create-proportionen", methods=["POST"])
def create_proportionen():
    if "image" not in request.files:
        return "Keine Datei", 400

    file = request.files["image"]
    mode = request.form.get("mode", "standard")
    line_color = request.form.get("line_color", "black")

    img = Image.open(file.stream)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))

    result = img.copy()
    draw = ImageDraw.Draw(result)

    width, height = result.size

    if line_color == "white":
        color = (255, 255, 255)
    elif line_color == "blue":
        color = (22, 121, 214)
    else:
        color = (0, 0, 0)

    line_width = max(1, width // 900)

    draw.line((width / 2, 0, width / 2, height), fill=color, width=line_width)
    draw.line((0, height / 2, width, height / 2), fill=color, width=line_width)

    draw.line((width / 3, 0, width / 3, height), fill=color, width=line_width)
    draw.line((2 * width / 3, 0, 2 * width / 3, height), fill=color, width=line_width)
    draw.line((0, height / 3, width, height / 3), fill=color, width=line_width)
    draw.line((0, 2 * height / 3, width, 2 * height / 3), fill=color, width=line_width)

    draw.line((0, 0, width, height), fill=color, width=line_width)
    draw.line((width, 0, 0, height), fill=color, width=line_width)

    if mode == "grid":
        steps = 8
        for i in range(1, steps):
            x = int(width * i / steps)
            y = int(height * i / steps)
            draw.line((x, 0, x, height), fill=color, width=1)
            draw.line((0, y, width, y), fill=color, width=1)

    output = io.BytesIO()
    result.save(output, format="PNG")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="proportionen_checker_katicas_galerie.png",
        mimetype="image/png"
    )


if __name__ == "__main__":
    app.run()
