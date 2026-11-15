"""WMK Maestro Multiagente — pipeline de produção musical auditável.
Todos os prompts são configuráveis. Sem execução de código arbitrário pela IA.
A geração musical é MIDI experimental; não renderiza áudio nem opera a DAW.
"""
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import maestro
from compositor_ia import compose_with_provider
from provedores import PRIVATE, active_provider, ask

AGENTS = [
 {"id":"diretor","nome":"Diretor musical","funcao":"Entender a ideia e definir direção criativa",
  "prompt":"Você é diretor musical de jogos e cinema. Transforme o pedido em um briefing original e prático. Defina clima, estilo, andamento sugerido, instrumentos, começo, clímax e encerramento. Responda em português brasileiro, no máximo 250 palavras."},
 {"id":"teoria","nome":"Harmonia e teoria","funcao":"Planejar tonalidade, acordes e ritmo",
  "prompt":"Você é especialista em harmonia. Sugira tonalidade, progressão de acordes coerente, métrica, ritmo e motivo melódico para o briefing. Explique sem termos difíceis e produza orientações concretas para o compositor MIDI. Até 300 palavras."},
 {"id":"arranjador","nome":"Arranjador","funcao":"Distribuir instrumentos e estruturar a trilha",
  "prompt":"Você é arranjador musical. Defina papéis e regiões de cada instrumento (melodia, acordes, baixo, bateria), dinâmica, estrutura por compassos e transições. Limite a quatro pistas MIDI nesta primeira versão; seja realista. Até 300 palavras."},
 {"id":"compositor","nome":"Compositor MIDI","funcao":"Gerar notas MIDI editáveis",
  "prompt":"Você é compositor de trilhas originais. Use o briefing, a harmonia e o arranjo das etapas anteriores como referência para criar uma composição MIDI original, com andamento, compassos, melodia, harmonia e ritmo. Não reproduza melodias protegidas."},
 {"id":"revisor","nome":"Revisor musical","funcao":"Avaliar e apontar problemas de composição",
  "prompt":"Você é revisor musical. Analise os dados conhecidos do MIDI e do briefing; identifique riscos de harmonia, ritmo, repetição excessiva, uso de instrumentos e pontos de melhoria. Não afirme ter escutado o áudio. Classifique como revisão textual, não prova de qualidade. Até 300 palavras."},
 {"id":"professor","nome":"Professor musical","funcao":"Explicar ao iniciante o resultado",
  "prompt":"Você é professor musical paciente e preciso. Explique em português brasileiro o significado de BPM, compasso, pistas MIDI e função de cada instrumento nesta composição. Dê três exercícios fáceis. Não invente análises de áudio. Até 300 palavras."}
]
BASE = PRIVATE / "agentes.json"
LOCK = threading.RLock()
MAX_STAGE_TEXT=3200
MAX_CONTEXT=4800

def default_config():
    return {"versao":1,"agentes":[dict(a,habilitado=True,provedor="") for a in AGENTS]}

def _load():
    if not BASE.is_file():return default_config()
    try:
        data=json.loads(BASE.read_text(encoding="utf-8"))
    except (OSError,ValueError) as exc: raise ValueError("Configuração dos agentes inválida.") from exc
    if not isinstance(data,dict) or not isinstance(data.get("agentes"),list):
        raise ValueError("Configuração dos agentes inválida.")
    return data

def read_config():
    with LOCK:return _load()

def save_config(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get("agentes"),list):
        raise ValueError("Cadastro de agentes inválido.")
    defaults={a["id"]:a for a in AGENTS}
    incoming=payload["agentes"]
    if len(incoming)!=len(AGENTS) or {x.get("id") for x in incoming if isinstance(x,dict)}!=set(defaults):
        raise ValueError("Todos os agentes precisam estar presentes, com IDs conhecidos.")
    final=[]
    for item in incoming:
        original=defaults[item["id"]]
        prompt=item.get("prompt")
        if not isinstance(prompt,str) or not 20<=len(prompt)<=6000:
            raise ValueError("Cada prompt deve ter de 20 a 6000 caracteres.")
        provider=item.get("provedor","")
        if not isinstance(provider,str) or (provider and not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}",provider)):
            raise ValueError("ID do provedor inválido.")
        final.append({**original,"prompt":prompt,"provedor":provider,"habilitado":bool(item.get("habilitado",True))})
    with LOCK:
        PRIVATE.mkdir(parents=True,exist_ok=True)
        temp=BASE.with_suffix(".tmp")
        temp.write_text(json.dumps({"versao":1,"agentes":final},ensure_ascii=False,indent=2),encoding="utf-8")
        try:os.chmod(temp,0o600)
        except OSError:pass
        os.replace(temp,BASE)
    return {"ok":True,"quantidade":len(final)}

def _provider(agent,request_id):
    pid=agent.get("provedor") or request_id or None
    p=active_provider(pid)
    if not p: raise ValueError("Cadastre e ative um provedor para a produção com IA.")
    return p

def _stage_ask(agent,provider,brief,history):
    context="\n\n".join((x["nome"]+": "+x["resultado"]) for x in history if isinstance(x.get("resultado"),str))
    prompt="PEDIDO DO USUÁRIO:\n"+brief+"\n\nETAPAS ANTERIORES:\n"+context[-MAX_CONTEXT:]
    answer=ask(provider,prompt,system=agent["prompt"])
    if not answer.strip():raise ValueError("Etapa "+agent["nome"]+" retornou resposta vazia.")
    return answer[:MAX_STAGE_TEXT]

def run_pipeline(brief,mode="ia",provider_id=None):
    if not isinstance(brief,str) or not 10<=len(brief.strip())<=2000:
        raise ValueError("Descreva sua música em 10 a 2000 caracteres.")
    if mode not in ("ia","offline"):raise ValueError("Modo inválido.")
    config=read_config()
    stages=[];music=None;warnings=[]
    for agent in config["agentes"]:
        if not agent.get("habilitado",True):
            stages.append({"id":agent["id"],"nome":agent["nome"],"status":"ignorado","resultado":"Etapa desativada pelo usuário."})
            continue
        entry={"id":agent["id"],"nome":agent["nome"],"status":"concluido"}
        try:
            if agent["id"]=="compositor":
                if mode=="ia":
                    p=_provider(agent,provider_id)
                    context="\n".join(x["resultado"] for x in stages if x["status"]=="concluido")[-MAX_CONTEXT:]
                    # O prompt do compositor é EDITÁVEL e faz parte do pedido musical.
                    music=compose_with_provider((agent["prompt"][:700]+"\nBriefing:\n"+brief[:700]+"\nContexto:\n"+context[:500])[:1950],p["id"])
                else:
                    music=maestro.compose({"prompt":brief,"bars":16})
                entry["resultado"]="MIDI criado: "+music["arquivo"]+"; "+str(music["notas"])+" notas em "+str(len(music["instrumentos"]))+" pistas."
            elif mode=="ia":
                p=_provider(agent,provider_id)
                context=brief
                if music and agent["id"] in ("revisor","professor"):
                    context+="\nRESUMO DE COMPOSIÇÃO GERADA: "+json.dumps(music,ensure_ascii=False)
                entry["resultado"]=_stage_ask(agent,p,context,stages)
            else:
                descriptions={
                    "diretor":"Briefing: "+brief,
                    "teoria":"Experimento sem IA: as notas são construídas por regras simples; verifique tonalidade e acordes na DAW.",
                    "arranjador":"Arranjo padrão: melodia, acompanhamento, baixo e percussão, conforme os instrumentos reconhecidos.",
                    "revisor":"Revisão offline: confirme consonância, ritmo, volumes e transições ouvindo no Sonic Studio. Sem análise sonora automática.",
                    "professor":"BPM é a velocidade; MIDI representa notas e eventos, não áudio. Exercício: altere uma nota e compare."
                }
                entry["resultado"]=descriptions.get(agent["id"],"")
        except (ValueError,TimeoutError) as exc:
            entry["status"]="erro"
            entry["resultado"]=str(exc)[:500]
            warnings.append(agent["nome"]+": "+entry["resultado"])
            stages.append(entry)
            if agent["id"]=="compositor":break
            continue
        stages.append(entry)
    if not music:
        warnings.append("Nenhum MIDI foi gerado. Confira o compositor e o provedor.")
    run_id=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")+uuid4().hex[:8]
    dossier={"id":run_id,"criado_em":datetime.now(timezone.utc).isoformat(),
            "pedido":brief,"modo":mode,"etapas":stages,"musica":music,"avisos":warnings}
    folder=maestro.OUTPUT/"dossies"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/("WMK_"+run_id+".json")).write_text(json.dumps(dossier,ensure_ascii=False,indent=2),encoding="utf-8")
    dossier["dossie"]="WMK_"+run_id+".json"
    return dossier
