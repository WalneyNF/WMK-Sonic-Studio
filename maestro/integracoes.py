#!/usr/bin/env python3
"""Integração local com MuseScore Studio e preparação de prompt para Suno.
O Suno não é acessado por API nesta versão; nenhum scraping ou download não autorizado.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_INPUT={".mid",".midi",".musicxml",".xml",".mxl",".mscz",".mscx"}
SUPPORTED_OUTPUT={".musicxml",".mxl",".pdf",".mid",".midi",".wav",".ogg"}
INSTRUMENTS={"sanfona":"accordion","acordeão":"accordion","acordeao":"accordion",
             "violão":"acoustic guitar","violao":"acoustic guitar","guitarra":"electric guitar",
             "piano":"piano","flauta":"flute","bateria":"drums","violino":"violin",
             "baixo":"bass"}
STYLES={"medieval":"medieval fantasy","batalha":"epic battle","aventura":"adventure",
        "terror":"dark atmospheric","alegre":"uplifting folk","rpg":"fantasy RPG"}

def find_musescore(user_path=None):
    if user_path:
        exe=Path(user_path).expanduser().resolve()
        if not exe.is_file(): raise ValueError("Executável do MuseScore não encontrado.")
        return str(exe)
    for name in ("MuseScore4.exe","MuseScore.exe","MuseScore4","musescore","mscore"):
        found=shutil.which(name)
        if found:return found
    for root in (Path("C:/Program Files/MuseScore 4/bin"),
                 Path("C:/Program Files/MuseScore 4"),
                 Path("C:/Program Files (x86)/MuseScore 4/bin")):
        for name in ("MuseScore4.exe","MuseScore.exe"):
            if (root/name).is_file():return str(root/name)
    raise ValueError("MuseScore Studio não localizado. Use --musescore com o caminho do executável.")

def convert(source,target,musescore=None,timeout=120):
    src=Path(source).expanduser().resolve()
    dst=Path(target).expanduser().resolve()
    if not src.is_file():raise ValueError("Arquivo de origem não encontrado.")
    if src.suffix.lower() not in SUPPORTED_INPUT:raise ValueError("Formato de entrada não permitido.")
    if dst.suffix.lower() not in SUPPORTED_OUTPUT:raise ValueError("Formato de saída não permitido.")
    if src==dst:raise ValueError("Origem e destino devem ser diferentes.")
    if src.stat().st_size>64*1024*1024:raise ValueError("Arquivo de origem acima de 64 MB.")
    if not dst.parent.is_dir():raise ValueError("Pasta de destino não encontrada.")
    exe=find_musescore(musescore)
    # Lista de argumentos, sem shell=True; caminho fornecido somente na máquina local.
    proc=subprocess.run([exe,"-o",str(dst),str(src)],capture_output=True,text=True,
                        errors="replace",timeout=timeout,check=False)
    if proc.returncode!=0 or not dst.is_file() or dst.stat().st_size==0:
        raise RuntimeError("MuseScore não concluiu a conversão. "+(proc.stderr or proc.stdout)[-450:])
    return {"origem":str(src),"saida":str(dst),"bytes":dst.stat().st_size}

def suno_prompt(description,bpm=None,instrumental=True):
    text=" ".join(str(description).strip().split())
    if not 1<=len(text)<=1800:raise ValueError("Descreva o estilo desejado (até 1800 caracteres).")
    low=text.lower()
    inst=list(dict.fromkeys(english for portuguese,english in INSTRUMENTS.items() if portuguese in low))
    mood=list(dict.fromkeys(english for portugues,english in STYLES.items() if portugues in low))
    tags=[*mood,*inst]
    if bpm is not None:
        if not isinstance(bpm,int) or not 40<=bpm<=220:raise ValueError("BPM deve ficar entre 40 e 220.")
        tags.append(f"{bpm} BPM")
    tags.extend(["original game soundtrack","instrumental only" if instrumental else "song with vocals",
                 "clear melodic structure","seamless loop-friendly ending"])
    # Não solicita reprodução de canções protegidas ou imitação fiel de artistas.
    return {"titulo":"WMK Sonic Studio — prompt para Suno",
            "descricao_original":text,"estilo_sugerido":", ".join(tags),
            "letra_ou_instrucoes":("Instrumental. No vocals. " if instrumental else "")+
                "Compose an original soundtrack based on this brief: "+text+
                ". Create a clear intro, memorable theme, contrasting section, and a natural ending.",
            "modo":"instrumental" if instrumental else "vocal",
            "aviso":"Cole manualmente o texto no site Suno. Não existe integração automática via API aqui."}

def main(argv=None):
    p=argparse.ArgumentParser(description="WMK: conversor MuseScore e prompts para Suno")
    sub=p.add_subparsers(dest="command",required=True)
    m=sub.add_parser("converter",help="Converter MIDI/MusicXML/MSCZ por meio do MuseScore instalado")
    m.add_argument("origem");m.add_argument("destino");m.add_argument("--musescore")
    s=sub.add_parser("suno",help="Preparar prompt para colar no site Suno")
    s.add_argument("descricao");s.add_argument("--bpm",type=int)
    s.add_argument("--vocal",action="store_true")
    s.add_argument("--salvar",help="Caminho .json para o resultado")
    args=p.parse_args(argv)
    try:
        if args.command=="converter":
            result=convert(args.origem,args.destino,args.musescore)
        else:
            result=suno_prompt(args.descricao,args.bpm,not args.vocal)
            if args.salvar:
                dest=Path(args.salvar).expanduser().resolve()
                if dest.suffix.lower()!=".json":raise ValueError("Use extensão .json em --salvar")
                dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,RuntimeError,subprocess.TimeoutExpired,OSError) as e:
        print("Erro:",e,file=sys.stderr);return 1

if __name__=="__main__":sys.exit(main())
