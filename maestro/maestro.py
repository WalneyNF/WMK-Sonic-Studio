#!/usr/bin/env python3
"""WMK Maestro IA: composição MIDI local, com IA Ollama opcional; sem dependências externas."""
import json, os, re, random, struct, sys
from importlib import import_module
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "composicoes"
PPQ = 480
STYLES = {
    "medieval": {"bpm": 95, "instruments": ["Sanfona", "Violao", "Baixo", "Percussao"], "mode": "minor"},
    "aventura": {"bpm": 115, "instruments": ["Flauta", "Violao", "Baixo", "Percussao"], "mode": "major"},
    "batalha": {"bpm": 145, "instruments": ["Metais", "Cordas", "Baixo", "Percussao"], "mode": "minor"},
    "terror": {"bpm": 72, "instruments": ["Cordas", "Piano", "Baixo", "Percussao"], "mode": "minor"},
    "alegre": {"bpm": 125, "instruments": ["Sanfona", "Violao", "Baixo", "Percussao"], "mode": "major"},
}
PROGRAMS = {"Sanfona": 21, "Violao": 24, "Guitarra": 26, "Flauta": 73, "Piano": 0,
            "Cordas": 48, "Metais": 61, "Baixo": 32, "Percussao": 0}
# General MIDI programs, zero based. Channel 10 (index 9) is percussion.
CHORDS = {"major":[0,5,7,0], "minor":[0,5,3,7]}
SCALES = {"major":[0,2,4,5,7,9,11], "minor":[0,2,3,5,7,8,10]}

def vlq(n):
    if n < 0: raise ValueError("intervalo MIDI negativo")
    b = [n & 0x7f]
    while (n := n >> 7):
        b.insert(0, (n & 0x7f) | 0x80)
    return bytes(b)

def chunk(t, data):
    return t + struct.pack(">I", len(data)) + data

def meta(t, payload):
    return b"\xff" + bytes([t]) + vlq(len(payload)) + payload

def track(events):
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    data, last = bytearray(), 0
    for tick, _priority, msg in events:
        data += vlq(tick - last) + msg
        last = tick
    data += b"\x00\xff\x2f\x00"
    return chunk(b"MTrk", data)

def parse_prompt(text):
    text = text.lower()
    style = next((k for k in STYLES if k in text), "aventura")
    instruments = [name for name in PROGRAMS if name.lower() in text or
                   (name == "Sanfona" and ("acorde" in text or "sanfona" in text)) or
                   (name == "Violao" and "violão" in text)]
    bpm = re.search(r"\b(\d{2,3})\s*bpm\b", text)
    bars = re.search(r"\b(\d{1,2})\s*compassos\b", text)
    duration = re.search(r"\b(\d{1,3})\s*(?:segundos?|s)\b", text)
    return style, instruments, int(bpm.group(1)) if bpm else None, int(bars.group(1)) if bars else None, int(duration.group(1)) if duration else None

def compose(request):
    prompt = str(request.get("prompt", "")).strip()
    if not prompt or len(prompt) > 2000:
        raise ValueError("Descreva sua música em até 2.000 caracteres.")
    style, found, bp, bars_input, seconds = parse_prompt(prompt)
    cfg = STYLES[style]
    bpm = int(request.get("bpm") or bp or cfg["bpm"])
    if not 40 <= bpm <= 220: raise ValueError("BPM deve ficar entre 40 e 220.")
    bars = int(request.get("bars") or bars_input or (round(seconds * bpm / 240) if seconds else 16))
    if not 4 <= bars <= 64: raise ValueError("Use entre 4 e 64 compassos.")
    instruments = found[:4] if found else cfg["instruments"]
    if len(instruments) < 2:
        instruments = list(dict.fromkeys(instruments + cfg["instruments"]))[:4]
    if "Percussao" not in instruments:
        instruments = (instruments[:3] + ["Percussao"])
    mode = cfg["mode"]
    scale = SCALES[mode]
    chords = CHORDS[mode]
    rng = random.Random(int(request.get("seed", 42)))
    events = []
    tempo = round(60000000 / bpm)
    master = [(0, 0, meta(0x51, tempo.to_bytes(3, "big"))),
              (0, 0, meta(0x58, bytes([4, 2, 24, 8])))]
    events.append(track(master))
    notes_count = 0
    for idx, instrument in enumerate(instruments):
        ch = 9 if instrument == "Percussao" else idx if idx < 9 else idx+1
        ev = [(0, 0, meta(0x03, instrument.encode("utf-8")))]
        ev.append((0, 0, bytes([0xC0 | ch, PROGRAMS[instrument]])))
        for bar in range(bars):
            degree = chords[(bar // 2) % len(chords)]
            base = (48 if instrument == "Baixo" else 60) + degree
            for step in range(4 if instrument != "Violao" else 8):
                start = bar * 4 * PPQ + step * (PPQ if instrument != "Violao" else PPQ//2)
                if instrument == "Percussao":
                    # GM drums: kick 36, snare 38, closed hi-hat 42
                    pitches = [36, 42, 38, 42]
                    pitch = pitches[step]
                    length = PPQ // 4
                elif instrument == "Baixo":
                    pitch = base - 12 + (7 if step == 2 else 0)
                    length = PPQ * 3 // 4
                elif instrument == "Violao":
                    pitch = base + [0, 4 if mode == "major" else 3, 7, 12][step % 4]
                    length = PPQ // 3
                else:
                    pitch = base + rng.choice(scale) + (0 if instrument != "Flauta" else 12)
                    length = PPQ * (1 if instrument == "Sanfona" else 3) // 4
                velocity = 75 + rng.randrange(0, 21)
                ev.append((start, 2, bytes([0x90 | ch, min(127, pitch), velocity])))
                ev.append((start + length, 1, bytes([0x80 | ch, min(127, pitch), 0])))
                notes_count += 1
        events.append(track(ev))
    payload = b"MThd" + struct.pack(">IHHH", 6, 1, len(events), PPQ) + b"".join(events)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    filename = "WMK_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".mid"
    (OUTPUT / filename).write_bytes(payload)
    result = {"arquivo": filename, "bpm": bpm, "compassos": bars, "estilo": style,
              "instrumentos": instruments, "notas": notes_count,
              "duracao_segundos": round(bars * 240 / bpm, 1),
              "observacao": "MIDI editável; o timbre real depende dos instrumentos/plugins configurados na DAW."}
    (OUTPUT / filename.replace(".mid", ".json")).write_text(
        json.dumps({"pedido": prompt, "resultado": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

def ollama_suggest(prompt, model="qwen2.5:7b"):
    # IA apenas interpreta o pedido. Nunca executa código ou acessa arquivos.
    model = str(model)[:80]
    body = json.dumps({"model":model,"stream":False, "format":"json",
        "prompt":"Retorne SOMENTE JSON com 'prompt' (descrição curta de estilo, instrumentos e BPM para música MIDI). "
                 "Preserve intenções e não invente informações sensíveis. Pedido: " + prompt}).encode()
    req = Request("http://127.0.0.1:11434/api/generate", data=body,
                  headers={"Content-Type":"application/json"}, method="POST")
    with urlopen(req, timeout=45) as response:
        result = json.loads(response.read(100000))
    suggestion = json.loads(result.get("response", "{}"))
    return str(suggestion.get("prompt") or prompt)[:2000]

class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
    def _allowed_origin(self):
        from urllib.parse import urlsplit
        origin=self.headers.get("Origin","")
        if not origin: return True
        parsed=urlsplit(origin)
        host=self.headers.get("Host","")
        return parsed.scheme=="http" and parsed.netloc==host and parsed.hostname in ("127.0.0.1","localhost")
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, (HERE/"index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/agente.html":
            self.send(200, (HERE/"agente.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/integracoes.html":
            self.send(200, (HERE/"integracoes.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/provedores.html":
            self.send(200, (HERE/"provedores.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/provedores":
            from provedores import list_providers
            self.send(200, json.dumps(list_providers(),ensure_ascii=False).encode())
        elif self.path == "/partituras.html":
            self.send(200, (HERE/"partituras.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/health":
            self.send(200, b'{"status":"ok","produto":"WMK Maestro IA"}')
        elif re.fullmatch(r"/arquivos/WMK_[0-9_]+\.mid", self.path):
            filename = self.path.rsplit("/", 1)[-1]
            p = OUTPUT / filename
            if p.is_file(): self.send(200, p.read_bytes(), "audio/midi")
            else: self.send(404, b'{"erro":"Arquivo nao encontrado"}')
        else: self.send(404, b'{"erro":"Nao encontrado"}')
    def do_POST(self):
        if self.path not in ("/api/compose", "/api/partituras", "/api/provedores/salvar", "/api/provedores/excluir", "/api/provedores/testar", "/api/ensinar", "/api/agente/planejar", "/api/agente/aplicar"):
            return self.send(404, b'{"erro":"Nao encontrado"}')
        if not self._allowed_origin():
            return self.send(403, b'{"erro":"Origem nao autorizada"}')
        try:
            size = int(self.headers.get("Content-Length", "0"))
            max_size = 2 * 1024 * 1024 if self.path == "/api/partituras" else 8192
            if not 0 < size <= max_size: raise ValueError("Pedido muito grande ou vazio.")
            if self.path.startswith("/api/agente/"):
                if size > 8192: raise ValueError("Pedido muito grande.")
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict): raise ValueError("Pedido inválido.")
                from agente import plan, apply
                if self.path == "/api/agente/planejar":
                    result=plan(str(data.get("arquivo","")),str(data.get("pedido","")),data.get("provedor") or None,bool(data.get("usar_ia",False)))
                else:
                    result=apply(str(data.get("arquivo","")),data.get("acoes"))
                self.send(200,json.dumps(result,ensure_ascii=False).encode())
                return
            if self.path.startswith("/api/provedores/") or self.path == "/api/ensinar":
                if size > 8192: raise ValueError("Pedido muito grande.")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data,dict): raise ValueError("Pedido inválido.")
                if self.path == "/api/provedores/salvar":
                    from provedores import save_provider
                    result=save_provider(data)
                elif self.path == "/api/provedores/excluir":
                    from provedores import remove_provider
                    result=remove_provider(str(data.get("id","")))
                elif self.path == "/api/provedores/testar":
                    from provedores import test_provider
                    result=test_provider(str(data.get("id","")))
                else:
                    from compositor_ia import teach
                    result=teach(data.get("pergunta",""),data.get("provedor") or None,data.get("contexto",""))
                self.send(200, json.dumps(result,ensure_ascii=False).encode())
                return
            if self.path == "/api/partituras":
                from partituras import parse_musicxml, parse_midi, to_midi
                import base64
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict): raise ValueError("Pedido inválido.")
                filename = str(data.get("nome", ""))[:180]
                if not filename.lower().endswith((".mid", ".midi", ".musicxml", ".xml", ".mxl")):
                    raise ValueError("Use arquivos MIDI, MusicXML ou MXL.")
                binary = base64.b64decode(data.get("conteudo", ""), validate=True)
                if len(binary) > 1024 * 1024: raise ValueError("Arquivo acima do limite de 1 MB.")
                score = parse_midi(binary) if filename.lower().endswith((".mid", ".midi")) else parse_musicxml(binary, filename)
                if score["formato"] == "MusicXML":
                    OUTPUT.mkdir(parents=True, exist_ok=True)
                    outname = "WMK_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".mid"
                    (OUTPUT/outname).write_bytes(to_midi(score))
                    score["arquivo"] = outname
                # Limita visualização a 120 primeiras notas por instrumento;
                # não altera o MIDI completo exportado.
                for p in score["instrumentos"]:
                    p["notas"] = p["notas"][:120]
                self.send(200, json.dumps(score, ensure_ascii=False).encode())
                return
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict): raise ValueError("Pedido invalido.")
            if data.get("modo") == "ia":
                from compositor_ia import compose_with_provider
                result = compose_with_provider(data.get("prompt",""),data.get("provedor") or None)
            else:
                if data.get("usar_ollama"):
                    data["prompt"] = ollama_suggest(str(data.get("prompt","")), data.get("modelo","qwen2.5:7b"))
                result = compose(data)
            self.send(200, json.dumps(result, ensure_ascii=False).encode())
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            self.send(400, json.dumps({"erro":str(e)},ensure_ascii=False).encode())
        except Exception as e:
            self.send(502, json.dumps({"erro":"Falha de processamento/IA: "+str(e)},ensure_ascii=False).encode())
    def log_message(self, fmt, *args): pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WMK Maestro IA - ferramenta local para gerar trilhas MIDI")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error("Porta inválida.")
    print(f"WMK Maestro IA: http://127.0.0.1:{args.port}  (Ctrl+C encerra)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
