"""WMK Maestro Agent: ações musicais seguras sobre arquivos MIDI existentes.
Não executa código da IA e não controla ainda o motor C++/JUCE.
Preserva o arquivo original; cada aplicação cria nova versão MIDI e registro JSON.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from partituras import parse_midi, to_midi
from provedores import active_provider, ask
from maestro import OUTPUT

ACTIONS={"transpor","alterar_tempo","ajustar_dinamica","remover_pista"}
SYSTEM="""Você é um agente que interpreta solicitações para editar notas MIDI.
Retorne SOMENTE um objeto JSON com "acoes": uma lista de até 4 ações.
As ações permitidas são:
{"tipo":"transpor","semitons":-12 a 12,"pista":número opcional (1 em diante)}
{"tipo":"alterar_tempo","bpm":40 a 220}
{"tipo":"ajustar_dinamica","percentual":25 a 175,"pista":número opcional}
{"tipo":"remover_pista","pista":número 1 em diante}
Não retorne Python, código executável, caminhos, comandos ou ações fora da lista.
Se o pedido for vago, responda {"acoes":[]}."""

def _filename(name):
    if not isinstance(name,str) or not re.fullmatch(r"WMK_[0-9_]+\.mid",name):
        raise ValueError("Escolha um MIDI WMK válido.")
    p=(OUTPUT/name).resolve()
    if p.parent!=OUTPUT.resolve() or not p.is_file():
        raise ValueError("Arquivo MIDI não encontrado.")
    if p.stat().st_size>1024*1024:
        raise ValueError("MIDI acima de 1 MB.")
    return p

def validate(actions,parts):
    if not isinstance(actions,list) or len(actions)>4:
        raise ValueError("Máximo de quatro ações por execução.")
    checked=[]
    for raw in actions:
        if not isinstance(raw,dict) or raw.get("tipo") not in ACTIONS:
            raise ValueError("Ação não permitida.")
        kind=raw["tipo"]
        a={"tipo":kind}
        if kind=="alterar_tempo":
            val=raw.get("bpm")
            if type(val)!=int or not 40<=val<=220:raise ValueError("BPM fora de 40 a 220.")
            a["bpm"]=val
        else:
            track=raw.get("pista")
            if track is not None:
                if type(track)!=int or not 1<=track<=len(parts):
                    raise ValueError("Pista inválida.")
                a["pista"]=track
            if kind=="remover_pista":
                if track is None:raise ValueError("Informe o número da pista.")
            elif kind=="transpor":
                val=raw.get("semitons")
                if type(val)!=int or not -12<=val<=12:raise ValueError("Transpose entre -12 e 12.")
                a["semitons"]=val
            elif kind=="ajustar_dinamica":
                val=raw.get("percentual")
                if type(val)!=int or not 25<=val<=175:raise ValueError("Dinâmica entre 25 e 175%.")
                a["percentual"]=val
        checked.append(a)
    return checked

def _apply(score,actions):
    clone=json.loads(json.dumps(score,ensure_ascii=False))
    for a in actions:
        kind=a["tipo"]
        if kind=="alterar_tempo":
            clone["bpm"]=a["bpm"]
            continue
        selected=[a["pista"]-1] if "pista" in a else range(len(clone["instrumentos"]))
        if kind=="remover_pista":
            clone["instrumentos"].pop(a["pista"]-1)
            continue
        for index in selected:
            part=clone["instrumentos"][index]
            # Percussão GM usa notas como códigos de instrumentos; não transpor!
            is_drums=any(x in part["instrumento"].lower() for x in ("percuss", "drum", "bateria"))
            for note in part["notas"]:
                if kind=="transpor" and not is_drums:
                    note["midi"]=max(0,min(127,note["midi"]+a["semitons"]))
                if kind=="ajustar_dinamica":
                    note["velocidade"]=max(1,min(127,round(note.get("velocidade",90)*a["percentual"]/100)))
    clone["total_notas"]=sum(len(p["notas"]) for p in clone["instrumentos"])
    return clone

def plan(filename,request,provider_id=None,use_ai=False):
    source=_filename(filename)
    score=parse_midi(source.read_bytes())
    parts=[{"pista":i+1,"nome":x["instrumento"],"notas":x["total_notas"]}
           for i,x in enumerate(score["instrumentos"])]
    if use_ai:
        p=active_provider(provider_id)
        if not p:raise ValueError("Cadastre um provedor de IA antes de usar a interpretação automática.")
        data=ask(p,json.dumps({"pedido":str(request)[:1200],"pistas":parts,"bpm":score["bpm"]},
                              ensure_ascii=False),system=SYSTEM)
        try:
            parsed=json.loads(data.strip().removeprefix(chr(96)*3+"json").removesuffix(chr(96)*3).strip())
        except ValueError:raise ValueError("A IA não retornou um plano JSON válido.")
        actions=parsed.get("acoes",[]) if isinstance(parsed,dict) else None
    else:
        # Modo sem IA: comandos claros em português; não adivinhar alterações.
        text=str(request).lower()
        actions=[]
        m=re.search(r"(?:tempo|bpm)\s*(?:para|=|:)?\s*(\d{2,3})",text)
        if m:actions.append({"tipo":"alterar_tempo","bpm":int(m.group(1))})
        m=re.search(r"(?:transpor|subir|descer)\s*(\d{1,2})\s*semitons?",text)
        if m:
            n=int(m.group(1))
            actions.append({"tipo":"transpor","semitons":-n if "descer" in text else n})
        m=re.search(r"(?:volume|dinâmica|dinamica|velocidade)\s*(?:para|=|:)\s*(\d{2,3})\s*%",text)
        if m:actions.append({"tipo":"ajustar_dinamica","percentual":int(m.group(1))})
    actions=validate(actions,parts)
    return {"arquivo":filename,"pedido":str(request)[:1200],"acoes":actions,
            "pistas":parts,"bpm":score["bpm"],
            "observacao":"Prévia: nenhuma alteração foi salva. Confira as ações antes de aplicar. Ações não suportadas são rejeitadas."}

def apply(filename,actions):
    source=_filename(filename)
    score=parse_midi(source.read_bytes())
    actions=validate(actions,score["instrumentos"])
    if not actions:raise ValueError("Nenhuma ação válida foi fornecida.")
    updated=_apply(score,actions)
    if not updated["instrumentos"]:raise ValueError("Não é possível remover todas as pistas.")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    name="WMK_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".mid"
    dest=OUTPUT/name
    dest.write_bytes(to_midi(updated))
    # Registra proveniência, parâmetros e método de desfazer sem guardar segredo da IA.
    record={"origem":filename,"nova_versao":name,"acoes":actions,
            "desfazer":"Retorne ao arquivo original: "+filename}
    dest.with_suffix(".json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    return record
