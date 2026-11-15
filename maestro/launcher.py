"""Iniciador Windows do WMK Maestro IA."""
import argparse
import sys
import threading
import webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer
import maestro

def healthcheck():
    import agente, compositor_ia, integracoes, partituras, pipeline, provedores
    import tempfile
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as d:
        with patch.object(maestro,"OUTPUT",Path(d)):
            song=maestro.compose({"prompt":"Música medieval com sanfona e violão","bars":4})
            score=partituras.parse_midi((Path(d)/song["arquivo"]).read_bytes())
            if score["total_notas"]<=0:raise RuntimeError("Teste MIDI sem notas.")
    for html in ("index.html","pipeline.html","partituras.html","provedores.html","integracoes.html","agente.html"):
        if not (maestro.HERE/html).is_file():
            raise RuntimeError("Página ausente no pacote: "+html)
    print("WMK Maestro IA: autoteste aprovado.")
    return 0

def main():
    parser=argparse.ArgumentParser(description="WMK Maestro IA - Estúdio musical com agentes")
    parser.add_argument("--port",type=int,default=8768)
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--no-browser",action="store_true")
    args=parser.parse_args()
    if args.selftest:return healthcheck()
    if not 1024<=args.port<=65535:parser.error("Porta inválida.")
    url=f"http://127.0.0.1:{args.port}/pipeline.html"
    try:
        server=ThreadingHTTPServer(("127.0.0.1",args.port),maestro.Handler)
    except OSError as exc:
        print("Não foi possível iniciar o servidor local:",exc,file=sys.stderr)
        return 1
    if not args.no_browser:
        threading.Timer(1.2,lambda:webbrowser.open(url)).start()
    print("WMK Maestro IA iniciado:",url,flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0

if __name__=="__main__":
    sys.exit(main())
