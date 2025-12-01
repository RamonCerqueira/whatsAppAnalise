# utils.py
# Helpers do WhatsApp Analyzer para uso em Vercel (serverless)
# Compatível com leitura de arquivos em memória ou disco
# Comentado e seguro para evitar crashes

import re
from datetime import datetime
from rapidfuzz import fuzz

# --------- Padrões de data do WhatsApp ---------
PATTERN1 = re.compile(r'^(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})(?:\s*-\s*)(.*?):\s*(.*)$')
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
            continue
    return None


# ----------------- Parse do TXT -----------------
def parse_whatsapp_txt(file_or_path):
    """
    Lê arquivo TXT (WhatsApp) e separa mensagens.
    file_or_path: pode ser path string ou arquivo-like (StringIO)
    Retorno: lista de dicts {'id', 'date', 'author', 'text'}
    """
    if isinstance(file_or_path, str):
        with open(file_or_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    else:
        lines = file_or_path.read().splitlines()
        file_or_path.seek(0)

    messages = []
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

        # regex exato para frase/palavra (escapando caracteres especiais)
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
                    try:
                        score = fuzz.partial_ratio(kw.lower(), text.lower())
                        if score >= fuzzy_threshold * 100:
                            matches.append({
                                "id": msg["id"],
                                "date": msg["date"],
                                "author": msg["author"],
                                "text_excerpt": excerpt(text, kw),
                                "score": score
                            })
                    except Exception:
                        # Ignorar problemas de unicode ou strings inválidas
                        continue

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
            try:
                txt = re.sub(
                    re.escape(kw),
                    lambda x: f"<mark>{x.group(0)}</mark>",
                    txt,
                    flags=re.IGNORECASE
                )
            except Exception:
                continue

        txt = txt.replace("\n", "<br>")

        out.append({
            "id": msg["id"],
            "date": msg["date"],
            "author": msg["author"],
            "html": txt
        })

    return out
