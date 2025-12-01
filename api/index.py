# api/index.py
# Versão serverless pura para Vercel (sem Flask)
# Mantém suas rotas: /, /analyze, /export/csv, /export/excel
# Processamento de arquivos em memória e templates via render_template_string

import json
import os
import pandas as pd
from io import BytesIO, StringIO
from utils import parse_whatsapp_txt, analyze_keywords, highlight_lines
from flask import render_template_string  # só para renderizar templates em string

# --------------------------
# Helpers
# --------------------------

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")

def load_template(name):
    """Carrega template HTML manualmente (Vercel não suporta render_template)."""
    path = os.path.join(BASE_DIR, "templates", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def json_response(data, status=200):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data, default=str)
    }

def html_response(html, status=200):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html"},
        "body": html
    }

def file_response(buffer, mimetype, filename):
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": mimetype,
            "Content-Disposition": f"attachment; filename={filename}"
        },
        "body": buffer.getvalue(),
        "isBase64Encoded": True  # Vercel exige base64 para arquivos binários
    }

# --------------------------
# Rotas serverless
# --------------------------

def handler(request):
    """
    Função handler principal para Vercel.
    request: objeto compatível com Flask-like (request.form, request.files)
    """

    try:
        path = request.path
        method = request.method.upper()

        # ----------------------
        # Página inicial "/"
        # ----------------------
        if path == "/" and method == "GET":
            html = load_template("index.html")
            return html_response(render_template_string(html))

        # ----------------------
        # Rota /analyze
        # ----------------------
        elif path == "/analyze" and method == "POST":
            file = request.files.get("file")
            keywords_raw = request.form.get("keywords", "")
            fuzzy = float(request.form.get("fuzzy_threshold", "0") or 0)

            if not file:
                return json_response({"error": "Arquivo ausente"}, 400)

            # Processa arquivo em memória
            text_bytes = file.read().decode("utf-8", errors="ignore")
            messages = parse_whatsapp_txt(StringIO(text_bytes))
            keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]

            report = analyze_keywords(messages, keywords, fuzzy_threshold=fuzzy)
            highlighted = highlight_lines(messages, keywords)

            # Gerar gráfico (dados)
            rows = []
            for item in report:
                for m in item['matches']:
                    dt = m['date'].date() if m['date'] else None
                    rows.append({'date': str(dt) if dt else 'unknown'})
            df = pd.DataFrame(rows)
            chart_df = df.groupby('date').size().reset_index(name='count') if not df.empty else pd.DataFrame({'date':[],'count':[]})

            html = load_template("report.html")
            rendered = render_template_string(html, report=report, text_lines=highlighted, chart_data=chart_df.to_dict("list"))

            return html_response(rendered)

        # ----------------------
        # Rota /export/csv
        # ----------------------
        elif path == "/export/csv" and method == "POST":
            data = request.get_json()
            if "report" not in data:
                return json_response({"error": "Dados ausentes"}, 400)

            df = pd.json_normalize(data["report"])
            buf = BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")
            buf.seek(0)

            return file_response(buf, "text/csv", "relatorio.csv")

        # ----------------------
        # Rota /export/excel
        # ----------------------
        elif path == "/export/excel" and method == "POST":
            data = request.get_json()
            if "report" not in data:
                return json_response({"error": "Dados ausentes"}, 400)

            df = pd.json_normalize(data["report"])
            buf = BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)

            return file_response(buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "relatorio.xlsx")

        else:
            return json_response({"error": "Rota não encontrada"}, 404)

    except Exception as e:
        import traceback
        return json_response({"error": str(e), "trace": traceback.format_exc()}, 500)
