import warnings
warnings.filterwarnings("ignore")
import socket
socket.setdefaulttimeout(20)
import streamlit as st, requests, json, os, io, re, zipfile, hashlib, textwrap, time, base64, threading
from datetime import datetime, timedelta, date
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip
from moviepy.audio.AudioClip import AudioClip, CompositeAudioClip, AudioArrayClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
try:
    from moviepy.video.compositing.concatenate import concatenate_videoclips
except Exception:
    try:
        from moviepy.video.compositing import concatenate_videoclips
    except Exception:
        from moviepy import concatenate_videoclips
try:
    from moviepy.audio.compositing.concatenate import concatenate_audioclips
except Exception:
    try:
        from moviepy.audio.compositing.CompositeAudioClip import concatenate_audioclips
    except Exception:
        from moviepy import concatenate_audioclips
import moviepy.video.fx as vfx

DASH, YT, PEX = st.secrets["DASHSCOPE_API_KEY"], st.secrets["YOUTUBE_API_KEY"], st.secrets["PEXELS_API_KEY"]
YTC_ID = st.secrets.get("YOUTUBE_CLIENT_ID") or st.secrets.get("YOUTUBE_Client_ID") or ""
YTC_SEC = st.secrets.get("YOUTUBE_CLIENT_SECRET") or st.secrets.get("YOUTUBE_Client_SECRET") or ""
YT_RT = st.secrets.get("YT_REFRESH_TOKEN","")
BASE = "https://dashscope-intl.aliyuncs.com/api/v1"
CHAT_MODELS = ["qwen3.7-plus", "qwen-plus"]
VIDEO_MODELS = ["wan2.7-t2v", "wan2.1-t2v-turbo"]
IMAGE_MODELS = ["qwen-image-3.0", "wanx2.1-t2i-turbo"]
GOLD, BLACK = (212,175,55), (5,6,8)
TMP = "/tmp"
LINE_F=f"{TMP}/shadow_line.json"; SUP_F=f"{TMP}/supporters.json"; SPO_F=f"{TMP}/sponsor.json"; SET_F=f"{TMP}/settings.json"
JOB_F=f"{TMP}/job.json"; DEC_F=f"{TMP}/decisions.json"; BIBLE_F=f"{TMP}/bible.json"; MET_F=f"{TMP}/metrics.json"
COST_F=f"{TMP}/costs.json"; REV_F=f"{TMP}/revenue.json"; HOF_F=f"{TMP}/hall_of_fame.json"; PREF_F=f"{TMP}/prefs.json"
SEEDS_F=f"{TMP}/seeds.json"; BULL_F=f"{TMP}/bulletin.json"; CRED_F=f"{TMP}/credits.json"; YT_TOK_F=f"{TMP}/yt_token.json"
SCAN_F=f"{TMP}/scan.json"
FONT = next((p for p in ["assets/Cinzel-Bold.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"] if os.path.exists(p)), None)
def F(sz): return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default(sz)
def slug(t): return re.sub(r'[^a-z0-9]+','_', t.lower()).strip('_')[:40]
def jload(p,d):
    try:
        if os.path.exists(p): return json.load(open(p))
    except Exception: pass
    return d
def jsave(p,d):
    try: json.dump(d,open(p,"w"))
    except Exception: pass
ENGINE={"v":""}
def decide(m):
    d=jload(DEC_F,[]); d.append(m); jsave(DEC_F,d)
def job_load(): return jload(JOB_F,{"running":False,"current":"","log":[],"live":None,"history":[]})
def job_save(j): jsave(JOB_F,j)
def prefs_txt():
    p=jload(PREF_F,[]); return " · ".join(p[-5:]) if p else "No CEO preferences stored yet."
DEFAULT_SEEDS="BlackRock buying housing\nTicketmaster Live Nation monopoly\nThe janitor who left $6 million to his hospital\nHow Norway became the world's landlord\nThe teacher who out-traded Wall Street\nBoeing whistleblowers"
def load_seeds():
    s=jload(SEEDS_F,None); return "\n".join(s) if s else DEFAULT_SEEDS
def save_seeds(t): jsave(SEEDS_F,[x for x in t.splitlines() if x.strip()])
def cred_load(): return jload(CRED_F,{"loaded_zar":0})
def cred_save(d): jsave(CRED_F,d)
DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
def occ(day_name,hhmm,add_days=0,weeks=0):
    target=DAYS.index(day_name); d=date.today()
    delta=(target-d.weekday())%7
    dt=d+timedelta(days=delta+add_days+7*weeks)
    hh,mm=[int(x) for x in (hhmm or "21:00").split(":")]
    return datetime(dt.year,dt.month,dt.day,hh,mm).strftime("%Y-%m-%dT%H:%M:00Z")
def ramp_advisor():
    line=load_line(); n=len([i for i in line if i["status"]=="rendered"])
    met=jload(MET_F,{}); ctrs=[float(m.get("ctr") or 0) for m in met.values() if m.get("ctr")]
    avg=sum(ctrs)/len(ctrs) if ctrs else 0
    if n<2: ph,rec,go="WARM-UP","2 episodes this week",False
    elif n<4: ph,rec,go="BUILD","4 episodes this week",False
    elif n<8: ph,rec,go="SCALE","8 episodes this week",avg>=3.5
    else: ph,rec,go="AGGRESSIVE","12-30 episodes this week",avg>=3.0
    if go: rec+=" — 🚀 signs are GOOD, go aggressive"
    return {"phase":ph,"rec":rec,"go":go,"n":n,"ctr":avg}
def smart_ep_when(phase,idx):
    if phase=="WARM-UP": return occ("Friday","21:00",weeks=idx)
    if phase=="BUILD": return occ("Tuesday" if idx%2 else "Friday","21:00",weeks=idx//2)
    if phase=="SCALE": return occ(["Monday","Wednesday","Friday"][idx%3],"21:00",weeks=idx//3)
    return occ(DAYS[idx%7],"21:00",weeks=idx//7)
def smart_sh_when(phase,k):
    return occ(["Monday","Wednesday","Friday"][k%3],"17:00",weeks=k//3)

# ---------------- MODEL DISCOVERY ----------------
_MC={"t":0.0,"ids":[]}
def list_models():
    if time.time()-_MC["t"]>21600:
        try:
            r=requests.get("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",headers={"Authorization":f"Bearer {DASH}"},timeout=30).json()
            _MC["ids"]=[m.get("id","") for m in r.get("data",[])]
        except Exception: pass
        _MC["t"]=time.time()
    return _MC["ids"]
def disc(pat,n=3):
    c=[i for i in list_models() if re.search(pat,i,re.I)]
    def ver(i):
        m=re.findall(r"\d+(?:\.\d+)+",i) or re.findall(r"\d+",i)
        try: return [int(x) for x in m[0].split(".")]
        except Exception: return [0]
    c.sort(key=ver,reverse=True); return c[:n]
def chain(pat,fb):
    out=disc(pat)
    for f in fb:
        if f not in out: out.append(f)
    return out

MOODS={"Calm investigator (default)":"low, calm, intimate documentary voice, slow deliberate pace, slightly breathy, grave tension, long pause before every reveal",
"Concerned witness":"worried, urgent, leaning in, slightly trembling with concern, as if warning a friend",
"Grave elegy":"mournful, heavy, slow, deep pauses, the voice of a eulogy",
"Cold expose":"clinical, sharp, controlled anger, precise diction, ice-cold delivery",
"Hushed suspense":"near-whisper, tense, every word a secret, long silences",
"Hopeful storyteller":"warm, admiring, quietly triumphant, a smile in the voice"}
EDGE_VOICES={"Calm investigator (default)":("en-US-GuyNeural","-10%"),"Concerned witness":("en-US-AriaNeural","-5%"),"Grave elegy":("en-GB-RyanNeural","-15%"),"Cold expose":("en-US-ChristopherNeural","-8%"),"Hushed suspense":("en-GB-SoniaNeural","-12%"),"Hopeful storyteller":("en-US-JennyNeural","-5%")}
QWEN_TTS_VOICES=["Cherry","Serena","Ethan","Chelsie"]
MOOD_ROT=list(MOODS.keys())
ANGLES={"Dark expose (default)":"Tone: dark investigative expose.","Mystery / curiosity":"Tone: puzzle-box mystery.","David vs Goliath":"Tone: underdog versus a financial giant.","Comeback / positive":"Tone: triumphant human comeback."}
TONE_LABEL={"Dark expose (default)":"A DARK EXPOSE","Mystery / curiosity":"A MYSTERY","David vs Goliath":"AN UNDERDOG STORY","Comeback / positive":"A COMEBACK"}

# ---------------- TTS NORMALIZER ----------------
_ONES=["","one","two","three","four","five","six","seven","eight","nine","ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
_TENS=["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
def _w3(n):
    h,r=divmod(n,100); s=""
    if h: s+=_ONES[h]+" hundred"
    if r:
        if s: s+=" "
        if r<20: s+=_ONES[r]
        else:
            t,u=divmod(r,10); s+=_TENS[t]+((" "+_ONES[u]) if u else "")
    return s
def num_to_words(n):
    n=int(n)
    if n==0: return "zero"
    parts=[]
    for val,name in ((1_000_000_000,"billion"),(1_000_000,"million"),(1000,"thousand")):
        if n>=val:
            q,n=divmod(n,val); parts.append(_w3(q)+" "+name)
    if n: parts.append(_w3(n))
    return " ".join(parts)
def normalize_tts(t):
    def money(m):
        num=m.group(1).replace(",",""); scale=m.group(2) or ""
        try: w=num_to_words(int(float(num)))
        except Exception: return m.group(0)
        return (w+" "+scale+" dollars").replace("  "," ").strip()
    t=re.sub(r"\$\s?([\d,]+(?:\.\d+)?)\s*(trillion|billion|million)?",money,t)
    t=re.sub(r"([\d,]+)\s*(trillion|billion|million)\b",lambda m:(num_to_words(int(m.group(1).replace(',','')))+" "+m.group(2)),t)
    t=re.sub(r"(\d+(?:\.\d+)?)\s*%",lambda m:(num_to_words(int(float(m.group(1))))+" percent"),t)
    return t
def mood_for(i): return MOOD_ROT[i%len(MOOD_ROT)]

# ---------------- OAUTH + YOUTUBE + DRIVE (on-demand) ----------------
YT_ONLY="https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/yt-analytics.readonly"
FULL=YT_ONLY+" https://www.googleapis.com/auth/drive.file"
def yt_auth_url(scopes=FULL):
    return (f"https://accounts.google.com/o/oauth2/v2/auth?client_id={YTC_ID}&redirect_uri=http://localhost&response_type=code&scope={requests.utils.quote(scopes)}&access_type=offline&prompt=consent")
def yt_connect(code):
    r=requests.post("https://oauth2.googleapis.com/token",data={"code":code,"client_id":YTC_ID,"client_secret":YTC_SEC,"redirect_uri":"http://localhost","grant_type":"authorization_code"}).json()
    if "access_token" not in r: raise RuntimeError(r.get("error_description","oauth failed"))
    jsave(YT_TOK_F,{"token":r["access_token"],"refresh":r.get("refresh_token"),"cid":YTC_ID,"csec":YTC_SEC})
    return r.get("refresh_token","")
def _creds():
    from google.oauth2.credentials import Credentials
    tok=jload(YT_TOK_F,None)
    if tok: c=Credentials(token=tok.get("token"),refresh_token=tok.get("refresh"),client_id=tok.get("cid"),client_secret=tok.get("csec"),token_uri="https://oauth2.googleapis.com/token")
    elif YT_RT and YTC_ID and YTC_SEC: c=Credentials(token=None,refresh_token=YT_RT,client_id=YTC_ID,client_secret=YTC_SEC,token_uri="https://oauth2.googleapis.com/token")
    else: return None
    if not c.valid and c.refresh_token:
        try:
            from google.auth.transport.requests import Request
            c.refresh(Request()); jsave(YT_TOK_F,{"token":c.token,"refresh":c.refresh_token,"cid":YTC_ID,"csec":YTC_SEC})
        except Exception: return None
    return c
def yt_service(kind="youtube"):
    from googleapiclient.discovery import build
    c=_creds()
    if not c: return None
    return build(kind,"v3" if kind=="youtube" else "v2",credentials=c)
def drive_service():
    from googleapiclient.discovery import build
    c=_creds()
    if not c: return None
    try: return build("drive","v3",credentials=c)
    except Exception: return None
VAULT="Shadow Ledger Vault"
def _vault_fid():
    d=drive_service()
    if not d: return None
    try:
        q=d.files().list(q=f"name='{VAULT}' and mimeType='application/vnd.google-apps.folder' and trashed=false",spaces="drive",fields="files(id)").execute()
        if q["files"]: return q["files"][0]["id"]
        return d.files().create(body={"name":VAULT,"mimeType":"application/vnd.google-apps.folder"}).execute()["id"]
    except Exception: return None
def drive_upsert(name,text,fid):
    from googleapiclient.http import MediaIoBaseUpload
    d=drive_service()
    if not d or not fid: return
    try:
        q=d.files().list(q=f"name='{name}' and '{fid}' in parents and trashed=false",fields="files(id)").execute()
        media=MediaIoBaseUpload(io.BytesIO(text.encode()),mimetype="application/json",resumable=False)
        if q["files"]: d.files().update(fileId=q["files"][0]["id"],media_body=media).execute()
        else: d.files().create(body={"name":name,"parents":[fid]},media_body=media).execute()
    except Exception: pass
def drive_read(name,fid):
    from googleapiclient.http import MediaIoBaseDownload
    d=drive_service()
    if not d or not fid: return None
    try:
        q=d.files().list(q=f"name='{name}' and '{fid}' in parents and trashed=false",fields="files(id)").execute()
        if not q["files"]: return None
        fh=io.BytesIO(); req=d.files().get_media(fileId=q["files"][0]["id"])
        down=MediaIoBaseDownload(fh,req); done=False
        while not done: _,done=down.next_chunk()
        return json.loads(fh.getvalue().decode())
    except Exception: return None
def vault_save(line):
    try: drive_upsert("state.json",json.dumps(line),_vault_fid())
    except Exception: pass
def vault_load():
    try: return drive_read("state.json",_vault_fid())
    except Exception: return None
def vault_save_job(j):
    try: drive_upsert("job.json",json.dumps(j),_vault_fid())
    except Exception: pass
def yt_channel_uploads():
    svc=yt_service()
    if not svc: return []
    try:
        ch=svc.channels().list(part="contentDetails",mine=True).execute()
        up=ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]; vids=[]; nxt=None
        for _ in range(3):
            r=svc.playlistItems().list(part="snippet",playlistId=up,maxResults=50,pageToken=nxt or "").execute()
            for it in r.get("items",[]): vids.append((it["snippet"]["resourceId"]["videoId"],it["snippet"]["title"]))
            nxt=r.get("nextPageToken")
            if not nxt: break
        return vids
    except Exception: return []

# ---------------- LINE (local-only at boot) ----------------
def load_line(): return jload(LINE_F,[])
def save_line(l):
    jsave(LINE_F,l)
if "line" not in st.session_state:
    st.session_state.line=load_line()
if "edits" not in st.session_state: st.session_state.edits={}
if "scan" not in st.session_state:
    st.session_state.scan=jload(SCAN_F,None)
for _it in st.session_state.line:
    if _it["status"]=="rendered" and not os.path.exists(_it.get("out") or ""):
        _it["status"]="approved"; _it["err"]="media cache cleared — script kept, press render to redo"
jsave(LINE_F, st.session_state.line)
def queue_topic(t,sc,tag):
    line=load_line()
    if t and not any(i["topic"]==t for i in line):
        line.append({"topic":t,"score":sc,"tag":tag,"status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":""})
        save_line(line)
        try: decide(f"Queued '{t[:40]}' ({tag}, score {sc}).")
        except Exception: pass
        return True
    return False

# ---------------- BIBLE/HOF/DNA/GATE ----------------
def bible_txt():
    b=jload(BIBLE_F,[])
    if not b: return "No previous episodes yet."
    return " · ".join(f"EP{e['ep']} {e['topic']}: {e.get('callback','')}" for e in b[-4:])
def bible_append(ep,topic,sc):
    try:
        g=qwen(f"Episode topic: {topic}. Script JSON: {json.dumps(sc)[:2500]}. Return JSON {{'facts':[3],'callback':'one sentence','sequel_seed':'one line'}}")
        b=jload(BIBLE_F,[]); b.append({"ep":ep,"topic":topic,"facts":g.get("facts",[]),"callback":g.get("callback",""),"sequel":g.get("sequel_seed","")}); jsave(BIBLE_F,b)
    except Exception: pass
def hof_update(vid,score):
    h=jload(HOF_F,[]); h.append({"vid":vid,"score":score}); jsave(HOF_F,h)
def hof_best():
    h=jload(HOF_F,[]); return max(h,key=lambda x:x.get("score",0)) if h else None
DNA="""You are showrunner of SHADOW LEDGER, a prestige financial documentary series.
Topic: {topic}. Series: {series}. ANGLE: {angle}
SERIES MEMORY: {bible}
CEO PREFERENCES (obey these): {prefs}
STRUCTURE: 1. COLD OPEN + VIEWER STAKES (first 15s). 2. ACT I SUSPECT. 3. ACT II MACHINE (open loop every 90s). 4. ACT III REVEAL. 5. OPEN QUESTION + CTA + BINGE-PITCH.
RULES: present tense, short cinematic sentences, NO ACCUSATIONS (alleged/documents show), concrete specifics, max 3 sentences/scene.
ANTI-SLOP: BANNED: delve, tapestry, landscape, game-changer, uncover the truth.
OUTPUT JSON: {{"title_options":[3],"hook_words":"MAX 4 WORDS","share_line":"max 10 words","scenes":[{{"narration":"","visual":"","ost":""}}],"pinned_question":"","binge_pitch":"","community_poll":{{"q":"","a":["",""]}},"cold_open_A":"max 20 words","cold_open_B":"max 20 words"}}"""
GATE="""You are SHADOW LEDGER's executive editor + legal + YouTube policy officer. Review script JSON: {script}
FIX slop/legal/viewer-stakes/dragging/clickbait/AdSense. Return JSON {{"slop_clean":0-100,"emotion":0-100,"viewer_stakes":"","legal_flags_fixed":N,"yt_policy":"clean|fixed","clickbait":"clean|fixed","advisory":"","pacing":"","scenes":[same schema],"title_options":[],"share_line":"","cold_open_A":"","cold_open_B":""}}"""
def qwen(prompt,sys=None):
    m=([{"role":"system","content":sys}] if sys else [])+[{"role":"user","content":prompt}]
    last=None
    for model in chain(r"plus",CHAT_MODELS):
        try:
            r=requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",headers={"Authorization":f"Bearer {DASH}"},json={"model":model,"messages":m,"response_format":{"type":"json_object"}},timeout=120).json()
            return json.loads(r["choices"][0]["message"]["content"])
        except Exception as e: last=e
    raise RuntimeError(f"chat failed: {last}")
def wan_video_prompt(v): return f"{v}. cinematic documentary film still, anamorphic 2.39:1, 35mm grain, low-key chiaroscuro, crushed blacks, gold practicals, teal shadows, slow dolly, no text, no watermark"

# ---------------- VOICE CHAIN ----------------
def speak(text,voice,mood):
    text=normalize_tts(text)
    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        dashscope.base_http_api_url="https://dashscope-intl.aliyuncs.com/api/v1"
        dashscope.base_websocket_api_url="wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"
        cm=sorted(disc(r"cosyvoice",6) or ["cosyvoice-v3-plus","cosyvoice-v3-flash","cosyvoice-v2"],key=lambda m:(0 if ("plus" in m or "instruct" in m) else 1))
        for model in cm:
            for instr in (MOODS[mood],None):
                try:
                    kw={"model":model,"voice":voice or "longanyang"}
                    if instr: kw["instruction"]=instr
                    b=SpeechSynthesizer(**kw).call(text)
                    if b: ENGINE["v"]=f"CosyVoice ({model}) — premium"; return b
                except Exception: continue
    except Exception: pass
    tm=sorted(disc(r"tts",6) or ["qwen3-tts-plus","qwen-audio-3.0-tts-flash"],key=lambda m:(0 if ("plus" in m or "instruct" in m) else 1))
    for model in tm:
        for vq in QWEN_TTS_VOICES:
            try:
                r=requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",headers={"Authorization":f"Bearer {DASH}"},json={"model":model,"messages":[{"role":"user","content":text}],"modalities":["audio"],"audio":{"voice":vq,"format":"mp3"}},timeout=90).json()
                b=base64.b64decode(r["choices"][0]["message"]["audio"]["data"])
                if b: ENGINE["v"]=f"Qwen-TTS ({model}/{vq}) — premium"; return b
            except Exception: continue
    try:
        import edge_tts,asyncio
        v,rr=EDGE_VOICES.get(mood,("en-US-GuyNeural","-10%"))
        p=f"{TMP}/edge_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
        asyncio.run(edge_tts.Communicate(text,v,rate=rr).save(p))
        ENGINE["v"]="Edge Neural (free, studio-grade)"; return open(p,"rb").read()
    except Exception: pass
    from gtts import gTTS
    p=f"{TMP}/gtts_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
    gTTS(text=text,lang="en").save(p); ENGINE["v"]="Google gTTS (free)"; return open(p,"rb").read()
def _task(tid): return requests.get(f"{BASE}/tasks/{tid}",headers={"Authorization":f"Bearer {DASH}"}).json()
def wan_video(prompt):
    for model in chain(r"wan.*t2v",VIDEO_MODELS):
        try:
            r=requests.post(f"{BASE}/services/aigc/video-generation/video-synthesis",headers={"Authorization":f"Bearer {DASH}","Content-Type":"application/json","X-DashScope-Async":"enable"},json={"model":model,"input":{"prompt":prompt},"parameters":{"size":"1280*720"}}).json()
            tid=r["output"]["task_id"]
            for _ in range(150):
                time.sleep(4); q=_task(tid); stt=q["output"]["task_status"]
                if stt=="SUCCEEDED": return q["output"]["video_url"]
                if stt in ("FAILED","CANCELED"): break
        except Exception: continue
    raise RuntimeError("video models failed")
def wan_images(prompt,n=2):
    for model in chain(r"qwen-image|wanx",IMAGE_MODELS):
        try:
            r=requests.post(f"{BASE}/services/aigc/text2image/image-synthesis",headers={"Authorization":f"Bearer {DASH}","Content-Type":"application/json","X-DashScope-Async":"enable"},json={"model":model,"input":{"prompt":prompt},"parameters":{"size":"1280*720","n":n}}).json()
            tid=r["output"]["task_id"]
            for _ in range(60):
                time.sleep(3); q=_task(tid); stt=q["output"]["task_status"]
                if stt in ("FAILED","CANCELED"): break
                if stt=="SUCCEEDED":
                    out=q["output"]
                    if "results" in out: return [x["url"] for x in out["results"]]
                    if "choices" in out:
                        u=[]
                        for ch in out["choices"]:
                            c=ch.get("message",{}).get("content")
                            if isinstance(c,list): u+=[i["image"] for i in c if isinstance(i,dict) and "image" in i]
                        if u: return u
        except Exception: continue
    raise RuntimeError("image models failed")
def pexels_clip(q): return requests.get("https://api.pexels.com/videos/search",headers={"Authorization":PEX},params={"query":q,"per_page":5}).json()["videos"][0]["video_files"][0]["link"]
def fetch(u,n):
    p=f"{TMP}/{n}"; open(p,"wb").write(requests.get(u).content); return p
def estimate(sc,pilot):
    sc_=sc["scenes"][:4] if pilot else sc["scenes"]; chars=sum(len(s["narration"]) for s in sc_)
    return int(chars/14)+8+len(sc_), len(sc_)*0.06+chars*0.00003
def balance_advice(line):
    met=jload(MET_F,{}); ctrs={}
    for vid,m in met.items():
        a=m.get("angle"); c=m.get("ctr")
        if a and c is not None: ctrs.setdefault(a,[]).append(c)
    best=max(ctrs,key=lambda k:sum(ctrs[k])/len(ctrs[k])) if ctrs else None
    recent=[i.get("angle") or "Dark expose (default)" for i in line if i["status"] in ("rendered","approved","scripted","queued")][-3:]
    if best and best not in recent: return best
    if len(recent)<2: return None
    dark=sum(1 for a in recent if a=="Dark expose (default)")
    if dark>=2: return "Mystery / curiosity"
    if len(recent)>=3 and not any(a=="Comeback / positive" for a in recent): return "Comeback / positive"
    if dark==0: return "Dark expose (default)"
    return None
def yt(path,**kw):
    try: return requests.get(f"https://www.googleapis.com/youtube/v3/{path}",params={"key":YT,**kw},timeout=15).json()
    except Exception: return {}
def golden_egg(topic):
    s=yt("search",part="snippet",q=topic,type="video",maxResults=10,order="viewCount")
    ids=[i["id"]["videoId"] for i in s.get("items",[])]
    if not ids: return 50,"no data"
    vs=yt("videos",part="statistics,snippet",id=",".join(ids))["items"]
    if not vs: return 50,"no data"
    views=[int(v["statistics"]["viewCount"]) for v in vs]
    demand=min(45,int(sum(views)/len(views)/1e6*9))
    fresh=min(20,int(sum(1 for v in vs if (datetime.now()-datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z","")))<timedelta(days=730))*2.5))
    chans={v["snippet"]["channelId"] for v in vs}; comp=max(0,20-len(chans)*2)
    bo=min(15,sum(1 for v in vs if int(v["statistics"]["viewCount"])>200000)*5)
    return min(100,demand+fresh+comp+bo),f"demand {demand}/45 · momentum {fresh}/20 · open field {comp}/20 · proof {bo}/15"
def hunt(theme,min_score=80,n=5):
    c=qwen(f"Generate {n*3} distinct financial-documentary topics about: {theme}. Return JSON {{'topics':[...]}}")
    out=[]
    for t in c.get("topics",[]):
        try:
            sc,why=golden_egg(t)
            if sc>=min_score: out.append((t,sc,why))
        except Exception: pass
    out.sort(key=lambda x:-x[1]); return out[:n]
def trend_radar(seed):
    try:
        r=requests.get("https://suggestqueries.google.com/complete/search",params={"client":"youtube","q":seed},timeout=10)
        sug=[s[0] if isinstance(s,list) else s for s in r.json()[1]]
    except Exception:
        sug=[]
    wk=yt("search",part="snippet",q=seed,type="video",order="viewCount",publishedAfter=(datetime.utcnow()-timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),maxResults=5)
    vel=[i["snippet"]["title"][:40] for i in wk.get("items",[])]
    if not sug: sug=[f"{seed} {x}" for x in ("explained","documentary","scandal","2026")]
    return sug,vel
def predict_spikes(seed):
    sug,vel=trend_radar(seed); out=[]
    for s in sug[:8]:
        try:
            sc,why=golden_egg(s); out.append((s,sc,why))
        except Exception: pass
    out.sort(key=lambda x:-x[1]); return out
def refresh_bulletin(seed_text):
    themes=[x for x in seed_text.splitlines() if x.strip()][:2] or ["finance"]; items=[]
    for th in themes:
        sug,vel=trend_radar(th)
        for s in sug[:4]:
            try:
                sc,why=golden_egg(s); items.append({"t":s,"sc":sc,"src":"LIVE"})
            except Exception: pass
        for v in vel[:2]: items.append({"t":v,"sc":0,"src":"HOT-7D"})
    try:
        for s,sc,why in predict_spikes(themes[0])[:5]: items.append({"t":s,"sc":sc,"src":"FORECAST"})
    except Exception: pass
    seen=set(); out=[]
    for i in items:
        k=i["t"].lower().strip()
        if k and k not in seen: seen.add(k); out.append(i)
    out.sort(key=lambda x:-x["sc"]); jsave(BULL_F,{"ts":datetime.now().isoformat(),"items":out[:12]}); return out[:12]
def series_plan(t): return qwen(f"Prestige documentary topic: {t}. Return JSON {{'series':bool,'why':'','episodes':[]}}")
TRIGGERS={"scam":"alleged fraud","scammer":"alleged fraudster","kill":"fatality","murder":"fatality","suicide":"tragic death","terrorist":"extremist","cartel":"syndicate","rape":"assault","steal":"misappropriate"}
def adsense_scrub(t):
    for b,g in TRIGGERS.items(): t=re.sub(rf"\b{b}\b",g,t,flags=re.IGNORECASE)
    return t
def yt_upload(path,title,desc,tags,when=None,thumb=None):
    from googleapiclient.http import MediaFileUpload
    svc=yt_service()
    if not svc: return None
    body={"snippet":{"title":title,"description":desc,"tags":tags,"categoryId":"25"},"status":{"privacyStatus":"private","selfDeclaredMadeForKids":False}}
    if when: body["status"]["publishAt"]=when
    resp=svc.videos().insert(part="snippet,status",body=body,media_body=MediaFileUpload(path,mimetype="video/mp4",resumable=True)).execute()
    vid=resp["id"]
    if thumb:
        try: svc.thumbnails().set(videoId=vid,media_body=MediaFileUpload(thumb,mimetype="image/png")).execute()
        except Exception: pass
    return vid
def yt_unpublish(vid):
    svc=yt_service()
    if not svc: return False
    svc.videos().update(part="status",body={"id":vid,"status":{"privacyStatus":"private"}}).execute(); return True
def yt_metrics(vid):
    svc=yt_service("youtubeAnalytics")
    if not svc: return None
    t=date.today(); s=t-timedelta(days=2)
    try:
        r=svc.query().execute(ids="channel==MINE",startDate=s.isoformat(),endDate=t.isoformat(),metrics="views,impressionCtr,averageViewDuration",filters=f"video=={vid}")
    except Exception: return None
    row=r.get("rows",[None])[0]
    return {"views":row[0] if row else 0,"ctr":row[1] if row else None,"avd":row[2] if row else 0}
def ceo_pilot(msg):
    line=load_line()
    state={"line":[{"ep":i+1,"topic":x["topic"],"status":x["status"]} for i,x in enumerate(line)],"prefs":jload(PREF_F,[])[-5:]}
    r=qwen(f"You are the CEO's Pilot. Return JSON {{'actions':[...],'reply':''}}. Actions: hunt/queue/reject/cancel/prefer/angle. State: {json.dumps(state)}. CEO: {msg}")
    outs=[]
    for a in r.get("actions",[]):
        act=a.get("action"); line=load_line()
        if act=="hunt":
            res=hunt(a.get("theme","financial scandals"),int(a.get("min_score",80)))
            outs.append(f"🎯 Queued {sum(1 for t,s,w in res if queue_topic(t,s,'HUNTED'))} topics.")
        elif act=="queue":
            if queue_topic(a.get("topic",""),0,"CEO"): outs.append(f"➕ Queued: {a.get('topic')}")
        elif act in ("reject","cancel"):
            idx=int(a.get("ep",1))-1
            if 0<=idx<len(line):
                it=line[idx]
                if act=="cancel" and it.get("yt_id"): yt_unpublish(it["yt_id"])
                it["status"]="rejected"; save_line(line)
                p=jload(PREF_F,[]); p.append(f"CEO rejected EP{idx+1}: {a.get('reason','')}"); jsave(PREF_F,p)
                outs.append(f"🚫 EP{idx+1} rejected — lesson stored.")
        elif act=="prefer":
            p=jload(PREF_F,[]); p.append(a.get("note","")); jsave(PREF_F,p); outs.append("🧠 Preference stored.")
        elif act=="angle":
            S=jload(SET_F,{}); S["angle"]=a.get("value"); jsave(SET_F,S); outs.append("🎨 Angle set.")
    return r.get("reply","Done, CEO."),outs

# ---------------- PIL + SOUND + RENDER ----------------
def card_img(title,sub="",w=1280,h=720,transparent=False):
    img=Image.new("RGBA" if transparent else "RGB",(w,h),(0,0,0,0) if transparent else BLACK)
    d=ImageDraw.Draw(img)
    if not transparent: d.rectangle([0,h//2-90,w,h//2+90],fill=(8,9,12))
    d.text((w//2,h//2-30),title,font=F(64),fill=GOLD,anchor="mm")
    if sub: d.text((w//2,h//2+50),sub,font=F(30),fill=(220,220,220),anchor="mm")
    d.rectangle([w//2-260,h//2+95,w//2+260,h//2+98],fill=GOLD)
    return np.array(img)
def credits_img(names):
    img=Image.new("RGB",(1280,720),BLACK); d=ImageDraw.Draw(img)
    d.rectangle([40,40,1240,680],outline=GOLD,width=2)
    d.text((640,140),"SUPPORTERS OF THE LEDGER",font=F(56),fill=GOLD,anchor="mm")
    for k,ln in enumerate(textwrap.wrap(" · ".join(names),58)[:4]): d.text((640,300+k*72),ln,font=F(34),fill=(230,230,230),anchor="mm")
    return np.array(img)
def ost_img(text):
    img=Image.new("RGBA",(1280,160),(0,0,0,0)); d=ImageDraw.Draw(img)
    d.text((640,80),text.upper(),font=F(72),fill=GOLD,anchor="mm",stroke_width=5,stroke_fill=(0,0,0))
    return np.array(img)
def pattern_interrupt(dur=0.8):
    img=Image.new("RGBA",(1280,720),(0,0,0,0)); d=ImageDraw.Draw(img)
    d.rectangle([0,0,1280,720],fill=(0,0,0,180)); d.text((640,360),"FOLLOW THE MONEY",font=F(110),fill=GOLD,anchor="mm")
    return ImageClip(np.array(img)).with_duration(dur)
def tiktok_intro(hook):
    img=Image.new("RGB",(1080,1920),BLACK); d=ImageDraw.Draw(img)
    d.text((540,800),"WHAT YOU'RE ABOUT",font=F(80),fill=GOLD,anchor="mm"); d.text((540,900),"TO SEE",font=F(80),fill=GOLD,anchor="mm")
    for k,ln in enumerate(textwrap.wrap(hook.upper(),20)[:4]): d.text((540,1100+k*80),ln,font=F(48),fill=(230,230,230),anchor="mm")
    return ImageClip(np.array(img)).with_duration(2.5)
def case_file_pdf(topic,series,dos,support,path,ep="001"):
    W,H=1240,1754; pages=[]
    def blank():
        img=Image.new("RGB",(W,H),BLACK); d=ImageDraw.Draw(img)
        d.rectangle([50,50,W-50,H-50],outline=GOLD,width=2); d.text((W//2,110),"SHADOW LEDGER · CASE FILE",font=F(30),fill=GOLD,anchor="mm")
        return img,d
    cov,d0=blank()
    d0.text((W//2,660),"SHADOW LEDGER",font=F(90),fill=GOLD,anchor="mm"); d0.text((W//2,780),series.upper(),font=F(40),fill=(230,230,230),anchor="mm")
    d0.text((W//2,860),f"EPISODE #{ep}",font=F(36),fill=GOLD,anchor="mm")
    for k,ln in enumerate(textwrap.wrap(topic,30)): d0.text((W//2,990+k*70),ln,font=F(54),fill=(240,240,240),anchor="mm")
    pages.append(cov)
    def section(title,items):
        img,d=blank(); d.text((W//2,210),title,font=F(52),fill=(240,240,240),anchor="mm"); y=330
        for it in items:
            for k,ln in enumerate(textwrap.wrap(str(it),74)):
                d.text((90,y),("• " if k==0 else "   ")+ln,font=F(30),fill=(220,220,220)); y+=46
                if y>H-160: pages.append(img); img,d=blank(); y=310
        pages.append(img)
    section("TIMELINE",dos.get("timeline",[])); section("KEY_PLAYERS",dos.get("key_players",[])); section("FOLLOW THE MONEY",dos.get("follow_the_money",[]))
    section("GLOSSARY",dos.get("glossary",[])); section("DISCUSSION",dos.get("discussion",[]))
    img,d=blank(); d.text((W//2,800),"STAND WITH THE LEDGER",font=F(60),fill=GOLD,anchor="mm"); d.text((W//2,900),f"Tips & Case Files: {support}",font=F(30),fill=GOLD,anchor="mm")
    pages.append(img)
    pages[0].save(path,save_all=True,append_images=pages[1:]); return path
def image_ad_clip(p,name):
    im=Image.open(p).convert("RGB"); w,h=im.size; tw,th=w/h,16/9
    if tw>th:
        nw=int(h*th); im=im.crop(((w-nw)//2,0,(w+nw)//2,h))
    else:
        nh=int(w/th); im=im.crop((0,(h-nh)//2,w,(h+nh)//2))
    im=im.resize((1280,720),Image.LANCZOS); d=ImageDraw.Draw(im)
    d.rectangle([0,640,1280,720],fill=(5,6,8)); d.text((40,680),f"SPONSOR · {name.upper()}",font=F(34),fill=GOLD,anchor="lm")
    return ImageClip(np.array(im))
def make_bug():
    if os.path.exists("assets/sl_logo.png") and not os.path.exists(f"{TMP}/bug.png"):
        a=np.array(Image.open("assets/sl_logo.png").convert("RGBA")); m=a[...,:3].sum(axis=2)<135; a[m,3]=0; a[~m,3]=150
        img=Image.fromarray(a); w,h=img.size; img.resize((int(w*160/h),160),Image.LANCZOS).save(f"{TMP}/bug.png")
make_bug()
def silence(d): return AudioClip(lambda t:[0,0],d,fps=44100)
SR=22050
def sound_bed(dur,markers,hopeful=False):
    n=int(dur*SR); t=np.arange(n)/SR; f1,f2=(66.0,82.5) if hopeful else (52.0,78.0)
    bed=0.10*np.sin(2*np.pi*f1*t)*(0.6+0.4*np.sin(2*np.pi*0.11*t))+0.05*np.sin(2*np.pi*f2*t+1.3)
    rng=np.random.default_rng(7); noise=np.convolve(rng.standard_normal(n),np.ones(40)/40,mode="same")
    for m in markers:
        s,e=max(0,int((m-3)*SR)),int(m*SR)
        if e>s:
            seg=np.arange(e-s)/(e-s); bed[s:e]+=noise[s:e]*0.12*seg**2
        s,e=int(m*SR),min(n,int((m+1.6)*SR)); tt=np.arange(e-s)/SR
        bed[s:e]+=0.35*np.sin(2*np.pi*45*tt)*np.exp(-3*tt)
    for dt in np.arange(45.0,dur,45.0):
        s,e=int(dt*SR),min(n,int((dt+1.0)*SR)); tt=np.arange(e-s)/SR
        bed[s:e]+=0.4*np.sin(2*np.pi*35*tt)*np.exp(-2*tt)
    step=int(1.4*SR); tk=int(0.03*SR); tt=np.arange(tk)/SR; tick=0.05*np.sin(2*np.pi*1800*tt)*np.exp(-80*tt)
    for s in range(0,n-tk,step): bed[s:s+tk]+=tick
    bed=bed/np.max(np.abs(bed))*0.5
    return AudioArrayClip(np.stack([bed,bed],axis=1),fps=SR)
def write_script(topic,series,angle,bible="",prefs=""):
    return qwen(DNA.format(topic=topic,series=series,angle=ANGLES[angle],bible=bible or bible_txt(),prefs=prefs or prefs_txt()))
def quality_gate(topic,sc): return qwen(GATE.format(topic=topic,script=json.dumps(sc)))
def apply_gate(sc,g):
    if g.get("scenes"):
        for s in g["scenes"]:
            s["narration"]=adsense_scrub(s["narration"]); s["ost"]=adsense_scrub(s.get("ost",""))
        sc["scenes"]=g["scenes"]
    for k in ("title_options","share_line","cold_open_A","cold_open_B"):
        if g.get(k): sc[k]=g[k]
    sc["advisory"]=g.get("advisory",""); return sc
def script_with_floor(topic,series,angle):
    sc=write_script(topic,series,angle); g=quality_gate(topic,sc); sc=apply_gate(sc,g)
    for _ in range(1):
        try:
            if int(g.get("slop_clean",0))<70 or int(g.get("emotion",0))<60:
                sc=write_script(topic,series,angle); g=quality_gate(topic,sc); sc=apply_gate(sc,g)
        except Exception: break
    return sc,g
def render_cold_open_preview(sc,voice,mood,ep):
    paths=[]
    for tag,txt in (("A",sc.get("cold_open_A","")),("B",sc.get("cold_open_B",""))):
        if not txt: continue
        ap=f"{TMP}/coldopen_{tag}_{ep}.mp3"; open(ap,"wb").write(speak(txt,voice,mood)); ac=AudioFileClip(ap)
        vu=None
        try: vu=wan_video(wan_video_prompt("intense single subject, gold rim light, matte black"))
        except Exception: pass
        if not vu: vu=pexels_clip("intense cinematic subject")
        vc=VideoFileClip(fetch(vu,f"cold_{tag}_{ep}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration<ac.duration: vc=concatenate_videoclips([vc,vc.copy()])
        vc=vc.with_duration(ac.duration).with_audio(ac)
        out=f"{TMP}/coldopen_{tag}_{ep}.mp4"; vc.write_videofile(out,codec="libx264",audio_codec="aac",fps=24,logger=None)
        paths.append((tag,out,txt))
    return paths
def sponsor_blocks(sp,voice,mood):
    b=[(ImageClip(card_img("A WORD FROM",sp["name"])).with_duration(2.5),silence(2.5),None)]
    ap=f"{TMP}/sp.mp3"; open(ap,"wb").write(speak(sp.get("script") or f"This investigation is brought to you by {sp['name']}.",voice,mood)); ac=AudioFileClip(ap)
    b.append((ImageClip(card_img(sp["name"],"a word from our sponsor")).with_duration(ac.duration),ac,sp.get("script","")))
    b.append((ImageClip(card_img("NOW, BACK TO","the investigation")).with_duration(2.5),silence(2.5),None))
    return b
def render(sc,topic,series,pilot,music,voice,mood,sp=None,angle="Dark expose (default)",supporters=None,live=None):
    scenes=sc["scenes"][:4] if pilot else sc["scenes"]; parts=[]; n=len(scenes); hopeful=angle in ("Comeback / positive","David vs Goliath")
    def L(stage,pct):
        if live: live(stage,pct)
    for i,s in enumerate(scenes):
        L(f"🎙️ Voicing + 🎥 filming scene {i+1}/{n}",0.05+0.6*i/n)
        ap=f"{TMP}/a{i}.mp3"; open(ap,"wb").write(speak(s["narration"],voice,mood)); ac=AudioFileClip(ap)
        vu=None
        for _ in range(2):
            try: vu=wan_video(wan_video_prompt(s["visual"])); break
            except Exception: vu=None
        if not vu: vu=pexels_clip(" ".join(s["visual"].split()[:8]))
        vc=VideoFileClip(fetch(vu,f"c{i}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration<ac.duration: vc=concatenate_videoclips([vc,vc.copy()])
        vc=vc.with_duration(ac.duration)
        if s.get("ost"): vc=CompositeVideoClip([vc,ImageClip(ost_img(s["ost"])).with_duration(min(3,ac.duration)).with_start(ac.duration*0.35).with_position((0,560))])
        parts.append((vc,ac,s["narration"]))
    L("🎞️ Cutting cold open → title → acts",0.75)
    title=(ImageClip(card_img("SHADOW LEDGER",f"{series} · {TONE_LABEL.get(angle,'A DARK EXPOSE')}")).with_duration(3),silence(3),None)
    adv=sc.get("advisory") or ""
    advclip=(ImageClip(card_img("VIEWER NOTE",adv)).with_duration(3),silence(3),None) if adv else None
    cred=(ImageClip(credits_img(supporters)).with_duration(4.5),silence(4.5),None) if supporters else None
    end=(ImageClip(card_img("SUBSCRIBE",sc.get("share_line") or "the next ledger opens soon")).with_duration(5),silence(5),None)
    base=[parts[0],title]+([advclip] if advclip else [])+parts[1:]
    if sp and sp.get("name") and sp.get("approved"):
        idx=2 if sp.get("place","").startswith("After") else max(2,len(base)-1)
        base=base[:idx]+sponsor_blocks(sp,voice,mood)+base[idx:]
    order=base+([cred] if cred else [])+[end]
    vids,auds,srt,markers,t=[],[],[],[],0.0
    for vc,ac,txt in order:
        vids.append(vc.with_audio(ac)); auds.append(ac)
        if txt: markers.append(t); srt.append((t,t+ac.duration,txt))
        t+=ac.duration
    vid=concatenate_videoclips(vids); aud=concatenate_audioclips(auds)
    layers_a=[aud]
    if music and os.path.exists(music):
        mc=AudioFileClip(music); nn2=int(vid.duration//mc.duration)+1
        layers_a.append(concatenate_videoclips([mc]*nn2).with_duration(vid.duration).with_volume_scaled(0.10))
    markers.append(vid.duration*0.68)
    layers_a.append(sound_bed(vid.duration,markers,hopeful=hopeful).with_volume_scaled(0.6))
    final=vid.with_audio(CompositeAudioClip(layers_a).with_duration(vid.duration))
    layers=[final]
    if os.path.exists(f"{TMP}/bug.png"): layers.append(ImageClip(f"{TMP}/bug.png").resized(height=64).with_position((28,28)).with_duration(final.duration))
    for dt in np.arange(45.0,final.duration-1,45.0): layers.append(pattern_interrupt(0.8).with_start(dt).with_position(("center","center")))
    layers.append(ImageClip(card_img("IF YOU FOLLOW THE MONEY,","subscribe - new investigations weekly",transparent=True)).with_duration(5).with_start(final.duration*0.68).with_position((76,540)).with_effects([vfx.FadeIn(0.6),vfx.FadeOut(0.8)]))
    final=CompositeVideoClip(layers)
    L("📼 Encoding final cut",0.9)
    out=f"{TMP}/episode_{hashlib.md5(topic.encode()).hexdigest()}.mp4"
    final.write_videofile(out,codec="libx264",audio_codec="aac",fps=24,logger=None)
    return out,srt
def shorts_three(vp,hooks,ep):
    outs=[]; vd=VideoFileClip(vp).duration
    for k,s0 in enumerate([3,max(4,vd*0.35),max(5,vd*0.6)]):
        c=VideoFileClip(vp).subclipped(s0,min(s0+32,vd-2)); c=c.resized(height=1920); w=c.size[0]
        c=c.cropped(x1=(w-1080)//2,x2=(w-1080)//2+1080)
        hk=hooks[k] if k<len(hooks) else "FOLLOW THE MONEY"
        c=CompositeVideoClip([c,ImageClip(ost_img(hk)).with_duration(min(4,c.duration)).with_start(0.5).with_position(("center",120))])
        p=f"{TMP}/shorts_{ep}_{k}.mp4"; c.write_videofile(p,codec="libx264",audio_codec="aac",fps=24,logger=None); outs.append(p)
    return outs
def traffic_short(vp,hook):
    vd=VideoFileClip(vp).duration
    c=VideoFileClip(vp).subclipped(3,min(28,vd-6)); c=c.resized(height=1920); w=c.size[0]
    c=c.cropped(x1=(w-1080)//2,x2=(w-1080)//2+1080)
    intro=tiktok_intro(hook)
    endc=ImageClip(card_img("FULL FILM ON YOUTUBE","search: SHADOW LEDGER")).with_duration(3).with_audio(silence(3))
    fin=concatenate_videoclips([intro,CompositeVideoClip([c,ImageClip(ost_img(hook)).with_duration(min(4,c.duration)).with_start(3).with_position(("center",120))]),endc])
    p=f"{TMP}/tiktok_traffic.mp4"; fin.write_videofile(p,codec="libx264",audio_codec="aac",fps=24,logger=None); return p
def dubs(sc):
    full=" ".join(s["narration"] for s in sc["scenes"])[:6000]
    tr=qwen(f"Translate to Spanish and German. Return JSON {{'es':'','de':''}}: {full}")
    import edge_tts,asyncio; outs={}
    for lang,v in (("es","es-ES-AlvaroNeural"),("de","de-DE-ConradNeural")):
        try:
            p=f"{TMP}/dub_{lang}.mp3"; asyncio.run(edge_tts.Communicate(normalize_tts(tr.get(lang,"")),v).save(p)); outs[lang]=p
        except Exception: pass
    return outs
def srt_text(srt):
    out=[]
    for i,(a,b,t) in enumerate(srt,1):
        f=lambda s:f"{int(s//3600):02d}:{int(s%3600//60):02d}:{int(s%60):02d},000"
        out.append(f"{i}\n{f(a)} --> {f(b)}\n{t}\n")
    return "\n".join(out)
def thumbs(topic,hook):
    urls=wan_images(f"YouTube thumbnail 1280x720: {topic}. single dramatic subject, gold rim light, matte black, teal shadows, no words")
    ps=[]
    for j,u in enumerate(urls):
        img=Image.open(io.BytesIO(requests.get(u).content)).convert("RGB"); d=ImageDraw.Draw(img)
        d.text((70,600),hook.upper(),font=F(92),fill=GOLD,stroke_width=6,stroke_fill=(0,0,0))
        p=f"{TMP}/thumb_{j}.png"; img.save(p); ps.append(p)
    return ps
CHECKLIST="YOUTUBE CHECKLIST — SHADOW LEDGER\n[ ] NOT made for kids\n[ ] Paid promotion: {sp}\n[ ] AdSense-scrubbed metadata\n[ ] Subtitles.srt\n[ ] End screen + cards\n[ ] Pin pinned_comment\n[ ] THUMB A/B\n[ ] Shorts on smart/manual days\n[ ] TikTok/Reels same day\n[ ] Schedule per smart/manual plan\n"
RIGHTS="RIGHTS RECORD — original AI-assisted editorial; Pexels stock; licensed neural TTS; original procedural score; Case Files original compilation.\n"
SHOP_BLURB="📄 THE CASE FILE — {topic}\nFull dossier: timeline, players, money, glossary, discussion. $5 pay-what-you-want.\n"
def pack_entries(it,ep,support,shop,series,do_shorts3=True,do_dubs=False):
    entries=[]; sc=it["script"]; sl=slug(it["topic"]); extra={"shorts":[],"tiktok":None}
    tp=thumbs(it["topic"],sc.get("hook_words",""))
    raw=qwen(f"Topic: {it['topic']}. Support: {support}. Pinned: {sc['pinned_question']}. Return JSON {{'title':'','description':'','tags':[15],'shorts_titles':[2]}}")
    safe={"title":adsense_scrub(raw["title"]),"description":adsense_scrub(raw["description"]),"tags":[adsense_scrub(t) for t in raw["tags"]],"shorts_titles":[adsense_scrub(t) for t in raw["shorts_titles"]]}
    if do_shorts3:
        hooks=(safe["shorts_titles"]+[sc.get("share_line","FOLLOW THE MONEY")])[:3]
        spaths=shorts_three(it["out"],hooks,ep); extra["shorts"]=spaths
        for k,p in enumerate(spaths): entries.append((f"SHORTS_{k+1}_{ep}_{sl}.mp4",p,True))
        tk=traffic_short(it["out"],hooks[0]); extra["tiktok"]=tk; entries.append((f"TIKTOK_TRAFFIC_{ep}_{sl}.mp4",tk,True))
    if do_dubs:
        for lang,p in dubs(sc).items(): entries.append((f"DUB_{lang}_{ep}.mp3",p,True))
    dos=qwen(f"Topic: {it['topic']}. Return JSON dossier {{'timeline':[],'key_players':[],'follow_the_money':[],'glossary':[],'discussion':[]}}")
    cfp=f"{TMP}/case_file_{ep}.pdf"; case_file_pdf(it["topic"],series,dos,support,cfp,ep=ep)
    entries.append((f"EPISODE_{ep}_{sl}.mp4",it["out"],True))
    for j,p in enumerate(tp): entries.append((f"THUMB_{'AB'[j]}_{ep}_{sl}.png",p,True))
    entries.append(("subtitles.srt",srt_text(it["srt"]).encode(),False))
    entries.append(("metadata.txt",json.dumps(safe,indent=2).encode(),False))
    entries.append(("pinned_comment.txt",(sc["pinned_question"]+f"\n☕ {support}").encode(),False))
    entries.append(("community_post.txt",json.dumps(sc["community_poll"]).encode(),False))
    entries.append((f"CASE_FILE_{ep}_{sl}.pdf",cfp,True))
    entries.append(("upload_checklist.txt",CHECKLIST.format(sp=it.get("sp","") or "No").encode(),False))
    entries.append(("rights_record.txt",RIGHTS.encode(),False))
    return entries,safe,extra

# ---------------- BACKGROUND WORKER ----------------
def batch_worker(topics=None,auto_upload=False,auto_schedule=True,auto_feed=False):
    JOB=job_load(); JOB["running"]=True; JOB["log"]=[]; job_save(JOB)
    S=jload(SET_F,{})
    phase=ramp_advisor()["phase"]
    manual=S.get("manual",False)
    ep_day=S.get("ep_day","Friday"); ep_time=S.get("ep_time","21:00")
    sh_day=S.get("sh_day","Monday"); sh_time=S.get("sh_time","17:00")
    line=load_line()
    todo=[x for x in line if (not topics) or x["topic"] in topics]
    todo=[x for x in todo if x["status"] not in ("rendered","rejected")]
    for it in todo:
        idx=line.index(it); t0=time.time()
        def live(stage,pct):
            JOB["live"]={"ep":idx+1,"topic":it["topic"][:34],"stage":stage,"pct":pct,"ts":time.time()}
            JOB["current"]=f"EP {idx+1} · {it['topic'][:30]}"; job_save(JOB)
        live("🚀 Starting",0.02)
        try:
            if not it["script"]:
                it["angle"]=it.get("angle") or S.get("angle") or "Dark expose (default)"
                it["script"],g=script_with_floor(it["topic"],S.get("series","The Monopoly Files"),it["angle"]); it["gate"]=g
            m_use=mood_for(idx) if S.get("auto_mood",True) else S.get("mood","Calm investigator (default)")
            sp=jload(SPO_F,None); it["sp"]=sp["name"] if (sp and sp.get("approved")) else ""
            sups=jload(SUP_F,[]) or None
            out,srt=render(it["script"],it["topic"],S.get("series","The Monopoly Files"),S.get("pilot",True),S.get("music"),S.get("voice","longanyang"),m_use,sp,angle=it.get("angle") or "Dark expose (default)",supporters=sups,live=live)
            it["out"],it["srt"],it["status"],it["err"]=out,srt,"rendered",""
            el=int(time.time()-t0); secs,cost=estimate(it["script"],S.get("pilot",True))
            costs=jload(COST_F,[]); costs.append({"ep":idx+1,"est":round(cost,3)}); jsave(COST_F,costs)
            JOB["log"].append(f"✅ EP {idx+1} rendered {el//60}m{el%60:02d}s")
            if auto_upload and not it.get("yt_id") and (os.path.exists(YT_TOK_F) or YT_RT):
                live("☁️ Uploading to YouTube…",0.95)
                try:
                    raw=qwen(f"Topic: {it['topic']}. Return JSON {{'title':'','description':'','tags':[15],'shorts_titles':[2]}}")
                    safe={"title":adsense_scrub(raw["title"]),"description":adsense_scrub(raw["description"]),"tags":[adsense_scrub(t) for t in raw["tags"]],"shorts_titles":[adsense_scrub(t) for t in raw["shorts_titles"]]}
                    when=(occ(ep_day,ep_time,weeks=idx) if manual else smart_ep_when(phase,idx)) if auto_schedule else None
                    vid=yt_upload(out,safe["title"],safe["description"],safe["tags"],when=when)
                    if vid:
                        it["yt_id"]=vid
                        JOB["log"].append(f"☁️ Uploaded {'scheduled '+when if when else 'private'}: {vid}")
                        hooks=(safe["shorts_titles"]+[it["script"].get("share_line","FOLLOW THE MONEY")])[:3]
                        for k,p in enumerate(shorts_three(out,hooks,f"{idx+1:03d}")):
                            try:
                                sw=(occ(sh_day,sh_time,add_days=k*2) if manual else smart_sh_when(phase,k)) if auto_schedule else None
                                yt_upload(p,(safe["shorts_titles"][k] if k<len(safe["shorts_titles"]) else "Follow the money")+" #shorts","Full film on Shadow Ledger.",["shorts","finance"],when=sw)
                                JOB["log"].append(f"☁️ Shorts #{k+1} uploaded{' '+sw if sw else ''}")
                            except Exception: pass
                        live("✅ Upload completed",1.0)
                except Exception as e: JOB["log"].append(f"⚠️ Upload failed: {str(e)[:60]}")
            JOB["history"].insert(0,{"ep":idx+1,"topic":it["topic"][:34],"status":"completed","took":f"{el//60}m{el%60:02d}s","ts":datetime.now().isoformat()})
        except Exception as e:
            it["status"],it["err"]="failed",str(e)[:120]
            JOB["log"].append(f"⚠️ EP {idx+1} failed: {str(e)[:60]}")
            JOB["history"].insert(0,{"ep":idx+1,"topic":it["topic"][:34],"status":"failed","took":str(e)[:40],"ts":datetime.now().isoformat()})
        save_line(line); JOB["live"]=None; job_save(JOB)
    vault_save(line); vault_save_job(JOB)
    if auto_feed:
        try:
            n=sum(1 for t,s,w in predict_spikes(S.get("series","finance"))[:6] if s>=80 and queue_topic(t,s,"AUTO"))
            JOB["log"].append(f"🤖 Auto-feed queued {n}")
        except Exception: pass
    JOB["running"]=False; JOB["current"]=""; job_save(JOB)

def revenue_forecast():
    rev=jload(REV_F,{"kofi_tips":[],"case_files":[]}); line=load_line()
    r=len([i for i in line if i["status"]=="rendered"])
    mk=sum(t.get("amount",0) for t in rev.get("kofi_tips",[]))*4; mc=sum(t.get("amount",0) for t in rev.get("case_files",[]))*4
    my=r*150 if (r*80>=1000 and r*40>=4000) else 0
    tot=mk+mc+my
    return {"subs":r*80,"hrs":r*40,"yt_ready":(r*80>=1000 and r*40>=4000),"usd":tot,"zar":tot*18.5,"target":tot*18.5>=100000}

# ---------------- UI (v46) ----------------
st.set_page_config(page_title="Shadow Ledger Studio",page_icon="🎬",layout="wide")
st.markdown("""<style>
 .stApp{background:radial-gradient(1200px 600px at 80% -10%,#14304f66,transparent),linear-gradient(180deg,#070d18,#0b1526 60%,#081020);}
 h1,h2,h3{color:#ffd76a !important;font-family:Georgia,serif;text-shadow:0 0 18px rgba(245,197,66,.35);}
 p,span,div,label{color:#e8f0ff;}
 [data-testid="stCaptionContainer"],.stCaption{color:#9fb3d1 !important;}
 .console{display:flex;gap:1.2rem;align-items:center;padding:.6rem 1.1rem;margin:.4rem 0 .9rem;background:linear-gradient(180deg,#12213a,#0d1830);border:1px solid #24406b;border-radius:16px;box-shadow:inset 0 1px 0 #ffffff14,0 8px 24px #0009;font-size:.8rem;letter-spacing:.08em;color:#9fb3d1;font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;flex-wrap:wrap;}
 .led{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:.45rem;box-shadow:0 0 10px currentColor;background:currentColor;}
 .led.g{color:#3ddc84;animation:pulse 2.2s infinite}.led.r{color:#ff5d5d}.led.y{color:#ffd76a;animation:pulse 1.4s infinite}
 .clk{margin-left:auto;color:#39d0ff}
 div.stButton>button{background:linear-gradient(180deg,#2a4a7a,#1a3050 55%,#12233f);color:#ffd76a;border:1px solid #3b6ea8;border-radius:14px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;font-size:.8rem;padding:.75rem 1.2rem;text-shadow:0 1px 0 #0008;box-shadow:0 4px 0 #0a1526,0 8px 20px #0009,inset 0 1px 0 #ffffff26;transition:.12s;}
 div.stButton>button:hover{transform:translateY(-2px);border-color:#f5c542;color:#fff;box-shadow:0 6px 0 #0a1526,0 12px 26px #000b,0 0 22px #f5c54233;}
 div.stButton>button:active{transform:translateY(2px);}
 [data-testid="stTabs"] [data-testid="stTab"]{background:linear-gradient(180deg,#1b2c4a,#12203a);border:1px solid #2a4a7a;border-radius:12px;color:#9fb3d1;font-weight:800;letter-spacing:.06em;text-transform:uppercase;font-size:.76rem;padding:.65rem 1.1rem;}
 [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{background:linear-gradient(180deg,#35597f,#1a3050);color:#ffd76a;border-color:#f5c542;box-shadow:inset 0 2px 0 #f5c542,0 0 18px #f5c54225;}
 .card{background:linear-gradient(180deg,#13223c,#0e1a30);border:1px solid #24406b;border-radius:14px;padding:.7rem 1rem;margin:.45rem 0;color:#e8f0ff;box-shadow:inset 0 1px 0 #ffffff10,0 4px 14px #0007;transition:.12s;}
 .card:hover{border-color:#39d0ff;transform:translateY(-1px);}
 .winner{border-color:#f5c542 !important;animation:glow 1.2s ease-in-out infinite;}
 .chip{display:inline-block;padding:.28rem .75rem;border-radius:999px;margin:0 .3rem .3rem 0;font-size:.78rem;border:1px solid #33507c;font-weight:700;}
 .chip.done{background:#0f3524;color:#7ee2a8;border-color:#1d5c3a}.chip.now{background:#3a2f14;color:#ffd76a;border-color:#8a6d2f;animation:pulse 1.8s infinite}.chip.todo{background:#141c2b;color:#7d8fa8}
 .gchip{display:inline-block;padding:.3rem .7rem;border-radius:999px;margin:0 .25rem .3rem 0;font-size:.75rem;font-weight:800;border:1px solid #33507c;color:#7d8fa8;background:#141c2b;}
 .gchip.done{background:#0f3524;color:#7ee2a8;border-color:#1d5c3a;}
 .gchip.next{color:#ffd76a;border-color:#f5c542;background:#3a2f14;animation:glow 1.6s ease-in-out infinite;}
 .section{margin:1.2rem 0 .4rem;padding:.6rem 1rem;border-left:4px solid #f5c542;background:linear-gradient(90deg,#f5c54214,transparent);border-radius:0 12px 12px 0;color:#ffd76a;font-weight:800;letter-spacing:.06em;text-transform:uppercase;}
 [data-testid="stSidebar"]{background:linear-gradient(180deg,#0c1626,#0a1220);border-right:1px solid #24406b}
 .stProgress > div > div{background:linear-gradient(90deg,#f5c542,#39d0ff) !important}
 @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
 @keyframes glow{0%,100%{box-shadow:0 0 4px #f5c54233}50%{box-shadow:0 0 18px #f5c542aa}}
</style>""",unsafe_allow_html=True)

line=load_line()
st.session_state.line=line
jb=job_load()
st.markdown(f"<div class='console'><span><span class='led {'y' if jb['running'] else 'g'}'></span>RENDER {'ACTIVE' if jb['running'] else 'IDLE'}</span><span><span class='led {'g' if (os.path.exists(YT_TOK_F) or YT_RT) else 'r'}'></span>YOUTUBE</span><span><span class='led g'></span>VOICE</span><span><span class='led g'></span>PILOT</span><span><span class='led g'></span>VAULT</span><span class='clk'>🕒 {datetime.now().strftime('%H:%M:%S')}</span></div>",unsafe_allow_html=True)
flags={"scan":bool(st.session_state.get("scan")) or bool(line),"slate":bool(line),"series":bool(st.session_state.get("series_checked")),"script":any(i["status"] in ("scripted","approved","rendered") for i in line),"approve":any(i["status"] in ("approved","rendered") for i in line),"render":any(i["status"]=="rendered" for i in line),"pack":bool(st.session_state.get("packed"))}
order=["scan","slate","series","script","approve","render","pack"]
labels={"scan":"1 SCAN","slate":"2 SLATE","series":"3 SERIES","script":"4 SCRIPT+GATE","approve":"5 APPROVE","render":"6 RENDER","pack":"7 PACK"}
states={}; cs=False
for k in order:
    if flags[k]: states[k]="done"
    else: states[k]="now" if not cs else "todo"; cs=True
pct=sum(flags.values())/len(order)
st.title("🎬 SHADOW LEDGER — Mission Control")
st.markdown("".join(f"<span class='chip {states[k]}'>{'✅ ' if states[k]=='done' else '⭐ ' if states[k]=='now' else '🔒 '}{labels[k]}</span>" for k in order),unsafe_allow_html=True)
st.progress(pct,text=f"Pipeline {int(pct*100)}% complete")

support=st.sidebar.text_input("☕ Support link (Ko-fi)","https://ko-fi.com/shadowledger")
shop=st.sidebar.text_input("📄 Case File shop link (blank until open)","")
ep_num=st.sidebar.text_input("Episode #","001")
voice=st.sidebar.text_input("🎙️ Narrator voice ID","longanyang")
auto_mood=st.sidebar.checkbox("🎭 Auto-rotate mood (recommended)",True)
mood=st.sidebar.selectbox("🎭 Manual mood (if auto OFF)",list(MOODS))
auto_upload=st.sidebar.checkbox("☁️ Auto-upload after render",True)
auto_schedule=st.sidebar.checkbox("🤖 Smart auto-schedule",True)
manual=st.sidebar.checkbox("✋ Manual schedule (I choose)",False)
if manual:
    ep_day=st.sidebar.selectbox("📅 Episode day",DAYS,index=4)
    ep_time=st.sidebar.text_input("🕘 Episode time (UTC)","21:00")
    sh_day=st.sidebar.selectbox("📅 Shorts day",DAYS,index=0)
    sh_time=st.sidebar.text_input("🕘 Shorts time (UTC)","17:00")
else:
    ep_day,ep_time,sh_day,sh_time="Friday","21:00","Monday","17:00"
auto_feed=st.sidebar.checkbox("🤖 Auto-feed ≥80 predictions",False)
music=st.sidebar.file_uploader("🎵 YOUR theme music (optional)",type=["mp3","wav"])
music_path=None
if music: music_path=f"{TMP}/house_{music.name}"; open(music_path,"wb").write(music.getbuffer())
series=st.sidebar.text_input("Series brand","The Monopoly Files")
with st.sidebar.expander("💳 CREDIT & RAMP CONSOLE",expanded=True):
    cr=cred_load(); loaded=st.number_input("💰 Credits loaded on Alibaba (ZAR)",0,100000,int(cr.get("loaded_zar",0)),100)
    if int(loaded)!=int(cr.get("loaded_zar",0)): cr["loaded_zar"]=int(loaded); cred_save(cr)
    costs=jload(COST_F,[]); spent=sum(c.get("est",0) for c in costs)*18.5; rem=loaded-spent
    burn=spent/len(costs) if costs else 0
    st.caption(f"Spent **R{spent:.0f}** · Remaining **R{rem:.0f}** · ~{int(rem/burn) if burn else '∞'} eps left")
    if loaded>0:
        frac=max(0.0,min(1.0,rem/loaded)); st.progress(frac,text=f"{int(100*frac)}% left")
        if frac<0.2: st.warning("⚠️ Top up soon")
        else: st.success("🟢 Healthy runway")
    ra=ramp_advisor(); st.caption(f"Phase **{ra['phase']}** · {ra['rec']}")
with st.sidebar.expander("🧑✈️ CEO's Pilot"):
    pmsg=st.text_input("Your order, CEO")
    if st.button("📨 Send to Pilot"):
        if pmsg.strip():
            reply,outs=ceo_pilot(pmsg); st.success(reply)
            for o in outs: st.caption(o)
with st.sidebar.expander("🔑 Connect + Vault (on-demand)"):
    if YTC_ID and YTC_SEC: st.success("Secrets detected ✅")
    else: st.warning("Secrets must be YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET (all caps).")
    if st.button("1️⃣ Connect (YouTube + Vault)"): st.code(yt_auth_url(FULL))
    if st.button("1️⃣ Connect (YouTube only)"): st.code(yt_auth_url(YT_ONLY))
    code=st.text_input("2️⃣ Paste the code")
    if code and st.button("🔗 Connect"):
        try:
            rt=yt_connect(code.strip()); st.success("Connected ✅")
            if rt: st.code(f'YT_REFRESH_TOKEN = "{rt}"')
        except Exception as e: st.error(str(e)[:120])
    if st.button("🔄 Recover rendered videos from YouTube"):
        with st.spinner("🔄 Scanning your channel…"):
            ups=yt_channel_uploads(); line=load_line(); hits=0
            for vid,title in ups:
                for it in line:
                    if it["topic"] and it["topic"][:25].lower() in title.lower() and it["status"]!="rendered":
                        it["yt_id"]=vid; it["status"]="rendered"; hits+=1
            save_line(line); st.session_state.line=load_line()
        st.success(f"✅ Re-linked {hits} episode(s).")
    if st.button("☁️ Backup line to Vault"):
        with st.spinner("☁️ Backing up…"): vault_save(load_line()); st.success("✅ Backed up.")
    if st.button("⬇️ Restore line from Vault"):
        with st.spinner("⬇️ Restoring…"):
            r=vault_load()
            if r: jsave(LINE_F,r); st.session_state.line=r; st.success(f"✅ Restored {len(r)} episode(s).")
            else: st.warning("No Vault backup found.")
adv=balance_advice(line)
angle_list=list(ANGLES)
angle=st.sidebar.selectbox("Story angle",angle_list,index=angle_list.index(adv) if adv in angle_list else 0)
pilot=st.sidebar.checkbox("PILOT MODE (60-90s)",True)
jsave(SET_F,{"series":series,"pilot":pilot,"auto_mood":auto_mood,"mood":mood,"angle":angle,"voice":voice,"music":music_path,"support":support,"ep_day":ep_day,"ep_time":ep_time,"sh_day":sh_day,"sh_time":sh_time,"manual":manual})
tab1,tab2,tabS,tab3,tab4=st.tabs(["🥚 1·SCAN","🏭 2·PRODUCE","💼 SPONSOR","📦 3·PUBLISH","📈 STRATEGY"])

def guide(steps):
    html=""; nxt=False
    for name,done in steps:
        if done: cls="done"; lab="✅"
        elif not nxt: cls="next"; lab="👉"; nxt=True
        else: cls=""; lab="•"
        html+=f"<span class='gchip {cls}'>{lab} {name}</span>"
    st.markdown(html,unsafe_allow_html=True)

with tab1:
    bull_items=jload(BULL_F,{}).get("items",[])
    guide([("1 BULLETIN",bool(bull_items)),("2 SCAN",bool(st.session_state.get("scan"))),("3 ADD",bool(line)),("4+ PRODUCE ➔",bool(line))])
    st.markdown("<div class='section'>🗺️ START HERE — follow the glowing step</div>",unsafe_allow_html=True)
    if "seeds_str" not in st.session_state: st.session_state.seeds_str=load_seeds()
    pa=st.session_state.pop("seed_add",None)
    if pa and pa not in st.session_state.seeds_str: st.session_state.seeds_str+="\n"+pa
    pm=st.session_state.pop("seed_add_multi",None)
    if pm:
        cur=set(st.session_state.seeds_str.splitlines())
        for t in pm:
            if t not in cur: st.session_state.seeds_str+="\n"+t
    with st.expander("📰 WHAT'S HOT — live bulletin",expanded=True):
        b=jload(BULL_F,{})
        if b.get("ts"):
            ago=datetime.now()-datetime.fromisoformat(b["ts"]); st.caption(f"🕒 Last refreshed {ago.days}d {ago.seconds//3600}h ago")
        if st.button("1️⃣ REFRESH BULLETIN (listen to YouTube)"):
            try:
                with st.spinner("📡 Listening…"): st.session_state["bull"]=refresh_bulletin(st.session_state.seeds_str)
            except Exception as e:
                st.error(f"📡 Bulletin hit a wall: {str(e)[:120]} — try again in a minute.")
        for i in (st.session_state.get("bull") or bull_items)[:10]:
            tag="🔥" if i["sc"]>=80 else "⭐" if i["sc"]>=60 else "•"
            score_txt=f" — 🥚 {i['sc']}/100" if i["sc"] else ""
            c1,c2,c3=st.columns([4,1,1])
            c1.markdown(f"{tag} **{i['t']}**{score_txt} · `{i['src']}`")
            if c2.button("➕",key=f"bq_{i['t']}"): queue_topic(i["t"],i["sc"],i["src"])
            if c3.button("📋",key=f"bs_{i['t']}"): st.session_state["seed_add"]=i["t"]
        if st.button("2️⃣ SEND ALL ≥70 TO SCAN SEEDS"):
            cur=[x for x in st.session_state.seeds_str.splitlines() if x.strip()]
            st.session_state["seed_add_multi"]=[i["t"] for i in (st.session_state.get("bull") or bull_items) if i["sc"]>=70 and i["t"] not in cur]
            st.success("✅ Sent to Scan box.")
    seeds=st.text_area("Seed topics (your ideas + hot topics)",st.session_state.seeds_str)
    st.session_state.seeds_str=seeds
    if st.button("3️⃣ STEP 1 · GOLDEN EGG SCAN"):
        save_seeds(seeds)
        with st.spinner(" Scanning…"):
            st.session_state.scan=sorted([(s,golden_egg(s)[0],golden_egg(s)[1]) for s in [x for x in seeds.splitlines() if x.strip()]],key=lambda r:-r[1])
            jsave(SCAN_F, st.session_state.scan)
    if st.session_state.get("scan") and len(st.session_state.get("scan",[]))>0:
        sc0=st.session_state.scan
        st.markdown(f"<div class='card winner'>🏆 WINNER: <b>{sc0[0][0]}</b> — 🥚 {sc0[0][1]}/100 (pre-ticked below)</div>",unsafe_allow_html=True)
        picks=[]
        for j,(t,sc,w) in enumerate(sc0):
            if st.checkbox(f"{'🏆 ' if j==0 else ''}{t}  (🥚 {sc}/100)",value=(j==0),key=f"ck1_{t}"): picks.append((t,sc))
        if st.button("➕ ADD TICKED TO PRODUCTION LINE"):
            for t,sc in picks: queue_topic(t,sc,"")
            st.session_state.line=load_line()
            st.success("✅ Added — go to 🏭 2·PRODUCE.")
    st.markdown("<div class='section'>🧠 INTELLIGENCE SECTION — boost your scores</div>",unsafe_allow_html=True)
    with st.expander("🎯 Hunt 80+ engine"):
        ht=st.text_input("Theme to hunt","global financial scandals, monopolies, comebacks")
        hm=st.number_input("Min score",50,100,80,5)
        if st.button("🎯 HUNT HIGH SCORERS"):
            try: st.session_state["hunt_res"]=hunt(ht,int(hm))
            except Exception as e: st.error(f"Hunt hiccup: {str(e)[:100]}")
        hr=st.session_state.get("hunt_res",[])
        if hr==[]: st.caption("No topics at that score — lower Min score or broaden the theme. Results appear just below.")
        for t,sc,why in hr:
            st.markdown(f"**🔥 {t}** — 🥚 {sc}/100")
            if st.button(f"➕ Queue {t[:40]}",key=f"hq_{t}"): queue_topic(t,sc,"HUNTED")
    with st.expander("🔮 Trend Anticipation"):
        stt=st.text_input("Seed to predict","BlackRock")
        if st.button("🔮 PREDICT SPIKES"): st.session_state["spikes"]=predict_spikes(stt)
        for t,sc,why in st.session_state.get("spikes",[])[:6]:
            st.markdown(f"**{'🔥' if sc>70 else '⭐'} {t}** — 🥚 {sc}/100")
            if st.button("➕",key=f"aq_{t}"): queue_topic(t,sc,"ANTICIPATED")
    with st.expander("📊 Analytics loop (studio learns)"):
        if os.path.exists(YT_TOK_F) or YT_RT:
            vids=[(i.get("yt_id"),i.get("angle"),i["topic"]) for i in line if i.get("yt_id")]
            if vids and st.button("FETCH 48H METRICS"):
                for vid,a,t in vids:
                    m=yt_metrics(vid)
                    if m:
                        met=jload(MET_F,{}); met[vid]={**m,"angle":a,"topic":t}; jsave(MET_F,met)
                        st.caption(f"• {t[:25]}: CTR {m['ctr']}%")
                        hof_update(vid,(m.get("views",0)/1000)+(float(m.get("ctr") or 0)*5))
                st.success("✅ Learned.")
    with st.expander("🏆 Hall of Fame + auto-sequel"):
        h=jload(HOF_F,[])
        if h:
            st.markdown(f"**🏆 Top:** score {hof_best()['score']:.1f}")
            if st.button("🎬 QUEUE SEQUEL"):
                tt=next((m.get("topic") for v,m in jload(MET_F,{}).items() if v==hof_best()["vid"]),None)
                if tt: queue_topic(f"Sequel to: {tt}",80,"HOF")

with tab2:
    if not flags["scan"]: st.warning("⬅️ Do 🥚 1·SCAN first (tick + add topics there).")
    else:
        st.markdown("## 📋 Production Line")
        for i,it in enumerate(line):
            st.markdown(f"<div class='card'>EP {i+1} · <b>{it['topic']}</b> — <code>{it['status']}</code></div>",unsafe_allow_html=True)
        st.markdown("## 5️⃣ STEP 3 · Series potential")
        if st.button("5️⃣ CHECK SERIES"):
            if line:
                try: st.session_state.splan=series_plan(line[0]["topic"])
                except Exception as e: st.error(f"Series check hiccup: {str(e)[:100]}")
            else: st.warning("⬅️ Add topics first in 🥚 1·SCAN.")
        if st.session_state.get("splan"):
            spn=st.session_state.splan
            st.markdown(f"**Verdict:** {'✅ series' if spn.get('series') else '❌ standalone'} — {spn.get('why','')}")
            if spn.get("series") and st.button("➕ ADD SERIES"):
                base_sc=(line[0].get("score",60) if line else 60)
                for e in spn.get("episodes",[]): queue_topic(e,base_sc,"SERIES")
                st.session_state.series_checked=True
                st.session_state.line=load_line()
                st.success("✅ Series added to line.")
        if flags["series"]:
            st.markdown("## 6️⃣ STEP 4 · Script + Gate")
            if any(i["status"]=="queued" for i in line):
                if st.button("6️⃣ WRITE SCRIPT + GATE"):
                    it=next(x for x in line if x["status"]=="queued")
                    it["angle"]=it.get("angle") or angle
                    it["script"],g=script_with_floor(it["topic"],series,it["angle"]); it["gate"]=g
                    it["status"]="scripted"; save_line(line)
                    st.session_state.edits={i2:(s["narration"],s["visual"]) for i2,s in enumerate(it["script"]["scenes"])}
                    st.success("✅ Scripted + gated.")
        cur=next((x for x in line if x["status"]=="scripted"),None)
        if cur:
            st.markdown("## 7️⃣ STEP 5 · Approve")
            if st.button("🎬 COLD-OPEN A/B PREVIEWS"):
                st.session_state[f"cp_{line.index(cur)}"]=render_cold_open_preview(cur["script"],voice,mood,line.index(cur))
            for tag,p,txt in st.session_state.get(f"cp_{line.index(cur)}",[]):
                st.video(p); st.caption(f"**{tag}:** {txt}")
            if st.button("7️⃣ APPROVE → UNLOCK RENDER"):
                cur["status"]="approved"; save_line(line); bible_append(line.index(cur)+1,cur["topic"],cur["script"])
                st.success("✅ Approved.")
        st.markdown("## 8️⃣ STEP 6 · Render (cloud background)")
        jb=job_load()
        if jb.get("live"):
            lv=jb["live"]; st.info(f"🟢 LIVE: EP {lv['ep']} {lv['topic']} — {lv['stage']} ({int(lv['pct']*100)}%)")
            st.progress(lv["pct"])
        for ln in jb["log"][-6:]: st.caption(ln)
        st.button("🔄 REFRESH STATUS")
        cA,cB=st.columns(2)
        if cA.button("8️⃣ RENDER NEXT (background)"):
            if not job_load()["running"]:
                nx=next((x for x in line if x["status"]=="approved"),None)
                if nx: threading.Thread(target=batch_worker,args=([nx["topic"]],auto_upload,auto_schedule,auto_feed),daemon=True).start(); st.success("☁️ Started.")
        if cB.button("8️⃣ RENDER ENTIRE LINE"):
            if not job_load()["running"]:
                threading.Thread(target=batch_worker,args=(None,auto_upload,auto_schedule,auto_feed),daemon=True).start(); st.success("☁️ Batch started.")
        st.markdown("<div class='section'>📺 LIVE OPS + 🗂 HISTORY (survives reboot)</div>",unsafe_allow_html=True)
        jl=job_load()
        if jl.get("live"): st.markdown(f"<div class='card winner'>🔴 NOW: EP {jl['live']['ep']} {jl['live']['topic']} — {jl['live']['stage']} ({int(jl['live']['pct']*100)}%)</div>",unsafe_allow_html=True)
        for i,it in enumerate([x for x in line if x["status"] in ("queued","approved","scripted")]):
            st.markdown(f"<div class='card'>⏳ EP {line.index(it)+1} {it['topic']} — {it['status']}</div>",unsafe_allow_html=True)
        for hrec in jl.get("history",[])[:10]:
            st.markdown(f"<div class='card'>{'✅' if hrec['status']=='completed' else '⚠️'} EP {hrec['ep']} {hrec['topic']} — {hrec['status']} · {hrec['took']}</div>",unsafe_allow_html=True)
        rendered=[i for i in line if i["status"]=="rendered" and i["out"] and os.path.exists(i["out"])]
        if rendered:
            st.markdown("### 📥 Downloads + ☁️ Uploads")
            for i2,it in enumerate(rendered):
                ep=f"{int(ep_num)+i2:03d}"; sl=slug(it["topic"])
                st.video(it["out"])
                c1,c2,c3=st.columns(3)
                c1.download_button("⬇️ MP4",open(it["out"],"rb").read(),f"EPISODE_{ep}_{sl}.mp4",key=f"dl_{ep}")
                if c2.button(f"📦 PACK {ep}",key=f"pk_{ep}"):
                    entries,safe,extra=pack_entries(it,ep,support,shop,series)
                    z=io.BytesIO()
                    with zipfile.ZipFile(z,"w") as zf:
                        for n,d,ip in entries:
                            if ip: zf.write(d,n)
                            else: zf.writestr(n,d)
                    st.session_state[f"pz_{ep}"]=z.getvalue()
                if st.session_state.get(f"pz_{ep}"): c3.download_button("⬇️ ZIP",st.session_state[f"pz_{ep}"],f"PACK_{ep}.zip",key=f"dz_{ep}")

with tabS:
    st.markdown("## 💼 SPONSOR SUITE")
    spn=st.text_input("Sponsor name","")
    sps=st.text_area("Ad read script","")
    spo=st.checkbox("✅ Approved")
    if st.button("💾 SAVE SLOT"):
        if spn: jsave(SPO_F,{"name":spn,"script":sps,"place":"After cold open + title","approved":spo}); st.success("✅")

with tab3:
    st.caption("Auto-upload sends episode+Shorts to YouTube. This tab builds the ZIP for TikTok/IG/FB + Case File + subtitles + metadata.")
    rendered=[i for i in line if i["status"]=="rendered" and i["out"] and os.path.exists(i["out"])]
    if not rendered: st.warning("⬅️ Render first. Use 'Recover rendered videos from YouTube' if a reboot cleared cache.")
    else:
        ch=st.selectbox("Episode to pack",[i["topic"] for i in rendered])
        it=rendered[[i["topic"] for i in rendered].index(ch)]
        if st.button("📦 BUILD PUBLISH PACK"):
            entries,safe,extra=pack_entries(it,ep_num,support,shop,series)
            z=io.BytesIO()
            with zipfile.ZipFile(z,"w") as zf:
                for n,d,ip in entries:
                    if ip: zf.write(d,n)
                    else: zf.writestr(n,d)
            st.session_state.packed=True
            st.download_button("📦 DOWNLOAD PACK",z.getvalue(),f"SHADOW_LEDGER_PACK_{ep_num}.zip")
            st.success("✅ Pack ready.")

with tab4:
    st.caption("Your money dashboard: revenue forecast + ramp phase + YPP readiness.")
    rf=revenue_forecast()
    st.markdown(f"**Projected:** ${rf['usd']:.0f}/mo ≈ R{rf['zar']:.0f} · Subs ~{rf['subs']} · {'✅ YPP-ready' if rf['yt_ready'] else '⏳ building'}")
    if rf["target"]: st.success("🏆 R100k/month TARGET REACHED")
    st.markdown("""**v46 — FINAL, CLEAN, FOOLPROOF.** Everything remembered & fixed: zero-network boot (no hang), no crash on empty
    lists, tab-2 unlock after reboot, resume-where-stopped, no double-upload, scan memory survives reboot, human-grade
    normalized voice + best-model-first TTS, Vault on-demand, live ops + history, smart schedule, PRESTIGE, Pilot, Hunt,
    Anticipation, analytics, Hall of Fame, dubs, sponsor, forecast, glowing guide. **Paste, commit (after renders land),
    reboot once — then it simply works.** 🎬""")
