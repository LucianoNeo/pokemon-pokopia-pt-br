from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import threading
import webbrowser
import zlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
BIN_NAME = "LD_C0_R.BIN"
IDX_NAME = "LI_C0_R.IDX"
INDEX_RECORD_SIZE = 32
MAX_BODY = 32 * 1024 * 1024
session_lock = threading.RLock()
session: dict = {"translated": None, "source": None}

LANG_WORDS = {
    "en": set("the and you your it this that to of in for with not is are was were we they he she my me our can could would do does did have has had what when where who why how from on at as be been being will just now hey oh please thanks thank friend good nice cool great really very if then there here all one two an i im dont cant thats its lets together building fixed move help home want need about around into out up down look see know make made go going get got come say said give take care".split()),
    "pt": set("de da do dos das que não nao você voce vocês voces eu um uma uns umas para pra com como é e está esta estão estao estou somos são sao foi já ja muito mais mas aqui ali isso isto esse essa esses essas ele ela eles elas meu minha meus minhas seu sua seus suas por porque quando onde quem qual quais agora então entao obrigado obrigada legal bacana bom boa bem fazer feito fez pode podia quero queria tenho tem tinha precisamos juntos prédio predio ponte consertou reformamos dá dar olha nossa".split()),
    "fr": set("je tu vous nous ils elles il elle le la les un une des du de au aux en dans par pas ne que qui quoi mais pourquoi peux peut peuvent suis est sont étais etait était faire fais fait être etre très tres ça cela c est ce cette ces mon ma mes ton ta tes son sa ses pour avec alors quand comme sur chez même meme beaucoup bien puis donc rien tout toute tous moment grosse fixette fixer fixe fusille fusilles regard droit réaction reaction puisque ainsi sortir grand jeu toujours flegme éprouve eprouve compte rester ici pendant autre duel veux moi toi t es j ai j fais m empêcher m empecher pourrais mettre maison s te plaît plait oui non salut bonjour merci voilà voila hein chouette coucou monsieur madame drôlement drolment assez".split()),
}


def detect_language(value: str) -> str:
    """Lightweight display filter: retain English, Portuguese, and neutral names."""
    plain = re.sub(r"<[^>]*>", " ", value or "").replace("’", "'").casefold()
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", plain, flags=re.UNICODE)
    if not words:
        return "neutral"
    scores = {lang: sum(2 for word in words if word in vocab)
              for lang, vocab in LANG_WORDS.items()}
    if re.search(r"[ãõ]", plain):
        scores["pt"] += 3
    if re.search(r"[èêœ]", plain):
        scores["fr"] += 3
    if re.search(r"\b(?:j|t|c|d|l|n|s|qu)'[a-zà-ÿ]+", plain):
        scores["fr"] += 2
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if len(words) <= 2 and any(word in {"oui", "bonjour", "salut", "merci", "voilà", "voila", "hein", "chouette", "coucou"} for word in words):
        return "fr"
    if ranked[0][1] < 4 or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
        return "neutral"
    return ranked[0][0]


def is_english_or_ptbr(value: str) -> bool:
    return detect_language(value) in ("en", "pt", "neutral")


def entry_lookup(pair: dict | None) -> dict[str, str]:
    if pair is None:
        return {}
    if pair.get("lookup") is None:
        pair["lookup"] = {item["key"]: item["text"] for item in load_entries(pair)}
    return pair["lookup"]


def entry_languages(pair: dict | None) -> dict[str, str]:
    if pair is None:
        return {}
    if pair.get("lang_lookup") is None:
        pair["lang_lookup"] = {item["key"]: item["language"] for item in load_entries(pair)}
    return pair["lang_lookup"]


def language_counts(translated: dict, source: dict | None) -> tuple[int, int]:
    source_map = entry_languages(source)
    entries = load_entries(translated)
    visible = sum(1 for item in entries
                  if item["language"] in ("en", "pt", "neutral") and
                  source_map.get(item["key"], "neutral") in ("en", "pt", "neutral"))
    return visible, len(entries) - visible


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_pair(romfs_path: str) -> dict:
    romfs = Path(romfs_path).expanduser().resolve()
    if romfs.name.lower() != "romfs" and not ((romfs / BIN_NAME).is_file() and (romfs / IDX_NAME).is_file()):
        raise ValueError("Selecione a pasta romfs ou uma pasta que contenha os dois arquivos C0.")
    bin_path, idx_path = romfs / BIN_NAME, romfs / IDX_NAME
    if not bin_path.is_file() or not idx_path.is_file():
        raise ValueError(f"Não encontrei {BIN_NAME} e {IDX_NAME} juntos nessa pasta.")
    binary, index = bin_path.read_bytes(), idx_path.read_bytes()
    if len(index) % INDEX_RECORD_SIZE:
        raise ValueError("O arquivo IDX não tem o tamanho esperado para esta versão.")
    return {
        "romfs": romfs,
        "bin_path": bin_path,
        "idx_path": idx_path,
        "bin": binary,
        "idx": index,
        "bin_hash": sha256(binary),
        "idx_hash": sha256(index),
        "banks": {},
        "entries": None,
        "stats": None,
    }


def decode_bank(binary: bytes, offset: int, stored_size: int | None = None) -> bytes:
    if offset < 0 or offset + 12 > len(binary):
        raise ValueError("offset do banco fora do BIN")
    limit, count, raw_size = struct.unpack_from("<III", binary, offset)
    if not limit or not count or count > 1024 or count != (raw_size + limit - 1) // limit:
        raise ValueError("cabeçalho do banco inválido")
    header_size = ((12 + 4 * count + 127) // 128) * 128
    cursor = offset + header_size
    block_end = offset + stored_size if stored_size else len(binary)
    if block_end > len(binary) or cursor > block_end:
        raise ValueError("limites do banco inválidos")
    parts = []
    for i in range(count):
        framed = struct.unpack_from("<I", binary, offset + 12 + i * 4)[0]
        expected = min(limit, raw_size - i * limit)
        if framed <= 0 or cursor + framed > block_end:
            raise ValueError("quadro do banco truncado")
        if framed == expected:
            part = binary[cursor:cursor + framed]
        else:
            if framed < 4:
                raise ValueError("quadro compactado inválido")
            compressed_size = struct.unpack_from("<I", binary, cursor)[0]
            if compressed_size + 4 != framed:
                raise ValueError("tamanho do quadro compactado não confere")
            part = zlib.decompress(binary[cursor + 4:cursor + framed])
        if len(part) != expected:
            raise ValueError("tamanho descompactado não confere")
        parts.append(part)
        cursor = (cursor + framed + 127) // 128 * 128
    return b"".join(parts)


def parse_table(raw: bytes):
    if len(raw) < 64:
        return None
    count, version = struct.unpack_from("<II", raw, 0)
    if version != 2 or not 0 < count <= 20000 or 64 + count * 8 > len(raw):
        return None
    first = struct.unpack_from("<I", raw, 64)[0]
    stride = next((s for s in (12, 16, 20, 24, 28, 32, 40, 48, 64) if first == count * s), 8)
    if 64 + count * stride > len(raw):
        return None
    columns = {12: 2, 32: 6}.get(stride, 1 if stride == 8 else stride // 4)
    columns = min(columns, stride // 4)
    floor = 64 + count * stride
    rows = []
    for row in range(count):
        for col in range(columns):
            field = 64 + row * stride + col * 4
            relative = struct.unpack_from("<I", raw, field)[0]
            target = field + relative
            if not relative or target < floor or target >= len(raw):
                continue
            end = raw.find(b"\0", target)
            if end < 0:
                continue
            try:
                value = raw[target:end].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if not value or any(ord(ch) < 32 and ch not in "\r\n\t" for ch in value):
                continue
            rows.append({"row": row, "col": col, "field": field, "text": value})
    return {"count": count, "stride": stride, "columns": columns, "floor": floor, "rows": rows}


def load_entries(pair: dict) -> list[dict]:
    if pair["entries"] is not None:
        return pair["entries"]
    entries = []
    banks = {}
    stats = {"index_records": len(pair["idx"]) // INDEX_RECORD_SIZE, "decoded_banks": 0,
             "text_banks": 0, "text_entries": 0, "invalid_banks": 0, "non_table_banks": 0}
    index, binary = pair["idx"], pair["bin"]
    for slot in range(len(index) // INDEX_RECORD_SIZE):
        offset, size, stored, flags = struct.unpack_from("<4Q", index, slot * INDEX_RECORD_SIZE)
        if not size or offset + 12 > len(binary) or stored == 0 or offset + stored > len(binary):
            continue
        try:
            raw = decode_bank(binary, offset, stored)
        except (ValueError, zlib.error, struct.error, OverflowError):
            stats["invalid_banks"] += 1
            continue
        stats["decoded_banks"] += 1
        parsed = parse_table(raw)
        if parsed is None or not parsed["rows"]:
            stats["non_table_banks"] += 1
            continue
        stats["text_banks"] += 1
        banks[slot] = {"slot": slot, "offset": offset, "size": size, "stored": stored,
                       "flags": flags, "raw": raw, "table": parsed}
        for item in parsed["rows"]:
            entries.append({"key": f"{slot}:{item['row']}:{item['col']}", "slot": slot,
                            "row": item["row"], "col": item["col"], "stride": parsed["stride"],
                            "text": item["text"], "language": detect_language(item["text"])})
    pair["banks"], pair["entries"], pair["stats"] = banks, entries, stats
    stats["text_entries"] = len(entries)
    return entries


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) // boundary * boundary


def encode_bank(raw: bytes, old_binary: bytes, old_offset: int) -> bytes:
    chunk_limit = struct.unpack_from("<I", old_binary, old_offset)[0]
    if not 0 < chunk_limit <= 0x100000:
        raise ValueError(f"limite de bloco inesperado no offset {old_offset:#x}")
    chunks = [raw[pos:pos + chunk_limit] for pos in range(0, len(raw), chunk_limit)]
    if not chunks or len(chunks) > 29:
        raise ValueError("o banco editado ultrapassou o limite suportado pelo cabeçalho")
    header_size = align(12 + 4 * len(chunks), 128)
    header = bytearray(header_size)
    header[:min(header_size, 128)] = old_binary[old_offset:old_offset + min(header_size, 128)]
    struct.pack_into("<III", header, 0, chunk_limit, len(chunks), len(raw))
    frames = []
    for i, chunk in enumerate(chunks):
        compressed = zlib.compress(chunk, 9)
        frame = struct.pack("<I", len(compressed)) + compressed
        struct.pack_into("<I", header, 12 + i * 4, len(frame))
        frames.append(frame)
    result = bytearray(header)
    for frame in frames:
        result.extend(frame)
        result.extend(b"\0" * (align(len(result), 128) - len(result)))
    return bytes(result)


def macro_signature(text: str) -> list[str]:
    return re.findall(r"<[^>]*>|\{[^}]*\}|%[0-9$]*[sdif]|\\[nrt]", text)


class Handler(BaseHTTPRequestHandler):
    server_version = "PokopiaTextWorkbench/1.0"

    def log_message(self, fmt, *args):
        print("[http] " + fmt % args)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Pedido grande demais.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        if parsed.path == "/api/state":
            with session_lock:
                tr = session["translated"]
                src = session["source"]
                self.send_json({"translated": str(tr["romfs"]) if tr else None,
                                "source": str(src["romfs"]) if src else None,
                                "stats": tr["stats"] if tr else None,
                                "source_stats": src["stats"] if src else None})
            return
        if parsed.path == "/api/entries":
            qs = parse_qs(parsed.query)
            query = qs.get("q", [""])[0].casefold().strip()
            try:
                page = max(1, int(qs.get("page", ["1"])[0]))
                page_size = min(250, max(20, int(qs.get("page_size", ["100"])[0])))
                only_edited = qs.get("edited", ["0"])[0] == "1"
                edited = set(json.loads(qs.get("keys", ["[]"])[0])) if only_edited else set()
            except (ValueError, json.JSONDecodeError):
                self.send_json({"error": "Parâmetros de busca inválidos."}, 400)
                return
            with session_lock:
                tr, src = session["translated"], session["source"]
                if not tr:
                    self.send_json({"error": "Abra primeiro a pasta romfs traduzida."}, 400)
                    return
                rows = load_entries(tr)
                source_map = entry_lookup(src)
                source_languages = entry_languages(src)
                matches = []
                for item in rows:
                    if only_edited and item["key"] not in edited:
                        continue
                    original = source_map.get(item["key"], "")
                    if item["language"] not in ("en", "pt", "neutral") or source_languages.get(item["key"], "neutral") not in ("en", "pt", "neutral"):
                        continue
                    haystack = f"{item['text']}\n{original}\n{item['slot']} {item['row']} {item['col']}".casefold()
                    if query and query not in haystack:
                        continue
                    matches.append({**item, "source": original})
                total = len(matches)
                start = (page - 1) * page_size
                self.send_json({"entries": matches[start:start + page_size], "total": total,
                                "page": page, "page_size": page_size,
                                "pages": max(1, (total + page_size - 1) // page_size),
                                "source_loaded": src is not None})
            return
        self.send_error(404)

    def do_POST(self):
        try:
            data = self.read_json()
            if self.path == "/api/entries":
                query = str(data.get("q", "")).casefold().strip()
                page = max(1, int(data.get("page", 1)))
                page_size = min(250, max(20, int(data.get("page_size", 100))))
                only_edited = bool(data.get("edited", False))
                edited = set(data.get("keys", [])) if only_edited else set()
                with session_lock:
                    tr, src = session["translated"], session["source"]
                    if not tr:
                        self.send_json({"error": "Abra primeiro a pasta romfs traduzida."}, 400)
                        return
                    rows = load_entries(tr)
                    source_map = entry_lookup(src)
                    source_languages = entry_languages(src)
                    matches = []
                    for item in rows:
                        if only_edited and item["key"] not in edited:
                            continue
                        original = source_map.get(item["key"], "")
                        if item["language"] not in ("en", "pt", "neutral") or source_languages.get(item["key"], "neutral") not in ("en", "pt", "neutral"):
                            continue
                        haystack = f"{item['text']}\n{original}\n{item['slot']} {item['row']} {item['col']}".casefold()
                        if query and query not in haystack:
                            continue
                        matches.append({**item, "source": original})
                    total = len(matches)
                    start = (page - 1) * page_size
                    self.send_json({"entries": matches[start:start + page_size], "total": total,
                                    "page": page, "page_size": page_size,
                                    "pages": max(1, (total + page_size - 1) // page_size),
                                    "source_loaded": src is not None})
                return
            if self.path == "/api/select-folder":
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                chosen = filedialog.askdirectory(title="Selecione a pasta romfs")
                root.destroy()
                self.send_json({"path": chosen})
                return
            if self.path == "/api/open":
                with session_lock:
                    tr = read_pair(data.get("translated", ""))
                    load_entries(tr)
                    src_path = data.get("source", "").strip()
                    src = read_pair(src_path) if src_path else None
                    if src:
                        load_entries(src)
                    session["translated"], session["source"] = tr, src
                    visible, hidden = language_counts(tr, src)
                    self.send_json({"ok": True, "translated": str(tr["romfs"]),
                                    "source": str(src["romfs"]) if src else None,
                                    "stats": tr["stats"], "source_stats": src["stats"] if src else None,
                                    "visible_entries": visible, "hidden_other_languages": hidden})
                return
            if self.path == "/api/save":
                edits = data.get("edits", {})
                if not isinstance(edits, dict):
                    raise ValueError("Lista de alterações inválida.")
                with session_lock:
                    pair = session["translated"]
                    if not pair:
                        raise ValueError("Abra primeiro a pasta romfs traduzida.")
                    current_bin = pair["bin_path"].read_bytes()
                    current_idx = pair["idx_path"].read_bytes()
                    if sha256(current_bin) != pair["bin_hash"] or sha256(current_idx) != pair["idx_hash"]:
                        raise ValueError("Os arquivos mudaram desde que foram abertos. Reabra a pasta antes de salvar para evitar sobrescrever alterações externas.")
                    bins = {slot: {**bank, "raw": bytearray(bank["raw"])} for slot, bank in pair["banks"].items()}
                    changed_slots = set()
                    for key, value in edits.items():
                        if not isinstance(value, str) or "\0" in value:
                            raise ValueError("Os textos precisam ser strings sem caractere NUL.")
                        try:
                            slot, row, col = (int(part) for part in key.split(":"))
                            bank = bins[slot]
                        except (ValueError, KeyError, TypeError):
                            raise ValueError(f"Chave de texto inválida: {key}")
                        table = bank["table"]
                        if not (0 <= row < table["count"] and 0 <= col < table["columns"]):
                            raise ValueError(f"Posição fora do banco: {key}")
                        entry = next((e for e in table["rows"] if e["row"] == row and e["col"] == col), None)
                        if entry is None:
                            raise ValueError(f"A posição {key} não é um texto editável.")
                        if value == entry["text"]:
                            continue
                        field = 64 + row * table["stride"] + col * 4
                        raw = bank["raw"]
                        target = len(raw)
                        encoded = value.encode("utf-8") + b"\0"
                        relative = target - field
                        if not 0 <= relative <= 0xFFFFFFFF:
                            raise ValueError(f"Texto grande demais para o formato no registro {key}.")
                        raw.extend(encoded)
                        struct.pack_into("<I", raw, field, relative)
                        changed_slots.add(slot)
                    if not changed_slots:
                        self.send_json({"ok": True, "message": "Nenhuma alteração nova para salvar.", "changed": 0})
                        return
                    new_bin = bytearray(current_bin)
                    new_idx = bytearray(current_idx)
                    for slot in sorted(changed_slots):
                        bank = bins[slot]
                        raw = bytes(bank["raw"])
                        raw += b"\0" * ((-len(raw)) % 8)
                        packed = encode_bank(raw, current_bin, bank["offset"])
                        new_offset = align(len(new_bin), 256)
                        new_bin.extend(b"\0" * (new_offset - len(new_bin)))
                        new_bin.extend(packed)
                        struct.pack_into("<QQQ", new_idx, slot * INDEX_RECORD_SIZE,
                                         new_offset, len(raw), len(packed))
                        rebuilt = decode_bank(bytes(new_bin), new_offset, len(packed))
                        if rebuilt != raw:
                            raise ValueError(f"Falha ao verificar o banco {slot} após compactação.")
                    backup_dir = pair["romfs"].parent / ("romfs_backup_texteditor_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
                    backup_dir.mkdir(parents=True, exist_ok=False)
                    shutil.copy2(pair["bin_path"], backup_dir / BIN_NAME)
                    shutil.copy2(pair["idx_path"], backup_dir / IDX_NAME)
                    bin_temp = pair["bin_path"].with_name(pair["bin_path"].name + ".texteditor.tmp")
                    idx_temp = pair["idx_path"].with_name(pair["idx_path"].name + ".texteditor.tmp")
                    try:
                        bin_temp.write_bytes(new_bin)
                        idx_temp.write_bytes(new_idx)
                        os.replace(bin_temp, pair["bin_path"])
                        os.replace(idx_temp, pair["idx_path"])
                    finally:
                        for tmp in (bin_temp, idx_temp):
                            if tmp.exists():
                                tmp.unlink()
                    pair["bin"], pair["idx"] = bytes(new_bin), bytes(new_idx)
                    pair["bin_hash"], pair["idx_hash"] = sha256(pair["bin"]), sha256(pair["idx"])
                    pair["banks"], pair["entries"], pair["stats"] = {}, None, None
                    pair["lookup"], pair["lang_lookup"] = None, None
                    load_entries(pair)
                    self.send_json({"ok": True, "changed": len(edits), "backup": str(backup_dir),
                                    "message": f"Salvo. Backup criado em {backup_dir}"})
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Editor de textos Pokopia disponível em http://127.0.0.1:8765", flush=True)
    threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
