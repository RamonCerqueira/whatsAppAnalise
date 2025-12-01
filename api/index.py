# api/index.py
# Versão serverless do seu Flask para Vercel.
# IMPORTANTE: usar render_template_string apontando para leitura manual dos templates.

from flask import Flask, request, send_file, jsonify
from flask import render_template_string
import os
import pandas as pd
from io import BytesIO
from utils import parse_whatsapp_txt, analyze_keywords, highlight_lines

app = Flask(__name__)

# --------------------------------------------------------------------
# Helpers para carregar templates (Vercel não suporta render_template)
# --------------------------------------------------------------------
def load_template(name):
    path = os.path.join(os.path.dirname(__file__), "..", "templates", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# --------------------------------------------------------------------
# Rotas
# --------------------------------------------------------------------

@app.route("/", methods=["GET"])
def form():
    html = load_template("index.html")
    return render_template_string(html)

@app.route("/analyze", methods=["POST"])
def analyze():
    file = request.files.get("file")
    keywords_raw = request.form.get("keywords", "")
    fuzzy = float(request.form.get("fuzzy_threshold", "0") or 0)

    if not file:
        return "Arquivo ausente", 400

    # lê o txt sem salvar no disco (Vercel não deixa)
    text_bytes = file.read().decode("utf-8", errors="ignore")
    temp_path = "/tmp/temp_whatsapp.txt"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(text_bytes)

    messages = parse_whatsapp_txt(temp_path)
    keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]

    report = analyze_keywords(messages, keywords, fuzzy_threshold=fuzzy)
    highlighted = highlight_lines(messages, keywords)

    # gerar gráfico
    rows = []
    for item in report:
        for m in item['matches']:
            dt = m['date'].date() if m['date'] else None
            rows.append({'date': str(dt) if dt else 'unknown'})
    df = pd.DataFrame(rows)
    chart_df = df.groupby('date').size().reset_index(name='count') if not df.empty else pd.DataFrame({'date':[],'count':[]})

    html = load_template("report.html")

    return render_template_string(
        html,
        report=report,
        text_lines=highlighted,
        chart_data=chart_df.to_dict("list")
    )

@app.route("/export/csv", methods=["POST"])
def export_csv():
    data = request.get_json()
    df = pd.json_normalize(data["report"])
    buf = BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="relatorio.csv")

@app.route("/export/excel", methods=["POST"])
def export_excel():
    data = request.get_json()
    df = pd.json_normalize(data["report"])
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="relatorio.xlsx",
    )

# Vercel: expoe o app
def handler(event, context):
    return app(event, context)
