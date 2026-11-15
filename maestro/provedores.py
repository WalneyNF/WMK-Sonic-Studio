"""Gerenciamento local de provedores de IA — sem dependências externas.
As chaves ficam em arquivo local fora do Git; nunca são devolvidas pela API.
"""
import json, os, re, threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
PRIVATE=Path(os.environ.get("WMK_MAESTRO_DATA_DIR",str(Path.home()/".wmk-sonic-studio"/"maestro")))
FILE=PRIVATE/"provedores.json"
LOCK=threading.RLock()
KINDS={
    "ollama":{"nome":"Ollama local","url":"http://127.0.0.1:11434","modelo":"qwen2.5:7b"},
    "groq":{"nome":"Groq","url":"https://api.groq.com/openai/v1","modelo":"llama-3.3-70b-versatile"},
    "openai":{"nome":"OpenAI","url":"https://api.openai.com/v1","modelo":"gpt-4.1-mini"},
    "gemini":{"nome":"Google Gemini","url":"https://generativelanguage.googleapis.com/v1beta","modelo":"gemini-2.5-flash"},
}
MAX_TOKENS=2600

def _write(data):
    PRIVATE.mkdir(parents=True,exist_ok=True)
    tmp=FILE.with_suffix(".tmp")
    with open(tmp,"w",encoding="utf-8") as f:
        os.chmod(tmp,0o600)
        json.dump(data,f,ensure_ascii=False,indent=2)
    os.replace(tmp,FILE)
    try: os.chmod(FILE,0o600)
    except OSError: pass

def _load():
    if not FILE.exists():return {}
    try:
        d=json.loads(FILE.read_text(encoding="utf-8"))
        return d if isinstance(d,dict) else {}
    except (ValueError,OSError): raise ValueError("Configurações de IA inválidas; faça um backup do arquivo antes de corrigir.")

def _safe_config(d):
    return {"id":d["id"],"nome":d["nome"],"tipo":d["tipo"],"modelo":d["modelo"],
            "tem_chave":bool(d.get("chave")),"ativo":bool(d.get("ativo",False)),
            "url":KINDS[d["tipo"]]["url"]}

def list_providers():
    with LOCK:return [_safe_config(v) for v in _load().values()]

def get_provider(pid):
    with LOCK:
        if pid not in _load():raise ValueError("Provedor não cadastrado.")
        return dict(_load()[pid])

def save_provider(data):
    if not isinstance(data,dict):raise ValueError("Cadastro inválido.")
    pid=str(data.get("id","")).strip()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}",pid):raise ValueError("ID deve conter 1 a 40 letras/números.")
    kind=str(data.get("tipo",""))
    if kind not in KINDS:raise ValueError("Provedor não suportado.")
    name=str(data.get("nome") or KINDS[kind]["nome"]).strip()[:80]
    model=str(data.get("modelo") or KINDS[kind]["modelo"]).strip()
    if not model or not re.fullmatch(r"[A-Za-z0-9_.:/+-]{1,120}",model):raise ValueError("Nome do modelo inválido.")
    key=str(data.get("chave") or "")
    if len(key)>512:raise ValueError("Chave muito longa.")
    with LOCK:
        current=_load()
        if not key: key=str(current.get(pid,{}).get("chave",""))
        if kind!="ollama" and not key: raise ValueError("Informe a chave de API do provedor.")
        current[pid]={"id":pid,"tipo":kind,"nome":name,"modelo":model,"chave":key,
                      "ativo":bool(data.get("ativo",False))}
        if current[pid]["ativo"]:
            for k in current:
                if k!=pid: current[k]["ativo"]=False
        _write(current)
        return _safe_config(current[pid])

def remove_provider(pid):
    with LOCK:
        d=_load()
        if pid not in d:raise ValueError("Provedor não cadastrado.")
        del d[pid];_write(d)
        return {"excluido":pid}

def active_provider(pid=None):
    with LOCK:
        d=_load()
        if pid:
            if pid not in d: raise ValueError("Provedor não cadastrado.")
            return dict(d[pid])
        return next((dict(x) for x in d.values() if x.get("ativo")),None)

def _request(url,body,headers):
    # Endpoints são FIXOS e pré-autorizados, sem URLs arbitrárias do usuário (SSRF).
    req=Request(url,data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type":"application/json",**headers},method="POST")
    try:
        with urlopen(req,timeout=40) as resp:
            payload=resp.read(1024*1024)
        return json.loads(payload)
    except HTTPError as e:
        raise ValueError(f"API retornou HTTP {e.code}. Confira modelo, chave e limites do plano.") from None
    except (URLError,TimeoutError) as e:
        raise ValueError("Não foi possível conectar ao provedor. Verifique internet/Ollama e URL configurada.") from None

def ask(provider,prompt,system="Você é um assistente musical. Responda em português brasileiro."):
    kind=provider["tipo"];model=provider["modelo"];key=provider.get("chave","")
    if kind=="ollama":
        data=_request(KINDS[kind]["url"]+"/api/chat",
              {"model":model,"stream":False,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],
               "options":{"num_predict":MAX_TOKENS}}, {})
        return str(data.get("message",{}).get("content",""))[:60000]
    if kind in ("groq","openai"):
        data=_request(KINDS[kind]["url"]+"/chat/completions",
              {"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],
               "max_completion_tokens":MAX_TOKENS},
              {"Authorization":"Bearer "+key})
        try:return str(data["choices"][0]["message"]["content"])[:60000]
        except (KeyError,IndexError,TypeError):raise ValueError("Resposta inesperada da API.")
    if kind=="gemini":
        data=_request(KINDS[kind]["url"]+"/models/"+model+":generateContent",
              {"contents":[{"role":"user","parts":[{"text":system+"\n\n"+prompt}]}],
               "generationConfig":{"maxOutputTokens":MAX_TOKENS}},
              {"x-goog-api-key":key})
        try:return "".join(x.get("text","") for x in data["candidates"][0]["content"]["parts"])[:60000]
        except (KeyError,IndexError,TypeError):raise ValueError("Resposta inesperada da API.")
    raise ValueError("Provedor não suportado.")

def test_provider(pid):
    p=get_provider(pid)
    answer=ask(p,"Responda com uma única palavra: música.")
    if not answer.strip():raise ValueError("O modelo retornou uma resposta vazia.")
    return {"ok":True,"provedor":p["nome"],"modelo":p["modelo"],"resposta":answer[:140]}
