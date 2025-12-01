# api/index.py
# Versão Flask pronta para Render
# Todas as rotas originais mantidas, processamento em memória e templates via render_template_string

import os
import pandas as pd
from io import BytesIO, StringIO
from flask import Flask, request, send_file, render_template_string, jsonify
from utils import parse_whatsapp_txt, analyze_keywords, highlight_lines
import traceback
import sys

# --------------------------
# App Flask
# --------------------------
app = Flask(__name__)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")

def load_template(name):
    """Carrega template HTML manualmente"""
    path = os.path.join(BASE_DIR, "templates", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# --------------------------
# Rotas
# --------------------------
@app.route("/", methods=["GET"])
def form():
    html = load_template("index.html")
    return render_template_string(html)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        file = request.files.get("file")
        keywords_raw = request.form.get("keywords", "")
        fuzzy = float(request.form.get("fuzzy_threshold", "0") or 0)

        if not file:
            return "Arquivo ausente", 400

        text_bytes = file.read().decode("utf-8", errors="ignore")
        messages = parse_whatsapp_txt(StringIO(text_bytes))
        keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]

        report = analyze_keywords(messages, keywords, fuzzy_threshold=fuzzy)
        highlighted = highlight_lines(messages, keywords)

        # gerar dados do gráfico
        rows = []
        for item in report:
            for m in item['matches']:
                dt = m['date'].date() if m['date'] else None
                rows.append({'date': str(dt) if dt else 'unknown'})
        df = pd.DataFrame(rows)
        chart_df = df.groupby('date').size().reset_index(name='count') if not df.empty else pd.DataFrame({'date':[],'count':[]})

        html = load_template("report.html")
        rendered = render_template_string(html, report=report, text_lines=highlighted, chart_data=chart_df.to_dict("list"))

        return rendered
    except Exception as e:
        print("[ERROR] /analyze:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/export/csv", methods=["POST"])
def export_csv():
    data = request.get_json()
    if "report" not in data:
        return jsonify({"error": "Dados ausentes"}), 400

    df = pd.json_normalize(data["report"])
    buf = BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="relatorio.csv")

@app.route("/export/excel", methods=["POST"])
def export_excel():
    data = request.get_json()
    if "report" not in data:
        return jsonify({"error": "Dados ausentes"}), 400

    df = pd.json_normalize(data["report"])
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="relatorio.xlsx")

# --------------------------
# Run local (opcional) para debug
# --------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
