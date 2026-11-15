"""Composição MIDI orientada por notas produzidas por LLM, com validação rígida."""
import json, re, struct
from datetime import datetime
import maestro
from provedores import ask, active_provider

INSTRUMENTS=list(maestro.PROGRAMS)
SYSTEM="""Você é compositor especializado em trilhas para jogos.
Responda SOMENTE um objeto JSON válido, sem markdown:
{"titulo":"...","bpm":110,"compassos":8,"partes":[{"instrumento":"Sanfona","notas":[{"inicio":0,"duracao":1,"altura":60,"velocidade":90}]}]}
"inicio" e "duracao" são em TEMPOS/BEATS (semicolcheia=0.25, semínima=1, compasso 4/4=4 tempos).
Altura MIDI entre 0 e 127. Velocidade entre 1 e 127. Máximo 4 partes, 128 notas por parte.
Instrumentos permitidos: Sanfona, Violao, Guitarra, Flauta, Piano, Cordas, Metais, Baixo, Percussao.
Na Percussao, alturas MIDI padrão GM: 36 bumbo, 38 caixa, 42 chimbal.
Crie melodia interessante, acordes coerentes e ritmo. Não produza textos fora do JSON.
Não mencione que o resultado é profissional se não puder garantir."""

def decode_json(text):
    text=text.strip()
    fence=chr(96)*3
    if text.startswith(fence):
        text=text.split("\n",1)[-1].rsplit(fence,1)[0].strip()
    try:return json.loads(text)
    except ValueError:
        begin=text.find("{");end=text.rfind("}")
        if begin>=0 and end>begin:return json.loads(text[begin:end+1])
        raise ValueError("A IA não respondeu em JSON musical válido.")

def validate(arrangement):
    if not isinstance(arrangement,dict):raise ValueError("A resposta musical precisa ser objeto JSON.")
    bpm=arrangement.get("bpm",110)
    bars=arrangement.get("compassos",8)
    if type(bpm) not in (int,float) or not 40<=bpm<=220:raise ValueError("BPM retornado pela IA é inválido.")
    if type(bars)!=int or not 4<=bars<=64:raise ValueError("Compassos retornados pela IA são inválidos.")
    parts=arrangement.get("partes")
    if not isinstance(parts,list) or not 1<=len(parts)<=4:raise ValueError("A IA deve retornar entre 1 e 4 pistas.")
    total=0
    clean=[]
    for part in parts:
        if not isinstance(part,dict) or part.get("instrumento") not in INSTRUMENTS:raise ValueError("Instrumento não reconhecido.")
        notes=part.get("notas")
        if not isinstance(notes,list) or not 1<=len(notes)<=128:raise ValueError("Pista sem notas ou acima de 128 notas.")
        safe=[]
        for n in notes:
            if not isinstance(n,dict):raise ValueError("Nota inválida.")
            start=n.get("inicio");duration=n.get("duracao");pitch=n.get("altura");vel=n.get("velocidade",85)
            if not all(type(x) in (int,float) for x in (start,duration,pitch,vel)):raise ValueError("Nota contém dados não numéricos.")
            if not (0<=start<bars*4 and 0<duration<=16 and 0<=pitch<=127 and 1<=vel<=127):raise ValueError("Nota fora da faixa permitida.")
            safe.append({"start":round(start*maestro.PPQ),"end":min(round((start+duration)*maestro.PPQ),bars*4*maestro.PPQ),
                         "pitch":int(pitch),"velocity":int(vel)})
            total+=1
        clean.append({"instrumento":part["instrumento"],"notas":safe})
    return {"titulo":str(arrangement.get("titulo") or "Música criada pela IA")[:100],"bpm":int(bpm),
            "compassos":bars,"partes":clean,"total_notas":total}

def render(validated,prompt,provider_name):
    tempo=round(60000000/validated["bpm"])
    tracks=[maestro.track([(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big"))])]
    for idx,part in enumerate(validated["partes"]):
        name=part["instrumento"]
        channel=9 if name=="Percussao" else idx if idx<9 else idx+1
        ev=[(0,0,b"\xff\x03"+maestro.vlq(len(name.encode()))+name.encode()),
            (0,0,bytes([0xc0|channel,maestro.PROGRAMS[name]]))]
        for n in part["notas"]:
            ev.append((n["start"],2,bytes([0x90|channel,n["pitch"],n["velocity"]])))
            ev.append((max(n["start"]+1,n["end"]),1,bytes([0x80|channel,n["pitch"],0])))
        tracks.append(maestro.track(ev))
    content=b"MThd"+struct.pack(">IHHH",6,1,len(tracks),maestro.PPQ)+b"".join(tracks)
    maestro.OUTPUT.mkdir(parents=True,exist_ok=True)
    name="WMK_"+datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".mid"
    (maestro.OUTPUT/name).write_bytes(content)
    result={"arquivo":name,"estilo":"Arranjo por IA","bpm":validated["bpm"],
            "compassos":validated["compassos"],"instrumentos":[p["instrumento"] for p in validated["partes"]],
            "notas":validated["total_notas"],"duracao_segundos":round(validated["compassos"]*240/validated["bpm"],1),
            "provedor":provider_name,"modo":"IA gerou as notas MIDI",
            "observacao":"Notas propostas pelo modelo de IA e validadas; revise harmonia e selecione timbres na DAW."}
    (maestro.OUTPUT/name.replace(".mid",".json")).write_text(
        json.dumps({"prompt":prompt,"resultado":result},ensure_ascii=False,indent=2),encoding="utf-8")
    return result

def compose_with_provider(prompt,provider_id=None):
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=2000:raise ValueError("Pedido inválido.")
    p=active_provider(provider_id)
    if not p:raise ValueError("Cadastre e ative um provedor antes de compor com IA.")
    response=ask(p,"Crie uma composição ORIGINAL para este pedido musical:\n"+prompt,system=SYSTEM)
    return render(validate(decode_json(response)),prompt,p["nome"])

def teach(question,provider_id=None,context=""):
    if not isinstance(question,str) or not 1<=len(question.strip())<=1500:raise ValueError("Escreva uma pergunta de até 1500 caracteres.")
    p=active_provider(provider_id)
    if not p:raise ValueError("Cadastre um provedor de IA para utilizar o professor.")
    context=str(context)[:1800]
    system="Você é professor de teoria musical para iniciantes, em português brasileiro. Explique notas, acordes, MIDI, intervalos e composição sem jargão desnecessário. Não invente notas de partituras que não recebeu."
    answer=ask(p,"Contexto musical (pode ser vazio): "+context+"\nPergunta: "+question,system=system)
    if not answer.strip():raise ValueError("A IA retornou resposta vazia.")
    return {"resposta":answer[:12000],"provedor":p["nome"],"modelo":p["modelo"]}
