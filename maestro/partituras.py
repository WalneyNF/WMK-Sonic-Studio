"""WMK Maestro: importador experimental de MusicXML/MXL e leitor analítico de MIDI.
Biblioteca padrão Python; limitações documentadas em README. Não executa arquivos enviados.
"""
import io, json, math, struct, zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict

MAX_UPLOAD = 2 * 1024 * 1024
MAX_UNCOMPRESSED = 8 * 1024 * 1024
MAX_NOTES = 30000
STEP = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
NAMES = ["Dó","Dó♯","Ré","Ré♯","Mi","Fá","Fá♯","Sol","Sol♯","Lá","Lá♯","Si"]
PPQ=480

def clean(tag):
    return tag.rsplit("}",1)[-1]

def children(node, name):
    return [c for c in node if clean(c.tag)==name]

def child(node, name):
    return next((c for c in node if clean(c.tag)==name),None)

def value(node, name, default=""):
    x=child(node,name) if node is not None else None
    return x.text.strip() if x is not None and x.text else default

def clamp_int(v, low, high, fallback):
    try: return max(low,min(high,int(v)))
    except (ValueError,TypeError): return fallback

def get_xml(data, filename):
    if len(data)>MAX_UPLOAD: raise ValueError("O arquivo excede 2 MB.")
    if filename.lower().endswith(".mxl"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                docs=[i for i in z.infolist() if i.filename.lower().endswith(".xml")
                      and not i.filename.startswith("META-INF/") and not i.is_dir()]
                if not docs: raise ValueError("O MXL não contém uma partitura MusicXML.")
                if any(x.file_size>MAX_UNCOMPRESSED for x in docs):
                    raise ValueError("O MXL contém XML muito grande.")
                with z.open(docs[0]) as f: return f.read(MAX_UNCOMPRESSED+1)
        except zipfile.BadZipFile as exc: raise ValueError("MXL inválido.") from exc
    return data

def parse_musicxml(data, filename="partitura.musicxml"):
    xml=get_xml(data,filename)
    if len(xml)>MAX_UNCOMPRESSED: raise ValueError("XML excede o limite permitido.")
    try: root=ET.fromstring(xml)
    except ET.ParseError as e: raise ValueError("MusicXML inválido: "+str(e)) from e
    if clean(root.tag)!="score-partwise":
        raise ValueError("Suporte inicial: MusicXML score-partwise. Exporte novamente pelo MuseScore Studio.")
    title=value(child(root,"work"),"work-title") or value(root,"movement-title") or "Partitura sem título"
    partnames={}
    pl=child(root,"part-list")
    if pl is not None:
        for sp in children(pl,"score-part"):
            partnames[sp.get("id","")]=value(sp,"part-name","Instrumento")
    bpm=120
    tracks=[]
    total=0
    for part in children(root,"part")[:32]:
        notes=[]; cursor=0; divisions=1; measure_no=0; measure_ticks=PPQ*4
        last_start_by_voice={}; measure_start=0
        for measure in children(part,"measure")[:500]:
            measure_no+=1
            cursor=measure_start
            local_max=measure_start
            for e in measure:
                kind=clean(e.tag)
                if kind=="attributes":
                    divisions=clamp_int(value(e,"divisions",divisions),1,100000,divisions)
                    time=child(e,"time")
                    if time is not None:
                        beats=clamp_int(value(time,"beats",4),1,32,4)
                        beat_type=clamp_int(value(time,"beat-type",4),1,64,4)
                        measure_ticks=max(1,round(PPQ*4*beats/beat_type))
                elif kind=="direction":
                    sound=child(e,"sound")
                    if sound is not None and sound.get("tempo"):
                        try: bpm=max(30,min(260,round(float(sound.get("tempo")))))
                        except ValueError: pass
                elif kind=="backup":
                    cursor=max(measure_start,cursor-round(clamp_int(value(e,"duration"),0,10000000,0)*PPQ/divisions))
                elif kind=="forward":
                    cursor+=round(clamp_int(value(e,"duration"),0,10000000,0)*PPQ/divisions)
                elif kind=="note":
                    dur=round(clamp_int(value(e,"duration"),0,10000000,0)*PPQ/divisions)
                    voice=value(e,"voice","1")
                    chord=child(e,"chord") is not None
                    start=last_start_by_voice.get(voice,cursor) if chord else cursor
                    if not chord: last_start_by_voice[voice]=start
                    if child(e,"rest") is None:
                        pitch=child(e,"pitch")
                        if pitch is not None:
                            step=value(pitch,"step","C")
                            alter=clamp_int(value(pitch,"alter",0),-2,2,0)
                            octave=clamp_int(value(pitch,"octave",4),-1,9,4)
                            midi=(octave+1)*12+STEP.get(step,0)+alter
                            if 0<=midi<=127 and dur>0:
                                notes.append({"inicio":start,"duracao":dur,"midi":midi,
                                             "nota":NAMES[midi%12]+str(midi//12-1),
                                             "compasso":measure_no,"voz":voice})
                                total+=1
                                if total>MAX_NOTES: raise ValueError("Partitura muito grande (limite 30 mil notas).")
                    if not chord: cursor+=dur
                    local_max=max(local_max,start+dur,cursor)
            measure_start=max(measure_start+measure_ticks,local_max)
        tracks.append({"instrumento":partnames.get(part.get("id",""),"Instrumento"),
                       "notas":notes,"total_notas":len(notes)})
    if not tracks: raise ValueError("A partitura não contém partes musicais.")
    return {"titulo":title,"formato":"MusicXML","bpm":bpm,"ppq":PPQ,
            "instrumentos":tracks,"total_notas":total,
            "limites":["Não interpreta repetições/voltas, dinâmicas nem articulações avançadas.",
                       "A conversão preserva notas, durações e partes básicas; outras informações podem ser perdidas."]}

def vlq(n):
    seq=[n&127]
    while n>>7:
        n>>=7
        seq.insert(0,(n&127)|128)
    return bytes(seq)

def mtrk(events):
    events.sort(key=lambda e:(e[0],e[1]))
    data=bytearray(); previous=0
    for tick,order,msg in events:
        data+=vlq(tick-previous)+msg; previous=tick
    data+=b"\x00\xff\x2f\x00"
    return b"MTrk"+struct.pack(">I",len(data))+data

def to_midi(score):
    bpm=score["bpm"]
    tempo=round(60000000/max(1,bpm))
    chunks=[mtrk([(0,0,b"\xff\x51\x03"+tempo.to_bytes(3,"big"))])]
    for idx,part in enumerate(score["instrumentos"][:15]):
        ch=9 if any(k in part["instrumento"].lower() for k in ("percuss", "bateria", "drum")) else idx if idx<9 else idx+1
        name=part["instrumento"].encode("utf-8")[:100]
        ev=[(0,0,b"\xff\x03"+vlq(len(name))+name),(0,1,bytes([0xc0|ch,0]))]
        for n in part["notas"]:
            start=n["inicio"]; end=start+max(1,n["duracao"])
            ev.extend([(start,2,bytes([0x90|ch,n["midi"],max(1,min(127,int(n.get("velocidade",90))))])),
                       (end,1,bytes([0x80|ch,n["midi"],0]))])
        chunks.append(mtrk(ev))
    return b"MThd"+struct.pack(">IHHH",6,1,len(chunks),PPQ)+b"".join(chunks)

def read_vlq(data,pos,limit):
    n=0
    for _ in range(4):
        if pos>=limit: raise ValueError("MIDI truncado.")
        b=data[pos]; pos+=1; n=(n<<7)|(b&127)
        if b<128: return n,pos
    raise ValueError("Intervalo MIDI inválido.")

def parse_midi(data):
    if len(data)>MAX_UPLOAD: raise ValueError("Arquivo MIDI excede 2 MB.")
    if len(data)<14 or data[:4]!=b"MThd": raise ValueError("Arquivo MIDI inválido.")
    hdr=struct.unpack(">IHHH",data[4:14]); size,fmt,num,division=hdr
    if size<6 or num>64 or division&0x8000: raise ValueError("Formato MIDI ou divisão SMPTE não suportados.")
    pos=8+size; bpm=120; tracks=[]; total=0
    for idx in range(num):
        if data[pos:pos+4]!=b"MTrk" or pos+8>len(data): raise ValueError("Pista MIDI truncada.")
        length=struct.unpack(">I",data[pos+4:pos+8])[0];pos+=8;end=pos+length
        if end>len(data): raise ValueError("Pista MIDI incompleta.")
        tick=0;running=None;opened=defaultdict(list);notes=[];title=f"Pista {idx+1}"
        while pos<end:
            delta,pos=read_vlq(data,pos,end);tick+=delta
            if pos>=end: raise ValueError("Evento MIDI incompleto.")
            status=data[pos]
            if status>=128: pos+=1
            elif running is not None: status=running
            else: raise ValueError("Running status inválido.")
            if status==0xff:
                if pos>=end: raise ValueError("Evento meta inválido.")
                kind=data[pos];pos+=1;amount,pos=read_vlq(data,pos,end)
                content=data[pos:pos+amount];pos+=amount
                if kind==0x03: title=content.decode("utf-8","replace")[:100]
                if kind==0x51 and len(content)==3:
                    micro=int.from_bytes(content,"big")
                    if micro: bpm=round(60000000/micro)
                running=None
            elif status in (0xf0,0xf7):
                amount,pos=read_vlq(data,pos,end);pos+=amount;running=None
            else:
                typ=status&0xf0;ch=status&0x0f
                if typ not in (0x80,0x90,0xa0,0xb0,0xc0,0xd0,0xe0):
                    raise ValueError("Status MIDI desconhecido.")
                count=1 if typ in (0xc0,0xd0) else 2
                if pos+count>end: raise ValueError("Evento MIDI incompleto.")
                a=data[pos]; b=data[pos+1] if count==2 else 0; pos+=count
                if typ==0x90 and b>0: opened[(ch,a)].append((tick,b))
                elif typ==0x80 or typ==0x90 and b==0:
                    key=(ch,a)
                    if opened[key]:
                        start,velocity=opened[key].pop(0)
                        midi=a
                        notes.append({"inicio":round(start*PPQ/division),
                                      "duracao":max(1,round((tick-start)*PPQ/division)),
                                      "midi":midi,"nota":NAMES[midi%12]+str(midi//12-1),
                                      "velocidade":velocity})
                        total+=1
                        if total>MAX_NOTES: raise ValueError("MIDI muito grande.")
                running=status
        tracks.append({"instrumento":title,"total_notas":len(notes),"notas":notes})
    return {"titulo":"Música MIDI","formato":"MIDI","bpm":bpm,"ppq":PPQ,
            "instrumentos":tracks,"total_notas":total,
            "limites":["As notas são extraídas para análise; automações e controladores não são interpretados.",
                       "Os timbres dependerão dos instrumentos virtuais usados na DAW."]}

def explain_note(note):
    name=note.get("nota","")
    midi=int(note.get("midi",60))
    degree=NAMES[midi%12]
    return {"nota":name,"explicacao":f"{name} é a nota {degree}, na oitava {midi//12-1}. "
            "A posição define a altura do som; a duração determina por quanto tempo será tocada.",
            "dica":"Experimente subir a nota dois semitons e ouça a diferença no Piano Roll."}
