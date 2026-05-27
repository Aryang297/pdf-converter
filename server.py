#!/usr/bin/env python3
"""
PDF Converter Backend Server
Handles PDF→DOCX and DOCX→PDF conversions
"""
import os
import sys
import uuid
import shutil
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pdf2docx import Converter

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "pdf_converter"
UPLOAD_DIR.mkdir(exist_ok=True)

SOFFICE_SCRIPT = "/mnt/skills/public/docx/scripts/office/soffice.py"


def session_dir(session_id: str) -> Path:
    d = UPLOAD_DIR / session_id
    d.mkdir(exist_ok=True)
    return d


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/convert/pdf-to-docx", methods=["POST"])
def pdf_to_docx():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files accepted"}), 400

    session_id = str(uuid.uuid4())
    work_dir = session_dir(session_id)

    pdf_path = work_dir / "input.pdf"
    docx_path = work_dir / "output.docx"

    file.save(str(pdf_path))

    try:
        cv = Converter(str(pdf_path))
        cv.convert(str(docx_path), start=0, end=None)
        cv.close()

        if not docx_path.exists():
            return jsonify({"error": "Conversion failed"}), 500

        orig_name = Path(file.filename).stem
        download_name = f"{orig_name}.docx"

        return send_file(
            str(docx_path),
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # cleanup after sending
        pass


@app.route("/convert/docx-to-pdf", methods=["POST"])
def docx_to_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    fname = file.filename.lower()
    if not (fname.endswith(".docx") or fname.endswith(".doc")):
        return jsonify({"error": "Only DOCX/DOC files accepted"}), 400

    session_id = str(uuid.uuid4())
    work_dir = session_dir(session_id)

    ext = Path(file.filename).suffix
    input_path = work_dir / f"input{ext}"
    file.save(str(input_path))

    try:
        # Use LibreOffice to convert docx → pdf
        result = subprocess.run(
            [sys.executable, SOFFICE_SCRIPT, "--headless",
             "--convert-to", "pdf", str(input_path),
             "--outdir", str(work_dir)],
            capture_output=True, text=True, timeout=60
        )

        pdf_path = work_dir / "input.pdf"
        if not pdf_path.exists():
            # Try alternate output name
            for f in work_dir.glob("*.pdf"):
                pdf_path = f
                break

        if not pdf_path.exists():
            return jsonify({"error": f"Conversion failed: {result.stderr}"}), 500

        orig_name = Path(file.filename).stem
        download_name = f"{orig_name}.pdf"

        return send_file(
            str(pdf_path),
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7861))
    print(f"PDF Converter server running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
