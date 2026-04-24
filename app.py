from flask import Flask, render_template, request, send_file
from PIL import Image
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create-pdf", methods=["POST"])
def create_pdf():
    file = request.files["image"]
    img = Image.open(file)

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer)

    width, height = img.size
    c.drawInlineImage(img, 0, 0, width=width, height=height)

    c.showPage()
    c.save()

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="poster.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run()
