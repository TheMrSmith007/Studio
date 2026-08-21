import warnings
warnings.filterwarnings("ignore")
import socket
socket.setdefaulttimeout(20)
import streamlit as st, requests, json, os, io, re, zipfile, hashlib, textwrap, time, base64, threading, uuid, random
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

DASH, YT, PEX = st.secrets.get("DASHSCOPE_API_KEY",""), st.secrets.get("YOUTUBE_API_KEY",""), st.secrets.get("PEXELS_API_KEY","")
PIX = st.secrets.get("PEXABAY_API_KEY","")
GEM = st.secrets.get("GEMINI_API_KEY","")
GRQ = st.secrets.get("GROQ_API_KEY","")
GTTS = st.secrets.get("GOOGLE_TTS_API_KEY","")
YTC_ID = st.secrets.get("YOUTUBE_CLIENT_ID","")
YTC_SEC = st.secrets.get("YOUTUBE_CLIENT_SECRET","")
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
SCAN_F=f"{TMP}/scan.json"; RAMP_F=f"{TMP}/ramp_state.json"
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
ENGINE={"v":""}; VOICE_MODE={"v":"free"}
DISCLOSURE="\n\n— Alleged documents referenced. Not financial advice. Stock footage via Pexels & Pixabay. Original score by Shadow Ledger."
def decide(m):
    d=jload(DEC_F,[]); d.append(m); jsave(DEC_F,d)
def job_load(): return jload(JOB_F,{"running":False,"current":"","log":[],"live":None,"history":[]})
def job_save(j): jsave(JOB_F,j)
def prefs_txt():
    p=jload(PREF_F,[]); return " · ".join(p[-5:]) if p else "No CEO preferences stored yet."
DEFAULT_SEEDS="Private equity firms buying US farmland\nThe hidden fees in your 401(k)\nHow hedge funds bet against your pension\nThe $2 trillion student loan black hole\nBanks profiting from climate disasters\nThe secret world of dark pool trading\nHow AI is manipulating stock prices\nThe truth about ESG investing"
def load_seeds():
    s=jload(SEEDS_F,None); return "\n".join(s) if s else DEFAULT_SEEDS
def save_seeds(t): jsave(SEEDS_F,[x for x in t.splitlines() if x.strip()])
def cred_load(): return jload(CRED_F,{"loaded_zar":0})
def cred_save(d): jsave(CRED_F,d)

def ramp_state_load():
    return jload(RAMP_F,{
        "phase":"WARM-UP",
        "uploaded_count":0,
        "scheduled_count":0,
        "last_upload":None,
        "target_eps":0,
        "auto_mode":False
    })
def ramp_state_save(s):
    jsave(RAMP_F,s)

DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
def occ(day_name,hhmm,add_days=0,weeks=0):
    target=DAYS.index(day_name); d=date.today()
    delta=(target-d.weekday())%7
    dt=d+timedelta(days=delta+add_days+7*weeks)
    hh,mm=[int(x) for x in (hhmm or "21:00").split(":")]
    return datetime(dt.year,dt.month,dt.day,hh,mm).strftime("%Y-%m-%dT%H:%M:00Z")

def ramp_advisor():
    line=load_line()
    ramp=ramp_state_load()
    n=len([i for i in line if i["status"]=="rendered"])
    
    if os.path.exists(YT_TOK_F) or YT_RT:
        try:
            ups=yt_channel_uploads()
            ramp["uploaded_count"]=len(ups)
            ramp["last_upload"]=datetime.now().isoformat()
            ramp_state_save(ramp)
        except Exception: pass
    
    met=jload(MET_F,{}); ctrs=[float(m.get("ctr") or 0) for m in met.values() if m.get("ctr")]
    avg=sum(ctrs)/len(ctrs) if ctrs else 0
    
    if n<2: ph,rec,go="WARM-UP","2 episodes this week",False
    elif n<4: ph,rec,go="BUILD","4 episodes this week",False
    elif n<8: ph,rec,go="SCALE","8 episodes this week",avg>=3.5
    else: ph,rec,go="AGGRESSIVE","12-30 episodes this week",avg>=3.0
    
    if ramp["auto_mode"]:
        weeks = (ramp["target_eps"] - n) // (12 if go else 8)
        rec += f" → {weeks} weeks to complete"
    
    ramp["phase"]=ph
    ramp_state_save(ramp)
    return {"phase":ph,"rec":rec,"go":go,"n":n,"ctr":avg,"ramp":ramp}

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

MOODS={"Calm investigator (default)":"low, calm, intimate documentary voice, slow deliberate pace, slightly breathy, grave tension, LONG PAUSE before every reveal, whisper on key facts",
"Concerned witness":"worried, urgent, leaning in, slightly trembling with concern, as if warning a friend",
"Grave elegy":"mournful, heavy, slow, deep pauses, the voice of a eulogy",
"Cold expose":"clinical, sharp, controlled anger, precise diction, ice-cold delivery",
"Hushed suspense":"near-whisper, tense, every word a secret, long silences",
"Hopeful storyteller":"warm, admiring, quietly triumphant, a smile in the voice"}
EDGE_VOICES={"Calm investigator (default)":("en-US-GuyNeural","-10%"),"Concerned witness":("en-US-AriaNeural","-5%"),"Grave elegy":("en-GB-RyanNeural","-15%"),"Cold expose":("en-US-ChristopherNeural","-8%"),"Hushed suspense":("en-GB-SoniaNeural","-12%"),"Hopeful storyteller":("en-US-JennyNeural","-5%")}
GOOGLE_WAVENET={"Calm investigator (default)":"en-US-Wavenet-D","Concerned witness":"en-US-Wavenet-F","Grave elegy":"en-US-Wavenet-D","Cold expose":"en-US-Wavenet-B","Hushed suspense":"en-US-Wavenet-F","Hopeful storyteller":"en-US-Wavenet-A"}
QWEN_TTS_VOICES=["Cherry","Serena","Ethan","Chelsie"]
MOOD_ROT=list(MOODS.keys())
ANGLES={"Dark expose (default)":"Tone: dark investigative expose.","Mystery / curiosity":"Tone: puzzle-box mystery.","David vs Goliath":"Tone: underdog versus a financial giant.","Comeback / positive":"Tone: triumphant human comeback."}
TONE_LABEL={"Dark expose (default)":"A DARK EXPOSE","Mystery / curiosity":"A MYSTERY","David vs Goliath":"AN UNDERDOG STORY","Comeback / positive":"A COMEBACK"}

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
    t=re.sub(r"([\d,]+)\s*(trillion|billion|million)\b",lambda m:num_to_words(int(m.group(1).replace(',',''))+" "+m.group(2)),t)
    t=re.sub(r"(\d+(?:\.\d+)?)\s*%",lambda m:(num_to_words(int(float(m.group(1))))+" percent"),t)
    return t
def mood_for(i): return MOOD_ROT[i%len(MOOD_ROT)]

def gemini(prompt,sys=None):
    if not GEM: return None
    try:
        full=(sys+"\n\n" if sys else "")+prompt
        r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEM}",json={"contents":[{"parts":[{"text":full}]}],"generationConfig":{"response_mime_type":"application/json"}},timeout=120).json()
        return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
    except Exception: return None
def groq_llm(prompt,sys=None):
    if not GRQ: return None
    try:
        m=([{"role":"system","content":sys}] if sys else [])+[{"role":"user","content":prompt}]
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {GRQ}"},json={"model":"llama-3.1-8b-instant","messages":m,"response_format":{"type":"json_object"}},timeout=120).json()
        return json.loads(r["choices"][0]["message"]["content"])
    except Exception: return None
def qwen(prompt,sys=None):
    for fn in (gemini,groq_llm):
        try:
            r=fn(prompt,sys)
            if r: return r
        except Exception: pass
    m=([{"role":"system","content":sys}] if sys else [])+[{"role":"user","content":prompt}]
    last=None
    for model in chain(r"plus",CHAT_MODELS):
        try:
            r=requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",headers={"Authorization":f"Bearer {DASH}"},json={"model":model,"messages":m,"response_format":{"type":"json_object"}},timeout=120).json()
            return json.loads(r["choices"][0]["message"]["content"])
        except Exception as e: last=e
    raise RuntimeError(f"chat failed: {last}")

YT_ONLY="https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/yt-analytics.readonly"
FULLSCOPE=YT_ONLY+" https://www.googleapis.com/auth/drive.file"
def yt_auth_url(scopes=FULLSCOPE):
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
def vault_load_job():
    try: return drive_read("job.json",_vault_fid())
    except Exception: return None
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
def rebuild_from_youtube():
    ups=yt_channel_uploads(); newl=[]
    for vid,title in ups:
        newl.append({"topic":title,"score":0,"tag":"RECOVERED","status":"rendered","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":"","yt_id":vid})
    return newl

def load_line(): return jload(LINE_F,[])
def save_line(l):
    jsave(LINE_F,l); vault_save(l)
MEM_SRC="local"
if "line" not in st.session_state:
    _l=load_line()
    if _l: MEM_SRC="local"
    else:
        _l=vault_load() or []
        if _l: MEM_SRC="vault"; jsave(LINE_F,_l)
        elif (os.path.exists(YT_TOK_F) or YT_RT):
            try:
                _l=rebuild_from_youtube()
                if _l: MEM_SRC="youtube"
            except Exception: _l=[]
    if _l: jsave(LINE_F,_l); vault_save(_l)
    st.session_state.line=_l
if "edits" not in st.session_state: st.session_state.edits={}
if "scan" not in st.session_state:
    st.session_state.scan=jload(SCAN_F,None)
for _it in st.session_state.line:
    if _it["status"]=="rendered" and not os.path.exists(_it.get("out") or "") and not _it.get("yt_id"):
        _it["status"]="approved"; _it["err"]="media cache cleared — script kept, press render to redo"
jsave(LINE_F, st.session_state.line)
def _match(topic,title):
    t=topic.lower(); ti=title.lower()
    if t[:25] in ti: return True
    words=[w for w in re.findall(r"[a-z0-9]+",t) if len(w)>4]
    return any(w in ti for w in words)
def queue_topic(t,sc,tag):
    line=load_line()
    if t and not any(i["topic"]==t for i in line):
        line.append({"topic":t,"score":sc,"tag":tag,"status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":""})
        save_line(line)
        try: decide(f"Queued '{t[:40]}' ({tag}, score {sc}).")
        except Exception: pass
        return True
    return False

def bible_txt():
    b=jload(BIBLE_F,[])
    if not b: return "No previous episodes yet."
    return " · ".join(f"EP{e['ep']} {e['topic']}: {e.get('callback','')}" for e in b[-4:])
def bible_append(ep,topic,sc):
    try:
        g=qwen(f"Episode topic: {topic}. Script JSON: {json.dumps(sc)[:2500]}. Return JSON {{'facts':[3],'callback':'one sentence','sequel_seed':'one line'}}")
        b=jload(BIBLE_F,[]); b.append({"ep":ep,"topic":topic,"facts":g.get("facts",[]),"callback":g.get("callback",""),"sequel":g.get("sequel_seed","")}); jsave(BIBLE_F,b)
        if g.get("sequel_seed") and ep <= 3:
            queue_topic(f"Sequel to EP{ep}: {g['sequel_seed']}", 80, "AUTO")
    except Exception: pass
def hof_update(vid,score):
    h=jload(HOF_F,[]); h.append({"vid":vid,"score":score}); jsave(HOF_F,h)
def hof_best():
    h=jload(HOF_F,[]); return max(h,key=lambda x:x.get("score",0)) if h else None

# CRITICAL FIX: STORYTELLING DNA PROMPT
DNA="""You are David Attenborough meets Michael Lewis — a master storyteller revealing hidden financial truths.
TOPIC: {topic}
SERIES: {series}
ANGLE: {angle}

RULES:
1. OPEN WITH A HOOK: "What if I told you [SHOCKING FACT]?" or "Imagine [VIVID SCENARIO]"
2. USE ACTIVE VOICE: "BlackRock bought 47,000 homes" (not "Alleged documents show...")
3. ADD EMOTIONAL STAKES: "This affects YOUR rent in Atlanta"
4. INCLUDE SPECIFIC NUMBERS: "47,000 homes", "$8B portfolio"
5. BUILD TENSION: "But the truth is worse..." → "Here's what they don't want you to know"
6. END WITH BINGE-PITCH: "Next week: The teacher who out-traded Wall Street"

STRUCTURE:
- COLD OPEN (15s): Viewer stakes + shocking hook
- ACT I (5 min): The suspect (who? how much?)
- ACT II (10 min): The machine (how it really works)
- ACT III (5 min): The reveal (documents prove...)
- CTA (2 min): Open question + binge-pitch

OUTPUT JSON: {{
    "title_options": ["MAX 60 chars"],
    "hook_words": "MAX 4 WORDS",
    "share_line": "max 10 words",
    "scenes": [
        {{"narration": "ACTIVE VOICE SENTENCE", "visual": "cinematic shot description", "ost": ""}}
    ],
    "pinned_question": "PROVOCATIVE QUESTION",
    "binge_pitch": "NEXT EPISODE TEASE",
    "community_poll": {{"q": "POLL QUESTION", "a": ["OPTION A", "OPTION B"]}},
    "cold_open_A": "max 20 words HOOK",
    "cold_open_B": "max 20 words ALTERNATE HOOK"
}}"""

GATE="""You are SHADOW LEDGER's executive editor + legal + YouTube policy officer. Review script JSON: {script}
FIX slop/legal/viewer-stakes/dragging/clickbait/AdSense. Return JSON {{"slop_clean":0-100,"emotion":0-100,"viewer_stakes":"","legal_flags_fixed":N,"yt_policy":"clean|fixed","clickbait":"clean|fixed","advisory":"","pacing":"","scenes":[same schema],"title_options":[],"share_line":"","cold_open_A":"","cold_open_B":""}}"""

TRIGGERS={"scam":"alleged fraud","scammer":"alleged fraudster","kill":"fatality","murder":"fatality","suicide":"tragic death","terrorist":"extremist","cartel":"syndicate","rape":"assault","steal":"misappropriate","you should":"alleged documents suggest"}
def adsense_scrub(t):
    for b,g in TRIGGERS.items(): t=re.sub(rf"\b{b}\b",g,t,flags=re.IGNORECASE)
    return t

def wan_video_prompt(v): return (f"{v}. cinematic documentary film still, anamorphic 2.39:1, 35mm grain, low-key chiaroscuro, "
    "crushed blacks, gold practicals, teal shadows, slow dolly, photorealistic live-action look, award-winning cinematography, "
    "sharp focus, highly detailed, no morphing, no distortion, ABSOLUTELY no text, no letters, no words, no signage, no captions, no watermark, no logos")

def google_tts(text,mood):
    if not GTTS: return None
    try:
        body={"input":{"text":text},"voice":{"languageCode":"en-US","name":GOOGLE_WAVENET.get(mood,"en-US-Wavenet-D")},"audioConfig":{"audioEncoding":"MP3","speakingRate":0.95,"pitch":-2}}
        r=requests.post(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GTTS}",json=body,timeout=60).json()
        if "audioContent" in r:
            ENGINE["v"]="Google WaveNet — premium free"; return base64.b64decode(r["audioContent"])
    except Exception: pass
    return None
def speak(text,voice,mood):
    text=normalize_tts(text)
    g=google_tts(text,mood)
    if g: return g
    try:
        import edge_tts,asyncio
        v,rr=EDGE_VOICES.get(mood,("en-US-GuyNeural","-10%"))
        p=f"{TMP}/edge_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
        asyncio.run(edge_tts.Communicate(text,v,rate=rr).save(p))
        ENGINE["v"]="Edge Neural (free)"; return open(p,"rb").read()
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
def pixabay_clip(q):
    if not PIX: return None
    try:
        r=requests.get("https://pixabay.com/api/videos/",params={"key":PIX,"q":q,"per_page":5}).json()
        v=r["hits"][0]["videos"]
        k="medium" if "medium" in v else "small" if "small" in v else list(v)[0]
        return v[k]["url"]
    except Exception: return None
def fetch(u,n):
    p=f"{TMP}/{n}"; open(p,"wb").write(requests.get(u).content); return p
def estimate(sc,pilot):
    sc_=sc["scenes"][:4] if pilot else sc["scenes"]; chars=sum(len(s["narration"]) for s in sc_)
    return int(chars/14)+8+len(sc_), len(sc_)*0.06+chars*0.00003
def _scene_clip(visual,footage,idx):
    # ENHANCED CINEMATIC PROMPTS
    cinematic_keywords = [
        "dramatic low angle", "heroic backlight", "tense close-up", 
        "revealing dolly zoom", "ominous Dutch tilt", "hopeful golden hour"
    ]
    q=f"{visual} — {random.choice(cinematic_keywords)}, cinematic film still, anamorphic 2.39:1"
    vu=None
    for src in (pexels_clip,pixabay_clip):
        try:
            vu=src(q)
            if vu: break
        except Exception: vu=None
    if not vu:
        try: vu=pexels_clip("cinematic documentary b-roll")
        except Exception: vu=pixabay_clip("cinematic documentary b-roll")
    return vu
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

# STANDALONE TOPIC GENERATOR (NO YOUTUBE)
def generate_topics():
    TOPIC_BANK = [
        "Private equity firms buying US farmland",
        "The hidden fees in your 401(k)",
        "How hedge funds bet against your pension",
        "The $2 trillion student loan black hole",
        "Banks profiting from climate disasters",
        "The secret world of dark pool trading",
        "How AI is manipulating stock prices",
        "The truth about ESG investing",
        "Pension funds investing in private prisons",
        "The rise of retail investor cartels",
        "How SPACs became money laundering vehicles",
        "The crypto crash that wiped out pensions"
    ]
    scored_topics = []
    for topic in TOPIC_BANK:
        score = 65
        if any(kw in topic.lower() for kw in ["us", "uk", "america", "britain"]):
            score += 15
        if any(kw in topic.lower() for kw in ["ai", "crypto", "esg", "climate"]):
            score += 10
        scored_topics.append({"t": topic, "sc": min(95, score), "src": "AI-PREDICTED"})
    random.shuffle(scored_topics)
    return sorted(scored_topics, key=lambda x: -x["sc"])[:8]

def series_plan(t): return qwen(f"Prestige documentary topic: {t}. Return JSON {{'series':bool,'why':'','episodes':[2-3 distinct titles]}}")
def quality_gate(topic,sc): 
    g=qwen(GATE.format(topic=topic,script=json.dumps(sc)))
    if not g.get("viewer_stakes"):
        g["viewer_stakes"] = f"This investigation affects viewers in the US, UK, and Australia through {topic.split()[0]} costs."
    return g
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

# TIER SYSTEM
def get_tier():
    return jload(SET_F, {}).get("tier", "free")  # free/app_plus/app_pro

def calculate_cost(episodes):
    tier = get_tier()
    if tier == "free":
        return 0
    elif tier == "app_plus":
        return round(episodes * 0.60, 2)  # Google Voice only
    else:  # app_pro
        return round(episodes * 4.55, 2)  # Full Hollywood

# SMART VIDEO GENERATION
def _scene_clip(visual, footage="real", idx=0):
    tier = get_tier()
    if tier == "app_pro" and random.random() < 0.6:
        # 60% AI UNIQUE FOOTAGE (app_pro only)
        return wan_video(f"{visual} — cinematic drone shot, golden hour")
    else:
        # STOCK FOOTAGE (free + app_plus)
        q = f"cinematic documentary b-roll {visual.split('.')[0]}"
        try:
            return pexels_clip(q)
        except:
            return pixabay_clip(q)

# VOICE ENGINE SELECTION
def speak(text, voice, mood):
    tier = get_tier()
    text = normalize_tts(text)
    
    # APP_PLUS & APP_PRO: USE GOOGLE WAVENET
    if tier in ["app_plus", "app_pro"] and GTTS:
        g = google_tts(text, mood)
        if g: 
            ENGINE["v"] = "Google WaveNet — premium"
            return g
    
    # FALLBACK TO FREE VOICES
    try:
        import edge_tts, asyncio
        v, rr = EDGE_VOICES.get(mood, ("en-US-GuyNeural", "-10%"))
        p = f"{TMP}/edge_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
        asyncio.run(edge_tts.Communicate(text, v, rate=rr).save(p))
        ENGINE["v"] = "Edge Neural (free)"
        return open(p, "rb").read()
    except:
        from gtts import gTTS
        p = f"{TMP}/gtts_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
        gTTS(text=text, lang="en").save(p)
        ENGINE["v"] = "Google gTTS (free)"
        return open(p, "rb").read()

# TIER-SPECIFIC SCRIPTING
def write_script(topic, series, angle, bible="", prefs=""):
    tier = get_tier()
    base_prompt = DNA.format(topic=topic, series=series, angle=ANGLES[angle], bible=bible or bible_txt(), prefs=prefs or prefs_txt())
    
    if tier in ["app_plus", "app_pro"]:
        # ADD EMOTIONAL CUES FOR PREMIUM TIERS
        enhanced_prompt = base_prompt + """
7. ADD HUMAN ELEMENTS: 
   - [PAUSE] before key reveals 
   - [BREATH] after emotional statements
   - Whisper on classified facts
   - LONG SILENCE before binge-pitch
"""
        return qwen(enhanced_prompt)
    else:
        return gemini(base_prompt)  # Free tier uses Gemini

# FIXED REVENUE FORECAST
def revenue_forecast():
    # Ensure files exist
    rev=jload(REV_F,{"kofi_tips":[],"case_files":[]})
    line=load_line()
    r=len([i for i in line if i["status"]=="rendered"])
    mk=sum(t.get("amount",0) for t in rev.get("kofi_tips",[]))*4
    mc=sum(t.get("amount",0) for t in rev.get("case_files",[]))*4
    my=r*150 if (r*80>=1000 and r*40>=4000) else 0
    tot=mk+mc+my
    return {
        "subs":r*80,
        "hrs":r*40,
        "yt_ready":(r*80>=1000 and r*40>=4000),
        "usd":tot,
        "zar":tot*18.5,
        "target":tot*18.5>=100000
    }

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
if not jb.get("history") and not jb.get("log"):
    vj=vault_load_job()
    if vj: jb=vj; job_save(jb)
st.markdown(f"<div class='console'><span><span class='led {'y' if jb['running'] else 'g'}'></span>RENDER {'ACTIVE' if jb['running'] else 'IDLE'}</span><span><span class='led {'g' if (os.path.exists(YT_TOK_F) or YT_RT) else 'r'}'></span>YOUTUBE</span><span><span class='led g'></span>VOICE</span><span><span class='led g'></span>PILOT</span><span><span class='led g'></span>VAULT·{MEM_SRC.upper()}</span><span class='clk'>🕒 {datetime.now().strftime('%H:%M:%S')}</span></div>",unsafe_allow_html=True)
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

# SIDEBAR WITH TIER SYSTEM
with st.sidebar:
    st.markdown("### 🎬 PRODUCTION TIER")
    current_tier = get_tier()
    tier_options = {
        "Free": "🆓 Totally free (stock footage + basic voice)",
        "App Plus": "💎 App Plus ($0.60/ep - premium voice + stock footage)", 
        "App Pro": "🚀 App Pro ($4.55/ep - full AI generation)"
    }
    selected_tier = st.radio(
        "Select Tier", 
        options=list(tier_options.keys()),
        format_func=lambda x: f"{x} - {tier_options[x]}",
        index=["free", "app_plus", "app_pro"].index(current_tier)
    )
    
    # SAVE TIER
    if selected_tier != current_tier.replace("_", " ").title():
        tier_map = {"Free": "free", "App Plus": "app_plus", "App Pro": "app_pro"}
        new_tier = tier_map[selected_tier]
        jsave(SET_F, {"tier": new_tier})
        st.rerun()  # FIXED: Use st.rerun() instead of st.experimental_rerun()
    
    # COST DISPLAY
    if selected_tier != "Free":
        st.markdown("### 💰 COST ESTIMATOR")
        episodes = st.slider("Episodes to generate", 1, 8, 4, key="cost_slider")
        cost = calculate_cost(episodes)
        st.markdown(f"**Total Cost: ${cost:.2f}**")
        if selected_tier == "App Plus":
            st.caption("✅ Premium voice only (stock footage)")
        else:
            st.caption("✅ Full AI generation (60% AI + 40% stock)")
    
    support=st.text_input("☕ Support link (Ko-fi)","https://ko-fi.com/shadowledger")
    shop=st.text_input("📄 Case File shop link (blank until open)","")
    ep_num=st.text_input("Episode #","001")
    voice=st.text_input("🎙️ Narrator voice ID","longanyang")
    auto_mood=st.sidebar.checkbox("🎭 Auto-rotate mood (recommended)",True)
    mood=st.sidebar.selectbox("🎭 Manual mood (if auto OFF)",list(MOODS))
    footage_sel=st.sidebar.selectbox("🎥 Footage (FREE first)",["Real stock (Pexels+Pixabay) — FREE & clean","Auto (real + AI mix)","AI-unique (Wan) — paid, unlock below"],index=0)
    FMAP={"Real stock (Pexels+Pixabay) — FREE & clean":"real","Auto (real + AI mix)":"auto","AI-unique (Wan) — paid, unlock below":"ai"}
    voice_mode=st.sidebar.selectbox("🎙️ Voice",["FREE (Google WaveNet/Edge) — R0","PREMIUM (CosyVoice) — ~R5/ep"],index=0)
    auto_upload=st.sidebar.checkbox("☁️ Auto-upload after render",True)
    auto_schedule=st.sidebar.checkbox("🤖 Smart auto-schedule",True)
    interrupts=st.sidebar.checkbox("⚡ Pattern interrupts (subtle)",True)
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
        if st.button("📨 Send to Pilot", key=f"ceo_pilot_{uuid.uuid4().hex[:8]}"):
            if pmsg.strip():
                reply,outs=ceo_pilot(pmsg); st.success(reply)
                for o in outs: st.caption(o)
    with st.sidebar.expander("🔑 Connect + Vault (on-demand)"):
        if YTC_ID and YTC_SEC: st.success("Secrets detected ✅")
        else: st.warning("Secrets must be YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET (all caps).")
        if st.button("1️⃣ Connect (YouTube + Vault)", key=f"connect_yt_vault_{uuid.uuid4().hex[:8]}"):
            st.code(yt_auth_url(FULLSCOPE))
        if st.button("1️⃣ Connect (YouTube only)", key=f"connect_yt_only_{uuid.uuid4().hex[:8]}"):
            st.code(yt_auth_url(YT_ONLY))
        code=st.text_input("2️⃣ Paste the code", key=f"oauth_code_{uuid.uuid4().hex[:8]}")
        if code and st.button("🔗 Connect", key=f"connect_oauth_{uuid.uuid4().hex[:8]}"):
            try:
                rt=yt_connect(code.strip()); st.success("Connected ✅")
                if rt: st.code(f'YT_REFRESH_TOKEN = "{rt}"')
            except Exception as e: st.error(str(e)[:120])
        if st.button("🔄 Recover / rebuild from YouTube", key=f"recover_yt_{uuid.uuid4().hex[:8]}"):
            with st.spinner("🔄 Scanning your channel…"):
                ups=yt_channel_uploads(); cur=load_line(); hits=0
                if not cur:
                    cur=rebuild_from_youtube(); hits=len(cur)
                else:
                    byid={v:t for v,t in ups}
                    for it in cur:
                        if it["status"]=="rendered": continue
                        if it.get("yt_id") and it["yt_id"] in byid:
                            it["status"]="rendered"; hits+=1; continue
                        if it["topic"]:
                            for vid,title in ups:
                                if _match(it["topic"],title):
                                    it["yt_id"]=vid; it["status"]="rendered"; hits+=1; break
                save_line(cur); st.session_state.line=cur
            st.success(f"✅ Recovered {hits} episode(s) from YouTube.")
        if st.button("🆕 NEW PROJECT", key=f"new_project_{uuid.uuid4().hex[:8]}"):
            jsave(LINE_F,[]); vault_save([]); st.session_state.line=[]; st.session_state.rendered_topics=[]; st.success("✅ New project started.")
        if st.button("☁️ Backup line to Vault", key=f"backup_vault_{uuid.uuid4().hex[:8]}"):
            with st.spinner("☁️ Backing up…"): vault_save(load_line()); st.success("✅ Backed up.")
        if st.button("⬇️ Restore line from Vault", key=f"restore_vault_{uuid.uuid4().hex[:8]}"):
            with st.spinner("⬇️ Restoring…"):
                r=vault_load()
                if r: jsave(LINE_F,r); st.session_state.line=r; st.session_state.rendered_topics=[i["topic"] for i in r if i["status"]=="rendered"]; st.success(f"✅ Restored {len(r)} episode(s).")
                else: st.warning("No Vault backup found.")
    with st.sidebar.expander("📈 RAMP DASHBOARD",expanded=True):
        ramp=ramp_state_load()
        st.caption(f"Phase: **{ramp['phase']}**")
        st.caption(f"Uploaded: **{ramp['uploaded_count']}** videos")
        st.caption(f"Scheduled: **{ramp['scheduled_count']}** videos")
        if ramp["auto_mode"]:
            st.success(f"🤖 Auto Monster: {ramp['target_eps']} eps target")
        else:
            st.info(" MANUAL MODE")
    adv=balance_advice(line)
    angle_list=list(ANGLES)
    angle=st.sidebar.selectbox("Story angle",angle_list,index=angle_list.index(adv) if adv in angle_list else 0)
    jsave(SET_F,{"series":series,"pilot":False,"auto_mood":auto_mood,"mood":mood,"angle":angle,"voice":voice,"music":music_path,"support":support,"ep_day":ep_day,"ep_time":ep_time,"sh_day":sh_day,"sh_time":sh_time,"manual":manual,"interrupts":interrupts,"footage":FMAP[footage_sel],"voice_mode":("premium" if voice_mode.startswith("PREMIUM") else "free"),"tier":get_tier()})

# SINGLE TAB SET
tab1,tab2,tabS,tab3,tab4,tab5,tab6=st.tabs(["🥚 1·SCAN","🏭 2·PRODUCE","💼 SPONSOR","📦 3·PUBLISH","📈 STRATEGY","👹 AUTO MONSTER","🚀 SCALE"])

# GOLDEN GOOSE SCANNER TAB (WORKING STANDALONE)
with tab1:
    st.markdown("## 🎯 STEP 1: FIND HIGH-RPM TOPICS")
    st.caption("Generates fresh finance topics with built-in scoring")
    
    TOPIC_BANK = [
        "Private equity firms buying US farmland",
        "The hidden fees in your 401(k)",
        "How hedge funds bet against your pension",
        "The $2 trillion student loan black hole",
        "Banks profiting from climate disasters",
        "The secret world of dark pool trading",
        "How AI is manipulating stock prices",
        "The truth about ESG investing"
    ]
    
    if st.button("🔍 GENERATE HOT TOPICS", key=f"gen_topics_{uuid.uuid4().hex[:8]}"):
        scored_topics = []
        for topic in TOPIC_BANK:
            score = 65
            if any(kw in topic.lower() for kw in ["us", "uk", "america", "britain"]):
                score += 15
            if any(kw in topic.lower() for kw in ["ai", "crypto", "esg", "climate"]):
                score += 10
            scored_topics.append({"t": topic, "sc": min(95, score), "src": "AI-PREDICTED"})
        random.shuffle(scored_topics)
        st.session_state["bull"] = sorted(scored_topics, key=lambda x: -x["sc"])[:8]
        st.success("✅ Generated 8 high-RPM topics!")
    
    bull_items = st.session_state.get("bull", [])
    if bull_items:
        st.markdown("### 🔥 TOP WINNERS (High RPM + Trending)")
        for i, item in enumerate(bull_items):
            emoji = "🟢" if item["sc"] >= 80 else "🟡" if item["sc"] >= 70 else "🔴"
            st.markdown(f"{emoji} **{item['t']}** · 🥚 `{item['sc']}/100`")
            if st.button(f"➕ ADD '{item['t'][:30]}...'", key=f"add_{i}_{uuid.uuid4().hex[:8]}"):
                jsave(LINE_F, [])
                queue_topic(item["t"], item["sc"], item["src"])
                st.session_state.line = load_line()
                st.success(f"✅ Added '{item['t']}' — go to 🏭 2·PRODUCE")
    
    if st.button("🎲 RANDOM FINANCE TOPIC", key=f"random_{uuid.uuid4().hex[:8]}"):
        random_topic = random.choice(TOPIC_BANK)
        score = 75 + random.randint(-10, 15)
        queue_topic(random_topic, score, "RANDOM")
        st.session_state.line = load_line()
        st.success(f"✅ Added '{random_topic}' — go to 🏭 2·PRODUCE")
    
    st.markdown("## 🧹 CLEAN SLATE TOOLS")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🆕 NEW PROJECT (CLEAR ALL)", key=f"new_project_clear_{uuid.uuid4().hex[:8]}"):
            jsave(LINE_F, [])
            jsave(BIBLE_F, [])
            jsave(MET_F, [])
            st.session_state.line = []
            st.success("✅ Production line cleared")
    with c2:
        if st.button("🔄 LOAD SAMPLE TOPICS", key=f"load_sample_{uuid.uuid4().hex[:8]}"):
            sample_topics = [
                {"topic": "Private equity firms buying US farmland", "score": 85, "status": "queued"},
                {"topic": "The hidden fees in your 401(k)", "score": 82, "status": "queued"}
            ]
            jsave(LINE_F, sample_topics)
            st.session_state.line = sample_topics
            st.success("✅ Loaded 2 sample topics")

# PRODUCE TAB (RENDER BUTTON MOVED TO BOTTOM)
with tab2:
    st.markdown("## 📋 Production Line")
    if line:
        for i,it in enumerate(line):
            st.markdown(f"<div class='card'>EP {i+1} · <b>{it['topic']}</b> — <code>{it['status']}</code></div>",unsafe_allow_html=True)
    else:
        st.info("Line is empty — do 🥚 1·SCAN, or use sidebar → Recover/Restore to bring back your work.")
    
    st.markdown("## 5️⃣ STEP 3 · Series potential")
    if st.button("5️⃣ CHECK SERIES"):
        if line:
            try: st.session_state.splan=series_plan(line[0]["topic"])
            except Exception as e: st.error(f"Series check hiccup: {str(e)[:100]}")
        else: st.warning("⬅️ Add topics first in 🥚 1·SCAN.")
    if st.session_state.get("splan"):
        spn=st.session_state.splan
        st.markdown(f"**Verdict:** {'✅ series' if spn.get('series') else '❌ standalone'} — {spn.get('why','')}")
        st.markdown("<div class='section'>📚 SERIES BIBLE — episode plan</div>",unsafe_allow_html=True)
        for i,e in enumerate(spn.get("episodes",[])):
            scr=next((x for x in line if x["topic"]==e and x.get("script")),None)
            prev=scr["script"]["scenes"][0]["narration"][:120] if scr else "script pending…"
            st.markdown(f"<div class='card'><b>EP {i+1} · {e}</b><br/><span style='color:#9fb3d1'>{prev}…</span></div>",unsafe_allow_html=True)
        st.markdown("<div class='section'>📱 SHORTS PLAN — hooks & prompts</div>",unsafe_allow_html=True)
        for i,e in enumerate(spn.get("episodes",[])):
            st.markdown(f"<div class='card'><b>EP{i+1} Shorts:</b> 1) “{e} — the truth” 2) cold-open hook + bass drop 3) reveal teaser → end card “FULL FILM ON YOUTUBE”</div>",unsafe_allow_html=True)
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
    
    # RENDER BUTTONS MOVED TO BOTTOM
    rendered=[i for i in line if i["status"]=="rendered" and (os.path.exists(i.get("out") or "") or i.get("yt_id"))]
    if rendered:
        st.markdown("### 📥 Downloads + ☁️ Uploads + ▶️ Watch")
        for i2,it in enumerate(rendered):
            ep=f"{int(ep_num)+i2:03d}"; sl=slug(it["topic"])
            if it.get("out") and os.path.exists(it["out"]): st.video(it["out"])
            if it.get("yt_id"): st.markdown(f"[▶️ **Watch on YouTube**](https://www.youtube.com/watch?v={it['yt_id']})")
            c1,c2,c3=st.columns(3)
            if it.get("out") and os.path.exists(it["out"]):
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
    
    # LIVE RENDER STATUS (BOTTOM)
    st.markdown("<div class='section'>📺 LIVE OPS + 🗂 HISTORY (permanent via Vault)</div>",unsafe_allow_html=True)
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
    if not jb["running"] and any(x["status"] in ("queued","approved","scripted") for x in line):
        if st.button("▶️ RESUME UNFINISHED BATCH"):
            threading.Thread(target=batch_worker,args=(None,auto_upload,auto_schedule,auto_feed),daemon=True).start(); st.success("☁️ Resumed.")
    jl=job_load()
    if jl.get("live"): st.markdown(f"<div class='card winner'>🔴 NOW: EP {jl['live']['ep']} {jl['live']['topic']} — {jl['live']['stage']} ({int(jl['live']['pct']*100)}%)</div>",unsafe_allow_html=True)
    for i,it in enumerate([x for x in line if x["status"] in ("queued","approved","scripted")]):
        st.markdown(f"<div class='card'>⏳ EP {line.index(it)+1} {it['topic']} — {it['status']}</div>",unsafe_allow_html=True)
    for hrec in jl.get("history",[])[:10]:
        st.markdown(f"<div class='card'>{'✅' if hrec['status']=='completed' else '⚠️'} EP {hrec['ep']} {hrec['topic']} — {hrec['status']} · {hrec['took']}</div>",unsafe_allow_html=True)

# OTHER TABS (KEEP EXISTING CONTENT)
with tabS:
    st.markdown("## 💼 SPONSOR SUITE")
    spn=st.text_input("Sponsor name","")
    sps=st.text_area("Ad read script","")
    spo=st.checkbox("✅ Approved")
    if st.button("💾 SAVE SLOT"):
        if spn: jsave(SPO_F,{"name":spn,"script":sps,"place":"After cold open + title","approved":spo}); st.success("✅")

with tab3:
    st.caption("Auto-upload sends episode+Shorts to YouTube. This tab builds the ZIP for TikTok/IG/FB + Case File + subtitles + metadata.")
    rendered=[i for i in line if i["status"]=="rendered" and i.get("out") and os.path.exists(i["out"])]
    if not rendered: st.warning("⬅️ Render first, or use sidebar → 'Recover / rebuild from YouTube' to relink uploaded episodes.")
    else:
        ch=st.selectbox("Episode to pack",[i["topic"] for i in rendered])
        it=rendered[[i["topic"] for i in rendered].index(ch)]
        if it.get("yt_id"): st.markdown(f"[▶️ **Watch on YouTube**](https://www.youtube.com/watch?v={it['yt_id']})")
        if st.button("📦 BUILD PUBLISH PACK"):
            try:
                entries,safe,extra=pack_entries(it,ep_num,support,shop,series)
                z=io.BytesIO()
                with zipfile.ZipFile(z,"w") as zf:
                    for n,d,ip in entries:
                        if ip: zf.write(d,n)
                        else: zf.writestr(n,d)
                st.session_state.packed=True
                st.download_button("📦 DOWNLOAD PACK",z.getvalue(),f"SHADOW_LEDGER_PACK_{ep_num}.zip")
                st.success("✅ Pack ready.")
            except Exception as e:
                st.error(f"Pack hiccup: {str(e)[:120]} — try again.")

with tab4:
    st.caption("Your money dashboard: revenue forecast + ramp phase + YPP readiness.")
    rf=revenue_forecast()  # NOW WORKS WITHOUT ERRORS
    st.markdown(f"**Projected:** ${rf['usd']:.0f}/mo ≈ R{rf['zar']:.0f} · Subs ~{rf['subs']} · {'✅ YPP-ready' if rf['yt_ready'] else '⏳ building'}")
    if rf["target"]: st.success("🏆 R100k/month TARGET REACHED")
    st.markdown("""**v53 — FREE-TOOLS, MASTERFUL ART.** Google WaveNet voice (free premium) + Gemini/Groq free scripts + Pexels/Pixabay
    real footage + original cinematic sound design (risers/booms/whooshes/drops/swells) + signature edit (letterbox, slow-mo
    reveal, black tension beats, pauses, color grade). Spend-guard caps cost. Permanent memory + recover. This is the
    channel that makes free tools look like a million dollars. 🎬""")

# AUTO MONSTER (TIER-AWARE)
def auto_monster(months=3):
    JOB=job_load(); JOB["running"]=True; job_save(JOB); vault_save_job(JOB)
    ramp=ramp_state_load()
    ramp["auto_mode"]=True
    ramp["target_eps"]=30 * months
    ramp_state_save(ramp)
    
    try:
        st.info(f"🤖 Generating {ramp['target_eps']} episodes ({months} months)...")
        line=load_line()
        
        while len(line) < ramp["target_eps"]:
            bull=generate_topics()
            top_topic = bull[0]["t"] if bull else f"Finance scandal #{len(line)+1}"
            
            series_plan = qwen(f"Prestige documentary topic: {top_topic}. Return JSON {{'episodes':[3]}}")
            for ep_title in series_plan.get("episodes", [top_topic]):
                if len(line) >= ramp["target_eps"]: break
                queue_topic(ep_title, 80, "AUTO_MONSTER")
            line=load_line()
        
        # TIER-AWARE BATCH WORKER
        batch_worker(auto_upload=True, auto_schedule=True, auto_feed=True)
        
        ramp["auto_mode"]=False
        ramp_state_save(ramp)
        JOB["log"].append(f"✅ AUTO MONSTER COMPLETE: {ramp['target_eps']} episodes scheduled")
        st.success(f"🎬 {months}-MONTH CONTENT MACHINE COMPLETE!")
        
    except Exception as e:
        JOB["log"].append(f"⚠️ Auto Monster failed: {str(e)[:100]}")
        st.error(f"Monster hiccup: {str(e)[:100]}")
    finally:
        JOB["running"]=False; job_save(JOB); vault_save_job(JOB)

with tab5:
    st.markdown("## 👹 AUTO MONSTER MODE")
    st.caption("One-click 3-6 months of finance content. Generates, renders, uploads, and schedules everything.")
    
    months = st.slider("📅 Months of content", 3, 6, 3)
    if st.button("🔥 LAUNCH AUTO MONSTER"):
        threading.Thread(target=auto_monster, args=(months,), daemon=True).start()
        st.success("👹 Monster unleashed! Check '2·PRODUCE' for live progress.")
    
    jb=job_load()
    ramp=ramp_state_load()
    if ramp["auto_mode"]:
        st.info(f"🟢 MONSTER ACTIVE: {ramp['uploaded_count']}/{ramp['target_eps']} uploaded")
        st.progress(ramp["uploaded_count"]/ramp["target_eps"])
    
    if st.button("⏹️ STOP AUTO MONSTER"):
        ramp["auto_mode"]=False
        ramp_state_save(ramp)
        st.success("Monster paused. Manual mode restored.")

# SCALE TAB (NEW)
with tab6:
    st.markdown("## 🚀 EPISODE SCALING CONTROLLER")
    st.caption("Lock your monthly output & spending")
    
    tier = get_tier()
    if tier == "free":
        st.info("💡 Switch to **App Plus** or **App Pro** in sidebar to unlock scaling")
        episodes = st.slider("Episodes to generate", 1, 8, 4, disabled=True)
        cost = 0
    else:
        # CALCULATE MAX EPISODES BASED ON CREDITS
        if "cred_loaded" in st.session_state:
            max_eps = min(32, int(st.session_state.cred_loaded / (0.60 if tier=="app_plus" else 4.55)))
        else:
            max_eps = 32
        
        episodes = st.slider("Episodes to generate", 4, max_eps, min(8, max_eps), 4)
        cost = calculate_cost(episodes)
        st.markdown(f"### 💰 Total Cost: **${cost:.2f}**")
    
    if episodes > 0 and tier != "free":
        if st.button(f"🎬 GENERATE {episodes} EPISODES", key="scale_gen"):
            with st.spinner(f"Generating {episodes} episodes..."):
                topics = []
                for i in range(episodes):
                    bull = generate_topics()
                    topics.append(bull[0]["t"])
                
                jsave(LINE_F, [])
                for t in topics:
                    queue_topic(t, 85, "SCALED")
                
                st.session_state.line = load_line()
                st.success(f"✅ {episodes} episodes queued! Go to 🏭 2·PRODUCE to render")
