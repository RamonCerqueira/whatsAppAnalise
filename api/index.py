# api/index.py
# Versão serverless pura para Vercel (sem Flask)
# Mantém suas rotas: /, /analyze, /export/csv, /export/excel
# Processamento de arquivos em memória e templates via render_template_string
# Logging completo para debugging

import json
import os
import pandas as pd
from io import BytesIO, StringIO
from utils import parse_whatsapp_txt, analyze_keywords, highlight_lines
from flask import render_template_string  # só para renderizar templates em string
import sys
import traceback

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
# Handler serverless
# --------------------------

def handler(request):
    """
    Handler serverless com logs completos para debugging na Vercel.
    """
    try:
        path = request.path
        method = request.method.upper()
        print(f"[LOG] Rota: {path} | Método: {method}", file=sys.stderr)

        # ----------------------
        # Página inicial "/"
        # ----------------------
        if path == "/" and method == "GET":
            html = load_template("index.html")
            print("[LOG] Renderizando index.html", file=sys.stderr)
            return html_response(render_template_string(html))

        # ----------------------
        # Rota /analyze
        # ----------------------
        elif path == "/analyze" and method == "POST":
            file = request.files.get("file")
            keywords_raw = request.form.get("keywords", "")
            fuzzy = float(request.form.get("fuzzy_threshold", "0") or 0)

            print(f"[LOG] Keywords recebidas: {keywords_raw}", file=sys.stderr)
            if file:
                file_size = len(file.read())
                file.seek(0)  # reset do ponteiro
                print(f"[LOG] Arquivo recebido com tamanho: {file_size} bytes", file=sys.stderr)
            else:
                print("[LOG] Nenhum arquivo enviado", file=sys.stderr)
                return json_response({"error": "Arquivo ausente"}, 400)

            # Processa arquivo em memória
            text_bytes = file.read().decode("utf-8", errors="ignore")
            messages = parse_whatsapp_txt(StringIO(text_bytes))
            keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]

            report = analyze_keywords(messages, keywords, fuzzy_threshold=fuzzy)
            highlighted = highlight_lines(messages, keywords)

            # Gerar dados do gráfico
            rows = []
            for item in report:
                for m in item['matches']:
                    dt = m['date'].date() if m['date'] else None
                    rows.append({'date': str(dt) if dt else 'unknown'})
            df = pd.DataFrame(rows)
            chart_df = df.groupby('date').size().reset_index(name='count') if not df.empty else pd.DataFrame({'date':[],'count':[]})

            html = load_template("report.html")
            rendered = render_template_string(html, report=report, text_lines=highlighted, chart_data=chart_df.to_dict("list"))

            print("[LOG] Análise concluída com sucesso", file=sys.stderr)
            return html_response(rendered)

        # ----------------------
        # Rota /export/csv
        # ----------------------
        elif path == "/export/csv" and method == "POST":
            data = request.get_json()
            if "report" not in data:
                print("[LOG] Dados ausentes para CSV", file=sys.stderr)
                return json_response({"error": "Dados ausentes"}, 400)

            df = pd.json_normalize(data["report"])
            buf = BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")
            buf.seek(0)
            print("[LOG] Export CSV gerado", file=sys.stderr)
            return file_response(buf, "text/csv", "relatorio.csv")

        # ----------------------
        # Rota /export/excel
        # ----------------------
        elif path == "/export/excel" and method == "POST":
            data = request.get_json()
            if "report" not in data:
                print("[LOG] Dados ausentes para Excel", file=sys.stderr)
                return json_response({"error": "Dados ausentes"}, 400)

            df = pd.json_normalize(data["report"])
            buf = BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)
            print("[LOG] Export Excel gerado", file=sys.stderr)
            return file_response(buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "relatorio.xlsx")

        else:
            print(f"[LOG] Rota não encontrada: {path}", file=sys.stderr)
            return json_response({"error": "Rota não encontrada"}, 404)

    except Exception as e:
        print("[ERROR] Exception na função handler:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return json_response({"error": str(e), "trace": traceback.format_exc()}, 500)
