# utils.py
# Helpers do WhatsApp Analyzer para uso no Vercel (serverless)
# Comentado e compatível com leitura em /tmp.

import re
from datetime import datetime
from rapidfuzz import fuzz

# --------- Padrões de data do WhatsApp ---------
# Exemplo comum: "04/12/2023 11:12 - Fulano: mensagem"
PATTERN1 = re.compile(r'^(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})(?:\s*-\s*)(.*?):\s*(.*)$')

# Outro formato: "01/12/2024, 14:22 - Fulano: mensagem"
PATTERN2 = re.compile(r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2})\s*-\s*(.*?):\s*(.*)$')


# ----------------- Parse de data -----------------
def _try_parse_date(date_str):
    for fmt in (
        "%d/%m/%Y %H:%M",
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%y %H:%M:%S",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            pass
    return None


# ----------------- Parse do TXT -----------------
def parse_whatsapp_txt(path):
    """
    Lê arquivo TXT (estilo export WhatsApp) e separa mensagens.
    Retorno: lista de dicts:
      {'id', 'date', 'author', 'text'}
    """
    messages = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()

    buffer = None
    msg_id = 0

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue

        m1 = PATTERN1.match(line)
        m2 = PATTERN2.match(line)

        if m1 or m2:
            if buffer:
                messages.append(buffer)

            msg_id += 1
            m = m1 or m2
            date_str = f"{m.group(1)} {m.group(2)}"
            date = _try_parse_date(date_str)
            author = m.group(3).strip()
            text = m.group(4).strip()

            buffer = {"id": msg_id, "date": date, "author": author, "text": text}

        else:
            # Continuação da mensagem anterior
            if buffer:
                buffer["text"] += "\n" + line
            else:
                msg_id += 1
                buffer = {"id": msg_id, "date": None, "author": "", "text": line}

    if buffer:
        messages.append(buffer)

    return messages


# ----------------- Trecho em volta da frase -----------------
def excerpt(text, phrase, context=50):
    idx = text.lower().find(phrase.lower())
    if idx == -1:
        return text[: 2 * context] + ("..." if len(text) > context * 2 else "")

    start = max(0, idx - context)
    end = min(len(text), idx + len(phrase) + context)
    return ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")


# ----------------- Busca das keywords -----------------
def analyze_keywords(messages, keywords, fuzzy_threshold=0.0):
    result = []

    for kw in keywords:
        matches = []

        # regex exato para frase/palavra (sem \b)
        exact_pattern = re.compile(re.escape(kw), re.IGNORECASE)

        for msg in messages:
            text = msg["text"]

            # Busca exata
            if exact_pattern.search(text):
                matches.append({
                    "id": msg["id"],
                    "date": msg["date"],
                    "author": msg["author"],
                    "text_excerpt": excerpt(text, kw),
                    "score": 100
                })
            else:
                # fuzzy opcional
                if fuzzy_threshold > 0:
                    score = fuzz.partial_ratio(kw.lower(), text.lower())
                    if score >= fuzzy_threshold * 100:
                        matches.append({
                            "id": msg["id"],
                            "date": msg["date"],
                            "author": msg["author"],
                            "text_excerpt": excerpt(text, kw),
                            "score": score
                        })

        result.append({
            "word": kw,
            "count": len(matches),
            "matches": matches
        })

    return result


# ----------------- Highlight no texto -----------------
def highlight_lines(messages, keywords):
    out = []
    for msg in messages:
        txt = msg["text"]

        for kw in keywords:
            txt = re.sub(
                re.escape(kw),
                lambda x: f"<mark>{x.group(0)}</mark>",
                txt,
                flags=re.IGNORECASE
            )

        txt = txt.replace("\n", "<br>")

        out.append({
            "id": msg["id"],
            "date": msg["date"],
            "author": msg["author"],
            "html": txt
        })

    return out
