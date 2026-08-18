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
DEFAULT_SEEDS="BlackRock buying housing\nTicketmaster Live Nation monopoly\nThe janitor who left $6 million to his hospital\nHow Norway became the world's landlord\nThe teacher who out-traded Wall Street\nBoeing whistleblowers"
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

def golden_egg(topic):
    s=yt("search",part="snippet",q=topic,type="video",maxResults=10,order="viewCount")
    ids=[i["id"]["videoId"] for i in s.get("items",[])]
    if not ids: return 50,"no data"
    vs=yt("videos",part="statistics,snippet",id=",".join(ids))["items"]
    if not vs: return 50,"no data"
    
    geo_bonus = 0
    for v in vs:
        title = v["snippet"]["title"].lower()
        if any(c in title for c in ["usa","us","america","uk","britain","australia","au"]):
            geo_bonus += 3
    geo_bonus = min(15, geo_bonus)
    
    views=[int(v["statistics"]["viewCount"]) for v in vs]
    demand=min(45,int(sum(views)/len(views)/1e6*9))
    fresh=min(20,int(sum(1 for v in vs if (datetime.now()-datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z","")))<timedelta(days=730))*2.5))
    chans={v["snippet"]["channelId"] for v in vs}; comp=max(0,20-len(chans)*2)
    bo=min(15,sum(1 for v in vs if int(v["statistics"]["viewCount"])>200000)*5)
    
    total = min(100, demand+fresh+comp+bo+geo_bonus)
    return total, f"demand {demand}/45 · geo {geo_bonus} · proof {bo}/15"

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
    # CRITICAL FIX: SPECIFIC VISUAL PROMPTS
    q=f"cinematic drone shot of {visual.split('.')[0]} — specific location, golden hour, teal shadows"
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
def write_script(topic,series,angle,bible="",prefs=""):
    return qwen(DNA.format(topic=topic,series=series,angle=ANGLES[angle],bible=bible or bible_txt(),prefs=prefs or prefs_txt()))

def card_img(title,sub="",w=1280,h=720,transparent=False):
    img=Image.new("RGBA" if transparent else "RGB",(w,h),(0,0,0,0) if transparent else BLACK)
    d=ImageDraw.Draw(img)
    if not transparent: d.rectangle([0,h//2-90,w,h//2+90],fill=(8,9,12))
    d.text((w//2,h//2-30),title,font=F(64),fill=GOLD,anchor="mm")
    if sub: d.text((w//2,h//2+50),sub,font=F(30),fill=(220,220,220),anchor="mm")
    d.rectangle([w//2-260,h//2+95,w//2+260,h//2+98],fill=GOLD)
    return np.array(img)

def vcard_img(title,sub=""):
    img=Image.new("RGB",(1080,1920),BLACK); d=ImageDraw.Draw(img)
    d.rectangle([60,820,1020,1100],fill=(8,9,12))
    for k,ln in enumerate(textwrap.wrap(title,18)[:4]): d.text((540,880+k*70),ln.upper(),font=F(56),fill=GOLD,anchor="mm")
    if sub:
        for k,ln in enumerate(textwrap.wrap(sub,24)[:3]): d.text((540,1140+k*50),ln,font=F(34),fill=(220,220,220),anchor="mm")
    d.rectangle([420,1180,660,1186],fill=GOLD)
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

def vost_img(text):
    img=Image.new("RGBA",(1080,100),(0,0,0,0)); d=ImageDraw.Draw(img)
    lines = textwrap.wrap(text.upper(), 35)
    y = 50
    for line in lines:
        d.text((540, y), line, font=F(28), fill=GOLD, anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        y += 32
    return np.array(img)

def pattern_interrupt(dur=0.6):
    img=Image.new("RGBA",(1280,720),(0,0,0,0)); d=ImageDraw.Draw(img)
    d.rectangle([0,640,1280,720],fill=(0,0,0,150))
    d.rectangle([40,676,560,684],fill=GOLD)
    d.text((60,660),"FOLLOW THE MONEY",font=F(28),fill=GOLD,anchor="lm")
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
    img,d=blank(); d.text((W//2,800),"STAND WITH THE LEDGER",font=F(60),fill=GOLD,anchor="mm"); 
    d.text((W//2,900),f"Tips & Case Files: {support}",font=F(30),fill=GOLD,anchor="mm")
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
    n=int(dur*SR); t=np.arange(n)/SR
    root=55.0 if not hopeful else 65.4
    pad=0.0
    for off in (0,3,5,7):
        f=root*(2**(off/12.0))
        pad+=0.05*np.sin(2*np.pi*f*t)*(0.7+0.3*np.sin(2*np.pi*0.07*t+off))
    swell=np.zeros(n)
    swell[:int(3*SR)]+=np.linspace(0,1,int(3*SR))
    swell[int(max(0,dur-4)*SR):]+=np.linspace(1,0,n-int(max(0,dur-4)*SR))
    pad*=(0.6+0.8*swell)
    bass=0.14*np.sin(2*np.pi*(root/2)*t)*(0.5+0.5*(np.sin(2*np.pi*2.0*t)>0))
    rng=np.random.default_rng(7); hats=np.zeros(n)
    step=int(0.5*SR); tk=int(0.02*SR); tt=np.arange(tk)/SR
    hat=0.05*rng.standard_normal(tk)*np.exp(-120*tt)
    for s in range(0,n-tk,step): hats[s:s+tk]+=hat
    bed=pad+bass+hats
    for m in markers:
        s,e=int(m*SR),min(n,int((m+1.8)*SR)); tt=np.arange(e-s)/SR
        bed[s:e]+=0.5*np.sin(2*np.pi*40*tt)*np.exp(-2.5*tt)
        w=int(0.4*SR); s=int(m*SR); e=min(n,s+w)
        bed[s:e]+=0.2*rng.standard_normal(e-s)*np.exp(-np.linspace(0,6,e-s))
        s=int(max(0,m-0.4)*SR); e=int(m*SR)
        bed[s:e]*=0.15
    bed=bed/np.max(np.abs(bed))*0.8
    return AudioArrayClip(np.stack([bed,bed],axis=1),fps=SR)

def render_cold_open_preview(sc,voice,mood,ep):
    paths=[]
    for tag,txt in (("A",sc.get("cold_open_A","")),("B",sc.get("cold_open_B",""))):
        if not txt: continue
        ap=f"{TMP}/coldopen_{tag}_{ep}.mp3"; open(ap,"wb").write(speak(txt,voice,mood)); ac=AudioFileClip(ap)
        vu=_scene_clip("intense single subject, gold rim light, matte black","real",0)
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

def render(sc,topic,series,pilot,music,voice,mood,sp=None,angle="Dark expose (default)",supporters=None,live=None,interrupts=True,footage="real"):
    # CRITICAL FIX: ALWAYS USE FULL SCENES (IGNORE PILOT MODE)
    scenes=sc["scenes"]  # ← THIS LINE FIXES 1-MINUTE VIDEOS
    parts=[]; n=len(scenes); hopeful=angle in ("Comeback / positive","David vs Goliath")
    def L(stage,pct):
        if live: live(stage,pct)
    for i,s in enumerate(scenes):
        L(f"🎙️ Voicing + 🎥 filming scene {i+1}/{n}",0.05+0.6*i/n)
        ap=f"{TMP}/a{i}.mp3"; open(ap,"wb").write(speak(s["narration"],voice,mood)); ac=AudioFileClip(ap)
        vu=_scene_clip(s["visual"],footage,i)
        vc=VideoFileClip(fetch(vu,f"c{i}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration<ac.duration: vc=concatenate_videoclips([vc,vc.copy()])
        vc=vc.with_duration(ac.duration)
        if s.get("ost"): vc=CompositeVideoClip([vc,ImageClip(ost_img(s["ost"])).with_duration(min(3,ac.duration)).with_start(ac.duration*0.35).with_position((0,560))])
        parts.append((vc,ac,s["narration"]))
    L("🎞️ Cutting cold open → title → acts",0.75)
    title=(ImageClip(card_img("SHADOW LEDGER",f"{series} · {TONE_LABEL.get(angle,'A DARK EXPOSE')}")).with_duration(3),silence(3),None)
    adv=sc.get("advisory") or ""
    if adv:
        adv_img = Image.new("RGB", (1280, 40), (8, 9, 12))
        d = ImageDraw.Draw(adv_img)
        lines = textwrap.wrap(adv, width=60)
        y = 20
        for line in lines:
            d.text((640, y), line.upper(), font=F(20), fill=GOLD, anchor="mm")
            y += 25
        advclip=(ImageClip(np.array(adv_img)).with_duration(3),silence(3),None)
    else:
        advclip=None
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
        layers_a.append(concatenate_videoclips([mc]*nn2).with_duration(vid.duration).with_volume_scaled(0.12))
    markers.append(vid.duration*0.68)
    layers_a.append(sound_bed(vid.duration,markers).with_volume_scaled(0.3))
    final=vid.with_audio(CompositeAudioClip(layers_a).with_duration(vid.duration))
    layers=[final]
    if os.path.exists(f"{TMP}/bug.png"): layers.append(ImageClip(f"{TMP}/bug.png").resized(height=64).with_position((28,28)).with_duration(final.duration))
    bar=70
    layers.append(ImageClip(np.zeros((bar,1280,3),dtype=np.uint8)).with_duration(final.duration).with_position((0,0)))
    layers.append(ImageClip(np.zeros((bar,1280,3),dtype=np.uint8)).with_duration(final.duration).with_position((0,720-bar)))
    final=CompositeVideoClip(layers)
    L("📼 Encoding final cut",0.9)
    # CRASH PROTECTION: ENSURE MINIMUM DURATION
    if final.duration < 60:
        st.warning("⚠️ Video too short! Adding filler scenes...")
        filler = ColorClip((1280,720), color=(0,0,0), duration=60-final.duration)
        final = concatenate_videoclips([final, filler])
    out=f"{TMP}/episode_{hashlib.md5(topic.encode()).hexdigest()}.mp4"
    final.write_videofile(out,codec="libx264",audio_codec="aac",fps=24,logger=None)
    return out,srt

def shorts_blockbuster(vp,hooks,ep,voice,mood,cold_open):
    outs=[]; vd=VideoFileClip(vp).duration
    # CRITICAL FIX: 5-MINUTE SHORTS STRUCTURE
    segments = [
        (0, min(15, vd)),           # Cold open (15s)
        (15, min(135, vd)),         # Act I (2 min)
        (135, min(255, vd)),        # Act II (2 min)
        (255, min(vd, 300))         # CTA (30s)
    ]
    for k, (start, end) in enumerate(segments):
        if start >= end: continue
        hk = hooks[k] if k < len(hooks) else "FOLLOW THE MONEY"
        intro = ImageClip(vcard_img("SHADOW LEDGER", hk)).with_duration(1.2).with_effects([vfx.FadeIn(0.3)])
        hook_txt = cold_open or hk
        ap = f"{TMP}/shook_{ep}_{k}.mp3"
        open(ap,"wb").write(speak(hook_txt,voice,mood))
        hac = AudioFileClip(ap)
        c = VideoFileClip(vp).subclipped(start, end)
        c = c.resized(height=1920)
        w = c.size[0]
        c = c.cropped(x1=(w-1080)//2, x2=(w-1080)//2+1080)
        ov = ImageClip(vost_img(hk)).with_duration(min(2.5, c.duration)).with_start(0.2).with_position((0, 450))
        endc = ImageClip(vcard_img("FULL INVESTIGATION","on Shadow Ledger")).with_duration(1.8).with_effects([vfx.FadeIn(0.3)])
        vis = concatenate_videoclips([intro, CompositeVideoClip([c,ov]), endc])
        total = vis.duration
        bed = sound_bed(total, [1.2 + 1])
        hookclip = hac.with_start(1.2)
        fin = vis.with_audio(CompositeAudioClip([bed.with_volume_scaled(0.4), hookclip]).with_duration(total))
        p = f"{TMP}/shorts_{ep}_{k}.mp4"
        fin.write_videofile(p, codec="libx264", audio_codec="aac", fps=24, logger=None)
        outs.append(p)
    return outs

def traffic_short(vp,hook):
    return shorts_blockbuster(vp,[hook],"tiktok","longanyang","Calm investigator (default)",hook)[0]

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
    ps=[]; hk=(hook or "FOLLOW THE MONEY").upper()
    img=Image.new("RGB",(1280,720),BLACK)
    d=ImageDraw.Draw(img)
    d.text((70,200),topic[:40],font=F(72),fill=GOLD)
    d.text((70,500),hk,font=F(92),fill=GOLD,stroke_width=6,stroke_fill=(0,0,0))
    p=f"{TMP}/thumb_A.png"; img.save(p); ps.append(p)
    img2=Image.new("RGB",(1280,720),BLACK)
    d2=ImageDraw.Draw(img2)
    d2.text((70,300),f"SHADOW\nLEDGER",font=F(80),fill=GOLD)
    d2.text((70,500),topic[:30],font=F(60),fill=(220,220,220))
    p2=f"{TMP}/thumb_B.png"; img2.save(p2); ps.append(p2)
    return ps

CHECKLIST="YOUTUBE CHECKLIST — SHADOW LEDGER\n[ ] NOT made for kids\n[ ] Paid promotion: {sp}\n[ ] AdSense-scrubbed metadata\n[ ] Subtitles.srt\n[ ] End screen + cards\n[ ] Pin pinned_comment\n[ ] THUMB A/B\n[ ] Shorts on smart/manual days\n[ ] TikTok/Reels same day\n[ ] Schedule per smart/manual plan\n"
RIGHTS="RIGHTS RECORD — real stock footage via Pexels & Pixabay (free commercial licenses); licensed/Google neural TTS; original procedural score & sound design; Case Files original compilation.\n"
SHOP_BLURB="📄 THE CASE FILE — {topic}\nFull dossier: timeline, players, money, glossary, discussion. $5 pay-what-you-want.\n"

def pack_entries(it,ep,support,shop,series,do_shorts3=True,do_dubs=False):
    entries=[]; sc=it["script"]; sl=slug(it["topic"]); extra={"shorts":[],"tiktok":None}
    tp=thumbs(it["topic"],sc.get("hook_words",""))
    try:
        raw=qwen(f"Topic: {it['topic']}. Support: {support}. Pinned: {sc['pinned_question']}. Return JSON {{'title':'','description':'','tags':[15],'shorts_titles':[2]}}")
    except Exception:
        raw={"title":it["topic"][:60],"description":f"{it['topic']} — a Shadow Ledger investigation. {support}","tags":["finance","documentary"],"shorts_titles":[]}
    safe={"title":adsense_scrub(raw.get("title",it["topic"][:60])),"description":adsense_scrub(raw.get("description","")),"tags":[adsense_scrub(t) for t in raw.get("tags",[])],"shorts_titles":[adsense_scrub(t) for t in raw.get("shorts_titles",[])]}
    voice=jload(SET_F,{}).get("voice","longanyang")
    if do_shorts3:
        hooks=(safe["shorts_titles"]+[sc.get("share_line","FOLLOW THE MONEY")])[:3]
        spaths=shorts_blockbuster(it["out"],hooks,ep,voice,"Calm investigator (default)",sc.get("cold_open_A",""))
        extra["shorts"]=spaths
        for k,p in enumerate(spaths): entries.append((f"SHORTS_{k+1}_{ep}_{sl}.mp4",p,True))
        tk=traffic_short(it["out"],hooks[0]); extra["tiktok"]=tk; entries.append((f"TIKTOK_TRAFFIC_{ep}_{sl}.mp4",tk,True))
    if do_dubs:
        for lang,p in dubs(sc).items(): entries.append((f"DUB_{lang}_{ep}.mp3",p,True))
    try:
        dos=qwen(f"Topic: {it['topic']}. Return JSON dossier {{'timeline':[],'key_players':[],'follow_the_money':[],'glossary':[],'discussion':[]}}")
    except Exception:
        dos={"timeline":[],"key_players":[],"follow_the_money":[],"glossary":[],"discussion":[]}
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

def batch_worker(topics=None,auto_upload=False,auto_schedule=True,auto_feed=False):
    JOB=job_load(); JOB["running"]=True; JOB["log"]=[]; job_save(JOB); vault_save_job(JOB)
    S=jload(SET_F,{})
    phase=ramp_advisor()["phase"]
    manual=S.get("manual",False)
    interrupts=S.get("interrupts",True)
    footage=S.get("footage","real")
    VOICE_MODE["v"]=S.get("voice_mode","free")
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
            # CRITICAL FIX: FORCE FULL EPISODES (NO PILOT MODE)
            out,srt=render(it["script"],it["topic"],S.get("series","The Monopoly Files"),False,S.get("music"),S.get("voice","longanyang"),m_use,sp,angle=it.get("angle") or "Dark expose (default)",supporters=sups,live=live,interrupts=interrupts,footage=footage)
            it["out"],it["srt"],it["status"],it["err"]=out,srt,"rendered",""
            el=int(time.time()-t0); secs,cost=estimate(it["script"],False)  # ← PILOT=FALSE
            costs=jload(COST_F,[]); costs.append({"ep":idx+1,"est":round(cost,3)}); jsave(COST_F,costs)
            JOB["log"].append(f"✅ EP {idx+1} rendered {el//60}m{el%60:02d}s")
            save_line(line); vault_save(line)
            if auto_upload and not it.get("yt_id") and (os.path.exists(YT_TOK_F) or YT_RT):
                live("☁️ Uploading to YouTube…",0.95)
                try:
                    raw=qwen(f"""Topic: {it['topic']}. 
Return JSON {{
    'title':'MAX 60 chars, include USA/UK if relevant',
    'description':'3 sentences. First: hook. Second: key facts. Third: CTA with shop link.',
    'tags':['finance','documentary',...15 total],
    'shorts_titles':[2]
}}""")
                    safe={
                        "title": adsense_scrub(raw["title"]),
                        "description": f"{adsense_scrub(raw['description'])}\n\n🔍 Covers: {', '.join(raw['tags'][:5])}. Support independent journalism: {support}",
                        "tags": raw["tags"] + ["finance documentary", "money exposé", "wall street secrets", "usa finance", "uk economy"],
                        "shorts_titles": [adsense_scrub(t) for t in raw["shorts_titles"]]
                    }
                    when=(occ(ep_day,ep_time,weeks=idx) if manual else smart_ep_when(phase,idx)) if auto_schedule else None
                    vid=yt_upload(out,safe["title"],safe["description"],safe["tags"][:20],when=when)
                    if vid:
                        it["yt_id"]=vid
                        JOB["log"].append(f"☁️ Uploaded {'scheduled '+when if when else 'private'}: {vid}")
                        hooks=(safe["shorts_titles"]+[it["script"].get("share_line","FOLLOW THE MONEY")])[:3]
                        spaths=shorts_blockbuster(out,hooks,f"{idx+1:03d}",S.get("voice","longanyang"),m_use,it["script"].get("cold_open_A",""))
                        for k,p in enumerate(spaths):
                            try:
                                sw=(occ(sh_day,sh_time,add_days=k*2) if manual else smart_sh_when(phase,k)) if auto_schedule else None
                                yt_upload(p,(safe["shorts_titles"][k] if k<len(safe["shorts_titles"]) else "Follow the money")+" #shorts","Full film on Shadow Ledger.",["shorts","finance"],when=sw)
                                JOB["log"].append(f"☁️ Shorts #{k+1} uploaded{' '+sw if sw else ''}")
                            except Exception: pass
                        live("✅ Upload completed",1.0)
                except Exception as e: JOB["log"].append(f"⚠️ Upload failed: {str(e)[:60]}")
            save_line(line); vault_save(line)
            JOB["history"].insert(0,{"ep":idx+1,"topic":it["topic"][:34],"status":"completed","took":f"{el//60}m{el%60:02d}s","ts":datetime.now().isoformat()})
            vault_save_job(JOB)
        except Exception as e:
            it["status"],it["err"]="failed",str(e)[:120]
            JOB["log"].append(f"⚠️ EP {idx+1} failed: {str(e)[:60]}")
            JOB["history"].insert(0,{"ep":idx+1,"topic":it["topic"][:34],"status":"failed","took":str(e)[:40],"ts":datetime.now().isoformat()})
            vault_save_job(JOB)
        save_line(line); JOB["live"]=None; job_save(JOB)
    vault_save(line); vault_save_job(JOB)
    if auto_feed:
        try:
            n=sum(1 for t,s,w in predict_spikes(S.get("series","finance"))[:6] if s>=80 and queue_topic(t,s,"AUTO"))
            JOB["log"].append(f"🤖 Auto-feed queued {n}")
        except Exception: pass
    JOB["running"]=False; JOB["current"]=""; job_save(JOB); vault_save_job(JOB)

def revenue_forecast():
    rev=jload(REV_F,{"kofi_tips":[],"case_files":[]}); line=load_line()
    r=len([i for i in line if i["status"]=="rendered"])
    mk=sum(t.get("amount",0) for t in rev.get("kofi_tips",[]))*4; mc=sum(t.get("amount",0) for t in rev.get("case_files",[]))*4
    my=r*150 if (r*80>=1000 and r*40>=4000) else 0
    tot=mk+mc+my
    return {"subs":r*80,"hrs":r*40,"yt_ready":(r*80>=1000 and r*40>=4000),"usd":tot,"zar":tot*18.5,"target":tot*18.5>=100000}

def yt_upload(path,title,desc,tags,when=None,thumb=None):
    from googleapiclient.http import MediaFileUpload
    svc=yt_service()
    if not svc: return None
    
    seo_desc = f"{desc}\n\n🔍 This investigation covers: {', '.join(tags[:5])}. Support independent journalism: {support}"
    seo_tags = tags + ["finance documentary", "money exposé", "wall street secrets", "usa finance", "uk economy"]
    
    body={
        "snippet":{
            "title": title,
            "description": seo_desc + DISCLOSURE,
            "tags": seo_tags[:20],
            "categoryId":"25"
        },
        "status":{
            "privacyStatus":"private",
            "selfDeclaredMadeForKids":False
        }
    }
    if when: body["status"]["publishAt"]=when
    resp=svc.videos().insert(part="snippet,status",body=body,media_body=MediaFileUpload(path,mimetype="video/mp4",resumable=True)).execute()
    vid=resp["id"]
    
    ramp=ramp_state_load()
    ramp["uploaded_count"]+=1
    ramp["scheduled_count"]+=1
    ramp_state_save(ramp)
    
    if thumb:
        try: svc.thumbnails().set(videoId=vid,media_body=MediaFileUpload(thumb,mimetype="image/png")).execute()
        except Exception: pass
    return vid

def smart_ep_when(phase,idx):
    ramp=ramp_state_load()
    base_weeks = idx // (12 if phase=="AGGRESSIVE" else 8 if phase=="SCALE" else 4 if phase=="BUILD" else 2)
    
    if phase=="AGGRESSIVE":
        days = ["Friday","Wednesday","Monday"]
    elif phase=="SCALE":
        days = ["Friday","Tuesday"]
    else:
        days = ["Friday"]
    
    day = days[idx % len(days)]
    return occ(day,"21:00",weeks=base_weeks)

def smart_sh_when(phase,k):
    days = ["Monday","Wednesday","Friday"]
    day = days[k % len(days)]
    return occ(day,"17:00",weeks=k//3)

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

support=st.sidebar.text_input("☕ Support link (Ko-fi)","https://ko-fi.com/shadowledger")
shop=st.sidebar.text_input("📄 Case File shop link (blank until open)","")
ep_num=st.sidebar.text_input("Episode #","001")
voice=st.sidebar.text_input("🎙️ Narrator voice ID","longanyang")
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
# CRITICAL FIX: REMOVED PILOT MODE CHECKBOX
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
    if st.button("1️⃣ Connect (YouTube + Vault)"): st.code(yt_auth_url(FULLSCOPE))
    if st.button("1️⃣ Connect (YouTube only)"): st.code(yt_auth_url(YT_ONLY))
    code=st.text_input("2️⃣ Paste the code")
    if code and st.button("🔗 Connect"):
        try:
            rt=yt_connect(code.strip()); st.success("Connected ✅")
            if rt: st.code(f'YT_REFRESH_TOKEN = "{rt}"')
        except Exception as e: st.error(str(e)[:120])
    if st.button("🔄 Recover / rebuild from YouTube"):
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
    if st.button("🆕 NEW PROJECT"):
        jsave(LINE_F,[]); vault_save([]); st.session_state.line=[]; st.success("✅ New project started.")
    if st.button("☁️ Backup line to Vault"):
        with st.spinner("☁️ Backing up…"): vault_save(load_line()); st.success("✅ Backed up.")
    if st.button("⬇️ Restore line from Vault"):
        with st.spinner("⬇️ Restoring…"):
            r=vault_load()
            if r: jsave(LINE_F,r); st.session_state.line=r; st.success(f"✅ Restored {len(r)} episode(s).")
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
jsave(SET_F,{"series":series,"pilot":False,"auto_mood":auto_mood,"mood":mood,"angle":angle,"voice":voice,"music":music_path,"support":support,"ep_day":ep_day,"ep_time":ep_time,"sh_day":sh_day,"sh_time":sh_time,"manual":manual,"interrupts":interrupts,"footage":FMAP[footage_sel],"voice_mode":("premium" if voice_mode.startswith("PREMIUM") else "free")})

# SINGLE TAB SET
tab1,tab2,tabS,tab3,tab4,tab5=st.tabs(["🥚 1·SCAN","🏭 2·PRODUCE","💼 SPONSOR","📦 3·PUBLISH","📈 STRATEGY","👹 AUTO MONSTER"])

# GOLDEN GOOSE SCANNER TAB
with tab1:
    st.markdown("## 🎯 STEP 1: FIND HIGH-RPM TOPICS")
    st.caption("Auto-finds trending finance topics with USA/UK audience focus")
    
    # INITIALIZE SCAN STATE
    if "scan_triggered" not in st.session_state:
        st.session_state.scan_triggered = False
    
    # SCAN BUTTON (UNIQUE KEY + STATE CONTROL)
    if st.button("🔍 SCAN YOUTUBE FOR HOT TOPICS", key="unique_scan_button"):
        st.session_state.scan_triggered = True
        st.session_state.bull = None  # Clear previous results
    
    # EXECUTE SCAN ONLY ONCE PER CLICK
    if st.session_state.scan_triggered and not st.session_state.get("bull"):
        with st.spinner("📡 Finding high-RPM finance topics..."):
            bull = refresh_bulletin(DEFAULT_SEEDS)
            st.session_state["bull"] = bull
            st.session_state.scan_triggered = False  # Reset trigger
            st.success(f"✅ Found {len(bull[:12])} hot topics")
    
    # SHOW TOPICS (ONLY IF SCANNED)
    bull_items = st.session_state.get("bull", [])
    if bull_items:
        st.markdown("### 🔥 TOP WINNERS (High RPM + Trending)")
        for i, item in enumerate(bull_items[:6]):  # Show top 6
            score_color = "green" if item["sc"] >= 80 else "orange" if item["sc"] >= 60 else "gray"
            st.markdown(f"**{item['t']}** · 🥚 `{item['sc']}/100` · `{item['src']}`")
            
            # ADD BUTTON FOR EACH TOPIC (UNIQUE KEY WITH TIMESTAMP)
            topic_key = f"add_{i}_{abs(hash(item['t'])) % 100000}"
            if st.button(f"➕ ADD '{item['t'][:30]}...'", key=topic_key):
                jsave(LINE_F, [])  # Clear old episodes
                queue_topic(item["t"], item["sc"], item["src"])
                st.session_state.line = load_line()
                st.success(f"✅ Added '{item['t']}' — go to 🏭 2·PRODUCE")
    
    st.markdown("## 🧹 CLEAN SLATE TOOLS")
    c1, c2 = st.columns(2)
    if c1.button("🆕 NEW PROJECT (CLEAR ALL)", key="new_project_clear_all"):
        jsave(LINE_F, [])
        jsave(BIBLE_F, [])
        jsave(MET_F, [])
        st.session_state.line = []
        st.success("✅ Production line cleared")
    
    if c2.button("🔄 REFRESH FROM YOUTUBE", key="refresh_youtube_channel"):
        with st.spinner("Scanning your channel..."):
            ups = yt_channel_uploads()
            newl = []
            for vid, title in ups:
                if "shorts" not in title.lower() and "#shorts" not in title:
                    newl.append({
                        "topic": title,
                        "status": "rendered",
                        "yt_id": vid
                    })
            jsave(LINE_F, newl)
            st.session_state.line = newl
        st.success(f"✅ Restored {len(newl)} full episodes")
    
    st.markdown("## 🧹 CLEAN SLATE TOOLS")
    c1, c2 = st.columns(2)
    if c1.button("🆕 NEW PROJECT (CLEAR ALL)", key="new_project_clear"):
        jsave(LINE_F, [])
        jsave(BIBLE_F, [])
        jsave(MET_F, [])
        st.session_state.line = []
        st.success("✅ Production line cleared")
    
    if c2.button("🔄 REFRESH FROM YOUTUBE", key="refresh_youtube_data"):
        with st.spinner("Scanning your channel..."):
            ups = yt_channel_uploads()
            newl = []
            for vid, title in ups:
                if "shorts" not in title.lower() and "#shorts" not in title:
                    newl.append({
                        "topic": title,
                        "status": "rendered",
                        "yt_id": vid
                    })
            jsave(LINE_F, newl)
            st.session_state.line = newl
        st.success(f"✅ Restored {len(newl)} full episodes")
    
    if c2.button("🔄 REFRESH FROM YOUTUBE", key="refresh_yt"):
        with st.spinner("Scanning your channel..."):
            ups = yt_channel_uploads()
            newl = []
            for vid, title in ups:
                if "shorts" not in title.lower() and "#shorts" not in title:
                    newl.append({
                        "topic": title,
                        "status": "rendered",
                        "yt_id": vid
                    })
            jsave(LINE_F, newl)
            st.session_state.line = newl
        st.success(f"✅ Restored {len(newl)} full episodes")
    
    # GOLDEN GOOSE BUTTON
    if st.button("🔍 SCAN YOUTUBE FOR HOT TOPICS"):
        with st.spinner("📡 Finding high-RPM finance topics..."):
            bull = refresh_bulletin(DEFAULT_SEEDS)
            st.session_state["bull"] = bull
            st.success(f"✅ Found {len(bull[:12])} hot topics")
    
    # SHOW TOPICS (ONLY IF SCANNED)
    bull_items = st.session_state.get("bull", [])
    if bull_items:
        st.markdown("### 🔥 TOP WINNERS (High RPM + Trending)")
        for i, item in enumerate(bull_items[:6]):  # Show top 6
            score_color = "green" if item["sc"] >= 80 else "orange" if item["sc"] >= 60 else "gray"
            st.markdown(f"**{item['t']}** · 🥚 `{item['sc']}/100` · `{item['src']}`")
            
            # ADD BUTTON FOR EACH TOPIC
            if st.button(f"➕ ADD '{item['t'][:30]}...'", key=f"add_{i}"):
                jsave(LINE_F, [])  # Clear old episodes
                queue_topic(item["t"], item["sc"], item["src"])
                st.session_state.line = load_line()
                st.success(f"✅ Added '{item['t']}' — go to 🏭 2·PRODUCE")
    
    st.markdown("## 🧹 CLEAN SLATE TOOLS")
    c1, c2 = st.columns(2)
    if c1.button("🆕 NEW PROJECT (CLEAR ALL)"):
        jsave(LINE_F, [])
        jsave(BIBLE_F, [])
        jsave(MET_F, [])
        st.session_state.line = []
        st.success("✅ Production line cleared")
    
    if c2.button("🔄 REFRESH FROM YOUTUBE"):
        with st.spinner("Scanning your channel..."):
            ups = yt_channel_uploads()
            newl = []
            for vid, title in ups:
                if "shorts" not in title.lower() and "#shorts" not in title:
                    newl.append({
                        "topic": title,
                        "status": "rendered",
                        "yt_id": vid
                    })
            jsave(LINE_F, newl)
            st.session_state.line = newl
        st.success(f"✅ Restored {len(newl)} full episodes")
    
    # GOLDEN GOOSE BUTTON
    if st.button("🔍 SCAN YOUTUBE FOR HOT TOPICS"):
        with st.spinner("📡 Finding high-RPM finance topics..."):
            bull = refresh_bulletin(DEFAULT_SEEDS)
            st.session_state["bull"] = bull
            st.success(f"✅ Found {len(bull[:12])} hot topics")
    
    # SHOW TOPICS (ONLY IF SCANNED)
   
