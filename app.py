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


def draw_overlap_guides(pdf, margin, printable_w, printable_h, overlap_pt, row, col, rows, cols):
    if overlap_pt <= 0:
        return

    pdf.saveState()
    pdf.setLineWidth(0.6)
    pdf.setDash(4, 3)
    pdf.setFont("Helvetica", 7)

    # rechte Überlappung nur markieren, wenn rechts noch eine Seite folgt
    if col < cols - 1:
        x = margin + printable_w - overlap_pt
        pdf.line(x, margin, x, margin + printable_h)
        pdf.drawString(x + 3, margin + printable_h / 2, "Überlappung")

    # untere Überlappung nur markieren, wenn darunter noch eine Reihe folgt
    if row < rows - 1:
        y = margin + overlap_pt
        pdf.line(margin, y, margin + printable_w, y)
        pdf.drawString(margin + printable_w / 2 - 25, y + 4, "Überlappung")

    pdf.restoreState()


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
    pdf.drawString(70, info_y, "Druckhin
