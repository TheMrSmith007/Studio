import warnings
warnings.filterwarnings("ignore")
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

# ---------------- CONFIG + FILE STATE ----------------
DASH, YT, PEX = st.secrets["DASHSCOPE_API_KEY"], st.secrets["YOUTUBE_API_KEY"], st.secrets["PEXELS_API_KEY"]
YTC_ID, YTC_SEC = st.secrets.get("YOUTUBE_CLIENT_ID",""), st.secrets.get("YOUTUBE_CLIENT_SECRET","")
YT_RT = st.secrets.get("YT_REFRESH_TOKEN","")
BASE = "https://dashscope-intl.aliyuncs.com/api/v1"
CHAT_MODELS = ["qwen3.7-plus", "qwen-plus"]
VIDEO_MODELS = ["wan2.7-t2v", "wan2.1-t2v-turbo"]
IMAGE_MODELS = ["qwen-image-3.0", "wanx2.1-t2i-turbo"]
GOLD, BLACK = (212,175,55), (5,6,8)
TMP = "/tmp"
LINE_F = f"{TMP}/shadow_line.json"
SUP_F = f"{TMP}/supporters.json"
SPO_F = f"{TMP}/sponsor.json"
SET_F = f"{TMP}/settings.json"
JOB_F = f"{TMP}/job.json"
DEC_F = f"{TMP}/decisions.json"
BIBLE_F = f"{TMP}/bible.json"
MET_F = f"{TMP}/metrics.json"
COST_F = f"{TMP}/costs.json"
REV_F = f"{TMP}/revenue.json"
HOF_F = f"{TMP}/hall_of_fame.json"
PREF_F = f"{TMP}/prefs.json"
SEEDS_F = f"{TMP}/seeds.json"
BULL_F = f"{TMP}/bulletin.json"
CRED_F = f"{TMP}/credits.json"
YT_TOK_F = f"{TMP}/yt_token.json"
FONT = next((p for p in ["assets/Cinzel-Bold.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"] if os.path.exists(p)), None)
def F(sz): return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default(sz)
def slug(t): return re.sub(r'[^a-z0-9]+','_', t.lower()).strip('_')[:40]
def jload(p, d):
    try:
        if os.path.exists(p): return json.load(open(p))
    except Exception: pass
    return d
def jsave(p, d):
    try: json.dump(d, open(p,"w"))
    except Exception: pass
ENGINE = {"v":""}
def decide(m):
    d = jload(DEC_F, []); d.append(m); jsave(DEC_F, d)
def job_load(): return jload(JOB_F, {"running":False,"current":"","log":[]})
def job_save(j): jsave(JOB_F, j)
def prefs_txt():
    p = jload(PREF_F, [])
    return " · ".join(p[-5:]) if p else "No CEO preferences stored yet."
DEFAULT_SEEDS = "BlackRock buying housing\nTicketmaster Live Nation monopoly\nThe janitor who left $6 million to his hospital\nHow Norway became the world's landlord\nThe teacher who out-traded Wall Street\nBoeing whistleblowers"
def load_seeds():
    s = jload(SEEDS_F, None)
    return "\n".join(s) if s else DEFAULT_SEEDS
def save_seeds(text):
    jsave(SEEDS_F, [x for x in text.splitlines() if x.strip()])
def cred_load(): return jload(CRED_F, {"loaded_zar":0})
def cred_save(d): jsave(CRED_F, d)
def ramp_advisor():
    line = load_line()
    n = len([i for i in line if i["status"]=="rendered"])
    met = jload(MET_F, {})
    ctrs = [float(m.get("ctr") or 0) for m in met.values() if m.get("ctr")]
    avg_ctr = sum(ctrs)/len(ctrs) if ctrs else 0
    if n < 2: phase, rec, go = "WARM-UP (wk 1-2)", "2 episodes this week", False
    elif n < 4: phase, rec, go = "BUILD (wk 3-4)", "4 episodes this week", False
    elif n < 8: phase, rec, go = "SCALE (wk 5-8)", "8 episodes this week", avg_ctr >= 3.5
    else: phase, rec, go = "AGGRESSIVE", "12-30 episodes this week", avg_ctr >= 3.0
    if go: rec += " — 🚀 signs are GOOD, go aggressive"
    return {"phase":phase,"rec":rec,"go":go,"n":n,"ctr":avg_ctr}

# ---------------- MODEL DISCOVERY ----------------
_MC = {"t":0.0,"ids":[]}
def list_models():
    if time.time() - _MC["t"] > 21600:
        try:
            r = requests.get("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
                             headers={"Authorization": f"Bearer {DASH}"}, timeout=30).json()
            _MC["ids"] = [m.get("id","") for m in r.get("data",[])]
        except Exception:
            pass
        _MC["t"] = time.time()
    return _MC["ids"]
def disc(pat, n=3):
    cands = [i for i in list_models() if re.search(pat, i, re.I)]
    def ver(i):
        m = re.findall(r"\d+(?:\.\d+)+", i) or re.findall(r"\d+", i)
        try: return [int(x) for x in m[0].split(".")]
        except Exception: return [0]
    cands.sort(key=ver, reverse=True)
    return cands[:n]
def chain(pat, fallbacks):
    out = disc(pat)
    for f in fallbacks:
        if f not in out: out.append(f)
    return out

MOODS = {
 "Calm investigator (default)": "low, calm, intimate documentary voice, slow deliberate pace, slightly breathy, grave tension, long pause before every reveal",
 "Concerned witness": "worried, urgent, leaning in, slightly trembling with concern, as if warning a friend",
 "Grave elegy": "mournful, heavy, slow, deep pauses, the voice of a eulogy for something that should never have happened",
 "Cold expose": "clinical, sharp, controlled anger, precise diction, ice-cold delivery",
 "Hushed suspense": "near-whisper, tense, every word a secret, long silences",
 "Hopeful storyteller": "warm, admiring, quietly triumphant, a smile in the voice, still slow and cinematic",
}
EDGE_VOICES = {
 "Calm investigator (default)": ("en-US-GuyNeural", "-10%"),
 "Concerned witness": ("en-US-AriaNeural", "-5%"),
 "Grave elegy": ("en-GB-RyanNeural", "-15%"),
 "Cold expose": ("en-US-ChristopherNeural", "-8%"),
 "Hushed suspense": ("en-GB-SoniaNeural", "-12%"),
 "Hopeful storyteller": ("en-US-JennyNeural", "-5%"),
}
QWEN_TTS_VOICES = ["Cherry","Serena","Ethan","Chelsie"]
MOOD_ROT = list(MOODS.keys())
ANGLES = {
 "Dark expose (default)": "Tone: dark investigative expose. Dopamine via outrage, justice, revelation.",
 "Mystery / curiosity": "Tone: puzzle-box mystery. Dopamine via curiosity loops and the final click of understanding.",
 "David vs Goliath": "Tone: underdog versus a financial giant. Dopamine via fairness and clever resistance.",
 "Comeback / positive": "Tone: triumphant human comeback inside finance. NOT a forced happy ending — earned, bittersweet, still leaves an open question.",
}
TONE_LABEL = {"Dark expose (default)":"A DARK EXPOSE","Mystery / curiosity":"A MYSTERY","David vs Goliath":"AN UNDERDOG STORY","Comeback / positive":"A COMEBACK"}

# ---------------- OAUTH + YOUTUBE + DRIVE VAULT ----------------
YT_SCOPES = ("https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube "
             "https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/drive.file")
def yt_auth_url():
    return (f"https://accounts.google.com/o/oauth2/v2/auth?client_id={YTC_ID}&redirect_uri=http://localhost"
            f"&response_type=code&scope={requests.utils.quote(YT_SCOPES)}&access_type=offline&prompt=consent")
def yt_connect(code):
    r = requests.post("https://oauth2.googleapis.com/token", data={"code":code,"client_id":YTC_ID,
        "client_secret":YTC_SEC,"redirect_uri":"http://localhost","grant_type":"authorization_code"}).json()
    if "access_token" not in r: raise RuntimeError(r.get("error_description","oauth failed"))
    jsave(YT_TOK_F, {"token":r["access_token"],"refresh":r.get("refresh_token"),"cid":YTC_ID,"csec":YTC_SEC})
    return r.get("refresh_token","")
def _creds():
    from google.oauth2.credentials import Credentials
    tok = jload(YT_TOK_F, None)
    if tok:
        c = Credentials(token=tok.get("token"), refresh_token=tok.get("refresh"), client_id=tok.get("cid"),
                        client_secret=tok.get("csec"), token_uri="https://oauth2.googleapis.com/token")
    elif YT_RT and YTC_ID and YTC_SEC:
        c = Credentials(token=None, refresh_token=YT_RT, client_id=YTC_ID, client_secret=YTC_SEC,
                        token_uri="https://oauth2.googleapis.com/token")
    else:
        return None
    if not c.valid and c.refresh_token:
        from google.auth.transport.requests import Request
        c.refresh(Request())
        jsave(YT_TOK_F, {"token":c.token,"refresh":c.refresh_token,"cid":YTC_ID,"csec":YTC_SEC})
    return c
def yt_service(kind="youtube"):
    from googleapiclient.discovery import build
    c = _creds()
    if not c: return None
    return build(kind, "v3" if kind=="youtube" else "v2", credentials=c)
def drive_service():
    from googleapiclient.discovery import build
    c = _creds()
    if not c: return None
    try: return build("drive","v3",credentials=c)
    except Exception: return None
VAULT = "Shadow Ledger Vault"
def _vault_fid():
    d = drive_service()
    if not d: return None
    try:
        q = d.files().list(q=f"name='{VAULT}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                           spaces="drive", fields="files(id)").execute()
        if q["files"]: return q["files"][0]["id"]
        return d.files().create(body={"name":VAULT,"mimeType":"application/vnd.google-apps.folder"}).execute()["id"]
    except Exception: return None
def drive_upsert(name, text, fid):
    from googleapiclient.http import MediaIoBaseUpload
    d = drive_service()
    if not d or not fid: return
    try:
        q = d.files().list(q=f"name='{name}' and '{fid}' in parents and trashed=false", fields="files(id)").execute()
        media = MediaIoBaseUpload(io.BytesIO(text.encode()), mimetype="application/json", resumable=False)
        if q["files"]: d.files().update(fileId=q["files"][0]["id"], media_body=media).execute()
        else: d.files().create(body={"name":name,"parents":[fid]}, media_body=media).execute()
    except Exception: pass
def drive_read(name, fid):
    from googleapiclient.http import MediaIoBaseDownload
    d = drive_service()
    if not d or not fid: return None
    try:
        q = d.files().list(q=f"name='{name}' and '{fid}' in parents and trashed=false", fields="files(id)").execute()
        if not q["files"]: return None
        fh = io.BytesIO(); req = d.files().get_media(fileId=q["files"][0]["id"])
        down = MediaIoBaseDownload(fh, req)
        done = False
        while not done: _, done = down.next_chunk()
        return json.loads(fh.getvalue().decode())
    except Exception: return None
def vault_save(line):
    try: drive_upsert("state.json", json.dumps(line), _vault_fid())
    except Exception: pass
def vault_load():
    try: return drive_read("state.json", _vault_fid())
    except Exception: return None
def yt_channel_uploads():
    svc = yt_service()
    if not svc: return []
    try:
        ch = svc.channels().list(part="contentDetails", mine=True).execute()
        up = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        vids = []
        nxt = None
        for _ in range(3):
            r = svc.playlistItems().list(part="snippet", playlistId=up, maxResults=50, pageToken=nxt or "").execute()
            for it in r.get("items",[]): vids.append((it["snippet"]["resourceId"]["videoId"], it["snippet"]["title"]))
            nxt = r.get("nextPageToken")
            if not nxt: break
        return vids
    except Exception: return []

def load_line(): return jload(LINE_F, [])
def save_line(l):
    jsave(LINE_F, l)
    vault_save(l)
if "line" not in st.session_state:
    _l = load_line()
    if not _l:
        _l = vault_load() or []
        if _l: jsave(LINE_F, _l)
    st.session_state.line = _l
if "edits" not in st.session_state: st.session_state.edits = {}
for _it in st.session_state.line:
    if _it["status"]=="rendered" and not os.path.exists(_it.get("out") or ""):
        _it["status"]="approved"; _it["err"]="media cache cleared — script kept, press render to redo"
save_line(st.session_state.line)
def queue_topic(t, sc, tag):
    line = load_line()
    if t and not any(i["topic"]==t for i in line):
        line.append({"topic":t,"score":sc,"tag":tag,"status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":""})
        save_line(line); decide(f"Queued '{t[:40]}' ({tag}, 🥚 {sc}).")
        return True
    return False
def mood_for(idx): return MOOD_ROT[idx % len(MOOD_ROT)]
def friday_for(i):
    d = date.today(); days_ahead = (4 - d.weekday()) % 7 or 7
    return (d + timedelta(days=days_ahead + 7*i)).isoformat() + "T21:00:00Z"
def monday_for(i):
    d = date.today(); days_ahead = (0 - d.weekday()) % 7 or 7
    return (d + timedelta(days=days_ahead + 7*i)).isoformat() + "T17:00:00Z"

# ---------------- BIBLE + HOF ----------------
def bible_txt():
    b = jload(BIBLE_F, [])
    if not b: return "No previous episodes yet."
    return " · ".join(f"EP{e['ep']} {e['topic']}: {e.get('callback','')}" for e in b[-4:])
def bible_append(ep, topic, sc):
    try:
        g = qwen(f"Episode topic: {topic}. Script JSON: {json.dumps(sc)[:2500]}. "
                 f"Return JSON {{'facts':[3 short concrete facts established], 'callback':'one sentence future episodes can reference this by', 'sequel_seed':'one line: what follow-up investigation this episode naturally leads to'}}")
        b = jload(BIBLE_F, []); b.append({"ep":ep,"topic":topic,"facts":g.get("facts",[]),"callback":g.get("callback",""),"sequel":g.get("sequel_seed","")})
        jsave(BIBLE_F, b)
    except Exception: pass
def hof_update(vid, score):
    h = jload(HOF_F, []); h.append({"vid":vid,"score":score,"ts":datetime.now().isoformat()})
    jsave(HOF_F, h)
def hof_best():
    h = jload(HOF_F, [])
    if not h: return None
    return max(h, key=lambda x: x.get("score",0))

# ---------------- DNA + GATE ----------------
DNA = """You are showrunner of SHADOW LEDGER, a prestige financial documentary series.
Topic: {topic}. Series: {series}. ANGLE: {angle}
SERIES MEMORY: {bible}
CEO PREFERENCES (obey these): {prefs}
(If memory exists, weave ONE natural callback to an earlier episode for binge continuity.)
STRUCTURE:
1. COLD OPEN + VIEWER STAKES: One human moment. MUST state how this affects the viewer's daily life, wallet or future in the first 15 seconds.
2. ACT I THE SUSPECT/PROTAGONIST: face, quote, defining moment.
3. ACT II THE MACHINE: stakes escalate; NEW open loop every 90s.
4. ACT III THE REVEAL: twist; numbers translated to human scale.
5. THE OPEN QUESTION: no neat bow, no preaching. Present facts, step back, ask a haunting question for the audience to decide in the comments. Then ONE in-brand CTA + a BINGE-PITCH teasing the next investigation.
RULES: present tense, short cinematic sentences. NO ACCUSATIONS; use 'alleged', 'according to documents', 'regulators claim'; frame controversy as questions; let the audience be the jury. Retention DNA in EVERY angle: open loops, pattern interrupts, concrete specifics.
ANTI-SLOP: BANNED: delve, tapestry, landscape, game-changer, uncover the truth. EVERY scene needs a concrete detail (number, date, place). Max 3 sentences per scene.
OUTPUT JSON: {{"title_options":[3], "hook_words":"MAX 4 WORDS", "share_line":"max 10 words, quotable, makes a viewer send this video to a friend", "scenes":[{{"narration":"", "visual":"", "ost":""}}], "pinned_question":"", "binge_pitch":"", "community_poll":{{"q":"","a":["",""]}}, "cold_open_A":"max 20 words, first hook version", "cold_open_B":"max 20 words, second hook version"}}"""

GATE = """You are SHADOW LEDGER's ruthless executive editor, media-legal reviewer AND YouTube policy compliance officer.
Topic: {topic}. Review this script JSON: {script}
FIX: (1) AI-slop -> concrete specifics; (2) legal/bias -> remove accusations, frame as questions, 'alleged/documents show';
(3) viewer stakes -> cold open must connect to the viewer's life; (4) dragging -> max 3 sentences; (5) clickbait -> title promise delivered;
(6) shareability -> share_line quotable and human;
(7) YOUTUBE ADVERTISER-FRIENDLY POLICY: no profanity, no graphic descriptions, sensitive events framed factually; rewrite any narration/ost words that trigger limited ads;
(8) advisory: if themes warrant, ONE professional viewer advisory (max 14 words, Netflix-style), else "".
Return JSON {{"slop_clean":0-100,"emotion":0-100,"viewer_stakes":"clear|added","legal_flags_fixed":N,"yt_policy":"clean|fixed",
"clickbait":"clear|fixed","advisory":"","pacing":"one line note","scenes":[polished scenes same schema],
"title_options":[polished, <60 chars],"share_line":"polished max 10 words","cold_open_A":"polished max 20 words","cold_open_B":"polished max 20 words"}}"""

def qwen(prompt, sys=None):
    m = ([{"role":"system","content":sys}] if sys else []) + [{"role":"user","content":prompt}]
    last = None
    for model in chain(r"plus", CHAT_MODELS):
        try:
            r = requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={"Authorization": f"Bearer {DASH}"},
                json={"model":model,"messages":m,"response_format":{"type":"json_object"}}, timeout=120).json()
            return json.loads(r["choices"][0]["message"]["content"])
        except Exception as e:
            last = e
    raise RuntimeError(f"chat models failed: {last}")

def wan_video_prompt(v): return (f"{v}. cinematic documentary film still, anamorphic 2.39:1, "
    "35mm grain, low-key chiaroscuro, crushed blacks, gold practicals, teal shadows, slow dolly, no text, no watermark")

# ---------------- VOICE CHAIN ----------------
def speak(text, voice, mood):
    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
        dashscope.base_websocket_api_url = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"
        for model in chain(r"cosyvoice", ["cosyvoice-v3-flash","cosyvoice-v3-plus","cosyvoice-v2","cosyvoice-v1"]):
            for instr in (MOODS[mood], None):
                try:
                    kw = {"model": model, "voice": voice or "longanyang"}
                    if instr: kw["instruction"] = instr
                    b = SpeechSynthesizer(**kw).call(text)
                    if b:
                        ENGINE["v"] = f"CosyVoice ({model}) — premium"; return b
                except Exception:
                    continue
    except Exception:
        pass
    for model in chain(r"tts", ["qwen-audio-3.0-tts-flash"]):
        for vq in QWEN_TTS_VOICES:
            try:
                r = requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
                    headers={"Authorization": f"Bearer {DASH}"},
                    json={"model":model,
                          "messages":[{"role":"user","content":text}],
                          "modalities":["audio"],
                          "audio":{"voice":vq,"format":"mp3"}}, timeout=90).json()
                b = base64.b64decode(r["choices"][0]["message"]["audio"]["data"])
                if b:
                    ENGINE["v"] = f"Qwen-TTS ({model}/{vq}) — premium"; return b
            except Exception:
                continue
    try:
        import edge_tts, asyncio
        v, rr = EDGE_VOICES.get(mood, ("en-US-GuyNeural", "-10%"))
        p = f"{TMP}/edge_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
        asyncio.run(edge_tts.Communicate(text, v, rate=rr).save(p))
        ENGINE["v"] = "Edge Neural (free, studio-grade)"
        return open(p, "rb").read()
    except Exception:
        pass
    from gtts import gTTS
    p = f"{TMP}/gtts_{hashlib.md5((text+mood).encode()).hexdigest()}.mp3"
    gTTS(text=text, lang="en").save(p)
    ENGINE["v"] = "Google gTTS (free)"
    return open(p, "rb").read()

# ---------------- VIDEO / IMAGE ----------------
def _task(tid):
    return requests.get(f"{BASE}/tasks/{tid}", headers={"Authorization": f"Bearer {DASH}"}).json()
def wan_video(prompt):
    for model in chain(r"wan.*t2v", VIDEO_MODELS):
        try:
            r = requests.post(f"{BASE}/services/aigc/video-generation/video-synthesis",
                headers={"Authorization": f"Bearer {DASH}", "Content-Type": "application/json", "X-DashScope-Async": "enable"},
                json={"model":model,"input":{"prompt":prompt},"parameters":{"size":"1280*720"}}).json()
            tid = r["output"]["task_id"]
            for _ in range(150):
                time.sleep(4)
                q = _task(tid); stt = q["output"]["task_status"]
                if stt == "SUCCEEDED": return q["output"]["video_url"]
                if stt in ("FAILED","CANCELED"): break
        except Exception:
            continue
    raise RuntimeError("video models failed")
def wan_images(prompt, n=2):
    for model in chain(r"qwen-image|wanx", IMAGE_MODELS):
        try:
            r = requests.post(f"{BASE}/services/aigc/text2image/image-synthesis",
                headers={"Authorization": f"Bearer {DASH}", "Content-Type": "application/json", "X-DashScope-Async": "enable"},
                json={"model":model,"input":{"prompt":prompt},"parameters":{"size":"1280*720","n":n}}).json()
            tid = r["output"]["task_id"]
            for _ in range(60):
                time.sleep(3)
                q = _task(tid); stt = q["output"]["task_status"]
                if stt in ("FAILED","CANCELED"): break
                if stt == "SUCCEEDED":
                    out = q["output"]
                    if "results" in out: return [x["url"] for x in out["results"]]
                    if "choices" in out:
                        urls = []
                        for ch in out["choices"]:
                            c = ch.get("message",{}).get("content")
                            if isinstance(c, list): urls += [i["image"] for i in c if isinstance(i,dict) and "image" in i]
                        if urls: return urls
        except Exception:
            continue
    raise RuntimeError("image models failed")
def pexels_clip(q):
    v = requests.get("https://api.pexels.com/videos/search", headers={"Authorization":PEX}, params={"query":q,"per_page":5}).json()["videos"]
    return v[0]["video_files"][0]["link"]
def fetch(url, name):
    p = f"{TMP}/{name}"; open(p,"wb").write(requests.get(url).content); return p
def estimate(sc, pilot):
    scenes = sc["scenes"][:4] if pilot else sc["scenes"]
    chars = sum(len(s["narration"]) for s in scenes)
    secs = int(chars/14) + 8 + len(scenes)
    cost = len(scenes)*0.06 + chars*0.00003
    return secs, cost
def balance_advice(line):
    met = jload(MET_F, {})
    ctrs = {}
    for vid, m in met.items():
        a = m.get("angle"); c = m.get("ctr")
        if a and c is not None: ctrs.setdefault(a, []).append(c)
    best = max(ctrs, key=lambda k: sum(ctrs[k])/len(ctrs[k])) if ctrs else None
    recent = [i.get("angle") or "Dark expose (default)" for i in line if i["status"] in ("rendered","approved","scripted","queued")][-3:]
    if best and best not in recent: return best
    if len(recent) < 2: return None
    dark = sum(1 for a in recent if a=="Dark expose (default)")
    if dark >= 2: return "Mystery / curiosity"
    if len(recent) >= 3 and not any(a=="Comeback / positive" for a in recent): return "Comeback / positive"
    if dark == 0: return "Dark expose (default)"
    return None

# ---------------- GOLDEN EGG + HUNT + RADAR + ANTICIPATION + BULLETIN ----------------
def yt(path, **kw): return requests.get(f"https://www.googleapis.com/youtube/v3/{path}", params={"key":YT, **kw}).json()
def golden_egg(topic):
    s = yt("search", part="snippet", q=topic, type="video", maxResults=10, order="viewCount")
    ids = [i["id"]["videoId"] for i in s.get("items",[])]
    if not ids: return 50, "no data"
    vs = yt("videos", part="statistics,snippet", id=",".join(ids))["items"]
    views = [int(v["statistics"]["viewCount"]) for v in vs]
    demand = min(45, int(sum(views)/len(views)/1_000_000*9))
    fresh = min(20, int(sum(1 for v in vs if (datetime.now() - datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z",""))) < timedelta(days=730))*2.5))
    chans = {v["snippet"]["channelId"] for v in vs}
    comp = max(0, 20 - len(chans)*2)
    break_out = min(15, sum(1 for v in vs if int(v["statistics"]["viewCount"])>200_000)*5)
    return min(100, demand+fresh+comp+break_out), f"demand {demand}/45 · momentum {fresh}/20 · open field {comp}/20 · small-channel proof {break_out}/15"
def hunt(theme, min_score=80, n=5):
    c = qwen(f"Generate {n*3} distinct, specific prestige financial-documentary topic ideas about: {theme}. "
             f"Prefer concrete companies, events, countries, scandals, comebacks. Return JSON {{'topics':[...]}}")
    scored = []
    for t in c.get("topics", []):
        try:
            sc, why = golden_egg(t)
            if sc >= min_score: scored.append((t, sc, why))
        except Exception: pass
    scored.sort(key=lambda x: -x[1])
    return scored[:n]
def trend_radar(seed):
    sug = requests.get("https://suggestqueries.google.com/complete/search", params={"client":"youtube","q":seed}).json()[1]
    wk = yt("search", part="snippet", q=seed, type="video", order="viewCount", publishedAfter=(datetime.utcnow()-timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"), maxResults=5)
    vel = [f"{i['snippet']['title'][:40]}…" for i in wk.get("items",[])]
    return [s[0] if isinstance(s,list) else s for s in sug], vel
def predict_spikes(seed):
    sug, vel = trend_radar(seed)
    scored = []
    for s in sug[:8]:
        try:
            sc, why = golden_egg(s)
            scored.append((s, sc, why))
        except Exception: pass
    scored.sort(key=lambda x: -x[1])
    return scored
def refresh_bulletin(seed_text):
    themes = [x for x in seed_text.splitlines() if x.strip()][:2] or ["finance"]
    items = []
    for th in themes:
        sug, vel = trend_radar(th)
        for s in sug[:4]:
            try:
                sc, why = golden_egg(s)
                items.append({"t": s, "sc": sc, "src": "LIVE"})
            except Exception: pass
        for vtxt in vel[:2]:
            items.append({"t": vtxt.replace("…",""), "sc": 0, "src": "HOT-7D"})
    try:
        for s, sc, why in predict_spikes(themes[0])[:5]:
            items.append({"t": s, "sc": sc, "src": "FORECAST"})
    except Exception: pass
    seen = set(); out = []
    for i in items:
        k = i["t"].lower().strip()
        if k and k not in seen:
            seen.add(k); out.append(i)
    out.sort(key=lambda x: -x["sc"])
    jsave(BULL_F, {"ts": datetime.now().isoformat(), "items": out[:12]})
    return out[:12]
def series_plan(topic):
    return qwen(f"Prestige documentary topic: {topic}. Decide if it supports a 2-3 episode series WITHOUT dragging. Return JSON {{'series':true/false,'why':'one line','episodes':[2-3 distinct titles]}}")

TRIGGERS = {"scam":"alleged fraud","scammer":"alleged fraudster","kill":"fatality","murder":"fatality","suicide":"tragic death","terrorist":"extremist","cartel":"syndicate","rape":"assault","steal":"misappropriate"}
def adsense_scrub(text):
    for bad, good in TRIGGERS.items():
        text = re.sub(rf'\b{bad}\b', good, text, flags=re.IGNORECASE)
    return text

def yt_upload(path, title, desc, tags, when=None, thumb=None):
    from googleapiclient.http import MediaFileUpload
    svc = yt_service()
    if not svc: return None
    body = {"snippet":{"title":title,"description":desc,"tags":tags,"categoryId":"25"},
            "status":{"privacyStatus":"private","selfDeclaredMadeForKids":False}}
    if when: body["status"]["publishAt"] = when
    resp = svc.videos().insert(part="snippet,status", body=body,
             media_body=MediaFileUpload(path, mimetype="video/mp4", resumable=True)).execute()
    vid = resp["id"]
    if thumb:
        try: svc.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb, mimetype="image/png")).execute()
        except Exception: pass
    return vid
def yt_unpublish(vid):
    svc = yt_service()
    if not svc: return False
    svc.videos().update(part="status", body={"id":vid,"status":{"privacyStatus":"private"}}).execute()
    return True
def yt_metrics(vid):
    from datetime import date as _d
    svc = yt_service("youtubeAnalytics")
    if not svc: return None
    today = _d.today(); start = today - timedelta(days=2)
    r = svc.query().execute(ids="channel==MINE", startDate=start.isoformat(), endDate=today.isoformat(),
          metrics="views,impressionCtr,averageViewDuration", filters=f"video=={vid}")
    row = r.get("rows",[None])[0]
    return {"views":row[0] if row else 0,"ctr":row[1] if row else None,"avd":row[2] if row else 0}

# ---------------- CEO'S PILOT ----------------
def ceo_pilot(msg):
    line = load_line()
    state = {"production_line":[{"ep":i+1,"topic":x["topic"],"status":x["status"],"score":x.get("score"),"yt_id":x.get("yt_id")} for i,x in enumerate(line)],
             "preferences": jload(PREF_F, [])[-5:], "recent_decisions": jload(DEC_F, [])[-5:]}
    r = qwen(f"""You are the CEO's Pilot for SHADOW LEDGER, an automated documentary studio. Read the CEO's message and the studio state, then return JSON:
{{"actions":[...],"reply":"short, warm, human confirmation of what you did"}}
Allowed actions (use only these):
- {{"action":"hunt","theme":"...","min_score":80}} find new topics about theme at/above score and queue them
- {{"action":"queue","topic":"..."}} add one topic to the production line
- {{"action":"reject","ep":N,"reason":"..."}} mark episode N rejected, store reason as a permanent lesson
- {{"action":"cancel","ep":N,"reason":"..."}} unpublish episode N on YouTube (set private), mark rejected, store lesson
- {{"action":"prefer","note":"..."}} store a permanent CEO preference the writers must obey
- {{"action":"angle","value":"Dark expose (default)|Mystery / curiosity|David vs Goliath|Comeback / positive"}} set default angle
State: {json.dumps(state)}
CEO message: {msg}""")
    outs = []
    for a in r.get("actions", []):
        act = a.get("action")
        line = load_line()
        if act == "hunt":
            res = hunt(a.get("theme","financial scandals"), int(a.get("min_score",80)))
            qd = sum(1 for t, sc, why in res if queue_topic(t, sc, "HUNTED"))
            outs.append(f"🎯 Hunted '{a.get('theme')}' → queued {qd} topics ≥{a.get('min_score',80)}.")
        elif act == "queue":
            t = a.get("topic","")
            if queue_topic(t, 0, "CEO"): outs.append(f"➕ Queued: {t}")
        elif act in ("reject","cancel"):
            idx = int(a.get("ep",1))-1
            if 0 <= idx < len(line):
                it = line[idx]
                if act=="cancel" and it.get("yt_id"):
                    yt_unpublish(it["yt_id"]); outs.append(f"🚫 EP{idx+1} unpublished on YouTube.")
                it["status"] = "rejected"; save_line(line)
                lesson = f"CEO rejected EP{idx+1} ({it['topic'][:30]}): {a.get('reason','')}"
                p = jload(PREF_F, []); p.append(lesson); jsave(PREF_F, p)
                decide(lesson); outs.append(f"🚫 EP{idx+1} rejected — lesson stored.")
        elif act == "prefer":
            p = jload(PREF_F, []); p.append(a.get("note","")); jsave(PREF_F, p)
            decide(f"CEO preference stored: {a.get('note','')}"); outs.append(f"🧠 Preference stored: {a.get('note','')[:60]}")
        elif act == "angle":
            S = jload(SET_F, {}); S["angle"] = a.get("value"); jsave(SET_F, S)
            outs.append(f"🎨 Default angle set: {a.get('value')}")
    return r.get("reply","Done, CEO."), outs

# ---------------- PIL CARDS ----------------
def card_img(title, sub="", w=1280, h=720, transparent=False):
    img = Image.new("RGBA" if transparent else "RGB", (w,h), (0,0,0,0) if transparent else BLACK)
    d = ImageDraw.Draw(img)
    if not transparent: d.rectangle([0,h//2-90,w,h//2+90], fill=(8,9,12))
    d.text((w//2, h//2-30), title, font=F(64), fill=GOLD, anchor="mm")
    if sub: d.text((w//2, h//2+50), sub, font=F(30), fill=(220,220,220), anchor="mm")
    d.rectangle([w//2-260, h//2+95, w//2+260, h//2+98], fill=GOLD)
    return np.array(img)
def credits_img(names):
    img = Image.new("RGB",(1280,720),BLACK); d = ImageDraw.Draw(img)
    d.rectangle([40,40,1240,680], outline=GOLD, width=2)
    d.text((640,140), "SUPPORTERS OF THE LEDGER", font=F(56), fill=GOLD, anchor="mm")
    lines = textwrap.wrap(" · ".join(names), 58)[:4]
    for k,ln in enumerate(lines):
        d.text((640,300+k*72), ln, font=F(34), fill=(230,230,230), anchor="mm")
    d.text((640,630), "thank you for funding independent investigations", font=F(26), fill=(160,160,160), anchor="mm")
    return np.array(img)
def ost_img(text):
    img = Image.new("RGBA",(1280,160),(0,0,0,0)); d = ImageDraw.Draw(img)
    d.text((640,80), text.upper(), font=F(72), fill=GOLD, anchor="mm", stroke_width=5, stroke_fill=(0,0,0))
    return np.array(img)
def pattern_interrupt(dur=0.8):
    img = Image.new("RGBA",(1280,720),(0,0,0,0)); d = ImageDraw.Draw(img)
    d.rectangle([0,0,1280,720], fill=(0,0,0,180))
    d.text((640,360), "FOLLOW THE MONEY", font=F(110), fill=GOLD, anchor="mm")
    return ImageClip(np.array(img)).with_duration(dur)
def tiktok_intro(hook):
    img = Image.new("RGB",(1080,1920),BLACK); d = ImageDraw.Draw(img)
    d.text((540,800), "WHAT YOU'RE ABOUT", font=F(80), fill=GOLD, anchor="mm")
    d.text((540,900), "TO SEE", font=F(80), fill=GOLD, anchor="mm")
    for k,ln in enumerate(textwrap.wrap(hook.upper(), 20)[:4]):
        d.text((540,1100+k*80), ln, font=F(48), fill=(230,230,230), anchor="mm")
    return ImageClip(np.array(img)).with_duration(2.5)
def case_file_pdf(topic, series, dos, support, path, ep="001"):
    W,H = 1240,1754
    pages=[]
    def blank():
        img = Image.new("RGB",(W,H),BLACK); d = ImageDraw.Draw(img)
        d.rectangle([50,50,W-50,H-50], outline=GOLD, width=2)
        d.text((W//2,110), "SHADOW LEDGER · CASE FILE", font=F(30), fill=GOLD, anchor="mm")
        return img,d
    cover,d0 = blank()
    d0.text((W//2,660), "SHADOW LEDGER", font=F(90), fill=GOLD, anchor="mm")
    d0.text((W//2,780), series.upper(), font=F(40), fill=(230,230,230), anchor="mm")
    d0.text((W//2,860), f"EPISODE #{ep}", font=F(36), fill=GOLD, anchor="mm")
    for k,ln in enumerate(textwrap.wrap(topic, 30)):
        d0.text((W//2,990+k*70), ln, font=F(54), fill=(240,240,240), anchor="mm")
    d0.text((W//2,1560), "TIMELINE · PLAYERS · MONEY · GLOSSARY · DISCUSSION", font=F(28), fill=GOLD, anchor="mm")
    pages.append(cover)
    def section(title, items):
        img,d = blank(); d.text((W//2,210), title, font=F(52), fill=(240,240,240), anchor="mm"); y=330
        for it in items:
            for k,ln in enumerate(textwrap.wrap(str(it), 74)):
                d.text((90,y), ("• " if k==0 else "   ")+ln, font=F(30), fill=(220,220,220)); y+=46
                if y>H-160: pages.append(img); img,d = blank(); y=310
        pages.append(img)
    section("TIMELINE", dos.get("timeline",[]))
    section("KEY_PLAYERS", dos.get("key_players",[]))
    section("FOLLOW THE MONEY", dos.get("follow_the_money",[]))
    section("GLOSSARY", dos.get("glossary",[]))
    section("DISCUSSION QUESTIONS", dos.get("discussion",[]))
    img,d = blank()
    d.text((W//2,700), "STAND WITH THE LEDGER", font=F(60), fill=GOLD, anchor="mm")
    d.text((W//2,830), "This dossier exists because supporters fund independent investigations.", font=F(30), fill=(220,220,220), anchor="mm")
    d.text((W//2,900), f"Tips, memberships & Case Files: {support}", font=F(30), fill=GOLD, anchor="mm")
    d.text((W//2,1010), "Editorial commentary based on public sources. Not financial advice.", font=F(24), fill=(150,150,150), anchor="mm")
    pages.append(img)
    pages[0].save(path, save_all=True, append_images=pages[1:])
    return path
def image_ad_clip(img_path, name):
    im = Image.open(img_path).convert("RGB")
    w, h = im.size; tw, th = w/h, 16/9
    if tw > th:
        nw = int(h*th); im = im.crop(((w-nw)//2, 0, (w+nw)//2, h))
    else:
        nh = int(w/th); im = im.crop((0, (h-nh)//2, w, (h+nh)//2))
    im = im.resize((1280,720), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle([0,640,1280,720], fill=(5,6,8))
    d.text((40,680), f"SPONSOR · {name.upper()}", font=F(34), fill=GOLD, anchor="lm")
    return ImageClip(np.array(im))
def make_bug():
    if os.path.exists("assets/sl_logo.png") and not os.path.exists(f"{TMP}/bug.png"):
        a = np.array(Image.open("assets/sl_logo.png").convert("RGBA"))
        m = a[...,:3].sum(axis=2) < 135; a[m,3]=0; a[~m,3]=150
        img = Image.fromarray(a); w,h = img.size
        img.resize((int(w*160/h),160), Image.LANCZOS).save(f"{TMP}/bug.png")
make_bug()
def silence(d): return AudioClip(lambda t: [0,0], d, fps=44100)

# ---------------- SOUND ----------------
SR = 22050
def sound_bed(dur, markers, hopeful=False):
    n = int(dur*SR); t = np.arange(n)/SR
    f1, f2 = (66.0, 82.5) if hopeful else (52.0, 78.0)
    bed = 0.10*np.sin(2*np.pi*f1*t)*(0.6+0.4*np.sin(2*np.pi*0.11*t)) + 0.05*np.sin(2*np.pi*f2*t+1.3)
    rng = np.random.default_rng(7)
    noise = np.convolve(rng.standard_normal(n), np.ones(40)/40, mode="same")
    for m in markers:
        s, e = max(0,int((m-3)*SR)), int(m*SR)
        if e > s:
            seg = np.arange(e-s)/(e-s); bed[s:e] += noise[s:e]*0.12*seg**2
        s, e = int(m*SR), min(n, int((m+1.6)*SR)); tt = np.arange(e-s)/SR
        bed[s:e] += 0.35*np.sin(2*np.pi*45*tt)*np.exp(-3*tt)
    for drop_t in np.arange(45.0, dur, 45.0):
        s, e = int(drop_t*SR), min(n, int((drop_t+1.0)*SR)); tt = np.arange(e-s)/SR
        bed[s:e] += 0.4*np.sin(2*np.pi*35*tt)*np.exp(-2*tt)
    step = int(1.4*SR); tk = int(0.03*SR)
    tt = np.arange(tk)/SR; tick = 0.05*np.sin(2*np.pi*1800*tt)*np.exp(-80*tt)
    for s in range(0, n-tk, step): bed[s:s+tk] += tick
    bed = bed/np.max(np.abs(bed))*0.5
    return AudioArrayClip(np.stack([bed,bed],axis=1), fps=SR)

# ---------------- SCRIPT + RENDER ----------------
def write_script(topic, series, angle, bible="", prefs=""):
    return qwen(DNA.format(topic=topic, series=series, angle=ANGLES[angle], bible=bible or bible_txt(), prefs=prefs or prefs_txt()))
def quality_gate(topic, sc):
    return qwen(GATE.format(topic=topic, script=json.dumps(sc)))
def apply_gate(sc, g):
    if g.get("scenes"):
        for s in g["scenes"]:
            s["narration"] = adsense_scrub(s["narration"]); s["ost"] = adsense_scrub(s.get("ost",""))
        sc["scenes"] = g["scenes"]
    if g.get("title_options"): sc["title_options"] = g["title_options"]
    if g.get("share_line"): sc["share_line"] = g["share_line"]
    if g.get("cold_open_A"): sc["cold_open_A"] = g["cold_open_A"]
    if g.get("cold_open_B"): sc["cold_open_B"] = g["cold_open_B"]
    sc["advisory"] = g.get("advisory","")
    return sc
def script_with_floor(topic, series, angle):
    sc = write_script(topic, series, angle)
    g = quality_gate(topic, sc); sc = apply_gate(sc, g)
    for _ in range(1):
        try:
            if int(g.get("slop_clean",0)) < 70 or int(g.get("emotion",0)) < 60:
                decide(f"Quality floor failed (slop {g.get('slop_clean')}, emotion {g.get('emotion')}) → auto-regenerate.")
                sc = write_script(topic, series, angle)
                g = quality_gate(topic, sc); sc = apply_gate(sc, g)
        except Exception: break
    return sc, g
def render_cold_open_preview(sc, voice, mood, ep):
    a, b = sc.get("cold_open_A",""), sc.get("cold_open_B","")
    paths = []
    for tag, txt in (("A", a), ("B", b)):
        if not txt: continue
        ap = f"{TMP}/coldopen_{tag}_{ep}.mp3"
        open(ap,"wb").write(speak(txt, voice, mood))
        ac = AudioFileClip(ap)
        vu = None
        try: vu = wan_video(wan_video_prompt(f"intense single subject, gold rim light, matte black, cinematic"))
        except Exception: pass
        if not vu: vu = pexels_clip("intense cinematic subject")
        vc = VideoFileClip(fetch(vu,f"cold_{tag}_{ep}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration < ac.duration: vc = concatenate_videoclips([vc, vc.copy()])
        vc = vc.with_duration(ac.duration).with_audio(ac)
        out = f"{TMP}/coldopen_{tag}_{ep}.mp4"
        vc.write_videofile(out, codec="libx264", audio_codec="aac", fps=24, logger=None)
    return paths

def sponsor_blocks(sp, voice, mood):
    b = [(ImageClip(card_img("A WORD FROM", sp["name"])).with_duration(2.5), silence(2.5), None)]
    if sp.get("video"):
        svc = VideoFileClip(sp["video"]).resized((1280,720)).with_fps(24)
        sa = svc.audio if svc.audio is not None else silence(svc.duration)
        b.append((svc, sa, f"[Sponsor segment: {sp['name']}]"))
    elif sp.get("image"):
        ap = f"{TMP}/sp.mp3"
        open(ap,"wb").write(speak(sp.get("script") or f"This investigation is brought to you by {sp['name']}.", voice, mood))
        b.append((image_ad_clip(sp["image"], sp["name"]), AudioFileClip(ap), f"[Sponsor segment: {sp['name']}]"))
    else:
        ap = f"{TMP}/sp.mp3"
        open(ap,"wb").write(speak(sp.get("script") or f"This investigation is brought to you by {sp['name']}.", voice, mood))
        ac = AudioFileClip(ap)
        b.append((ImageClip(card_img(sp["name"], "a word from our sponsor")).with_duration(ac.duration), ac, sp.get("script","")))
    b.append((ImageClip(card_img("NOW, BACK TO", "the investigation")).with_duration(2.5), silence(2.5), None))
    return b

def render(sc, topic, series, pilot, music, voice, mood, sp=None, angle="Dark expose (default)", supporters=None):
    scenes = sc["scenes"][:4] if pilot else sc["scenes"]
    parts = []; n = len(scenes)
    hopeful = angle in ("Comeback / positive", "David vs Goliath")
    for i, s in enumerate(scenes):
        ap = f"{TMP}/a{i}.mp3"; open(ap,"wb").write(speak(s["narration"], voice, mood))
        ac = AudioFileClip(ap)
        vu = None
        for _try in range(2):
            try:
                vu = wan_video(wan_video_prompt(s["visual"])); break
            except Exception: vu = None
        if not vu: vu = pexels_clip(" ".join(s["visual"].split()[:8]))
        vc = VideoFileClip(fetch(vu,f"c{i}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration < ac.duration: vc = concatenate_videoclips([vc, vc.copy()])
        vc = vc.with_duration(ac.duration)
        if s.get("ost"):
            vc = CompositeVideoClip([vc, ImageClip(ost_img(s["ost"]))
                 .with_duration(min(3,ac.duration)).with_start(ac.duration*0.35).with_position((0,560))])
        parts.append((vc, ac, s["narration"]))
    title = (ImageClip(card_img("SHADOW LEDGER", f"{series} · {TONE_LABEL.get(angle,'A DARK EXPOSE')}")).with_duration(3), silence(3), None)
    adv = sc.get("advisory") or ""
    advclip = (ImageClip(card_img("VIEWER NOTE", adv)).with_duration(3), silence(3), None) if adv else None
    cred = (ImageClip(credits_img(supporters)).with_duration(4.5), silence(4.5), None) if supporters else None
    end   = (ImageClip(card_img("SUBSCRIBE", sc.get("share_line") or "the next ledger opens soon")).with_duration(5), silence(5), None)
    base = [parts[0], title] + ([advclip] if advclip else []) + parts[1:]
    if sp and sp.get("name") and sp.get("approved"):
        idx = 2 if sp.get("place","").startswith("After") else max(2, len(base)-1)
        base = base[:idx] + sponsor_blocks(sp, voice, mood) + base[idx:]
    order = base + ([cred] if cred else []) + [end]
    vids, auds, srt, markers, t = [], [], [], [], 0.0
    for vc, ac, txt in order:
        vids.append(vc.with_audio(ac)); auds.append(ac)
        if txt: markers.append(t); srt.append((t, t+ac.duration, txt))
        t += ac.duration
    vid = concatenate_videoclips(vids)
    aud = concatenate_audioclips(auds)
    layers_a = [aud]
    if music and os.path.exists(music):
        mc = AudioFileClip(music); nn2 = int(vid.duration//mc.duration)+1
        layers_a.append(concatenate_videoclips([mc]*nn2).with_duration(vid.duration).with_volume_scaled(0.10))
    markers.append(vid.duration*0.68)
    layers_a.append(sound_bed(vid.duration, markers, hopeful=hopeful).with_volume_scaled(0.6))
    final = vid.with_audio(CompositeAudioClip(layers_a).with_duration(vid.duration))
    layers = [final]
    if os.path.exists(f"{TMP}/bug.png"):
        layers.append(ImageClip(f"{TMP}/bug.png").resized(height=64).with_position((28,28)).with_duration(final.duration))
    for drop_t in np.arange(45.0, final.duration-1, 45.0):
        layers.append(pattern_interrupt(0.8).with_start(drop_t).with_position(("center","center")))
    layers.append(ImageClip(card_img("IF YOU FOLLOW THE MONEY,","subscribe - new investigations weekly",transparent=True))
                  .with_duration(5).with_start(final.duration*0.68).with_position((76,540))
                  .with_effects([vfx.FadeIn(0.6), vfx.FadeOut(0.8)]))
    final = CompositeVideoClip(layers)
    out = f"{TMP}/episode_{hashlib.md5(topic.encode()).hexdigest()}.mp4"
    final.write_videofile(out, codec="libx264", audio_codec="aac", fps=24, logger=None)
    return out, srt

# ---------------- SHORTS + TRAFFIC + DUBS ----------------
def shorts_three(video_path, hooks, ep):
    outs = []
    vd = VideoFileClip(video_path).duration
    starts = [3, max(4, vd*0.35), max(5, vd*0.6)]
    for k, s0 in enumerate(starts):
        c = VideoFileClip(video_path).subclipped(s0, min(s0+32, vd-2))
        c = c.resized(height=1920); w = c.size[0]
        c = c.cropped(x1=(w-1080)//2, x2=(w-1080)//2+1080)
        hk = hooks[k] if k < len(hooks) else "FOLLOW THE MONEY"
        ov = ImageClip(ost_img(hk)).with_duration(min(4, c.duration)).with_start(0.5).with_position(("center",120))
        c = CompositeVideoClip([c, ov])
        p = f"{TMP}/shorts_{ep}_{k}.mp4"; c.write_videofile(p, codec="libx264", audio_codec="aac", fps=24, logger=None)
        outs.append(p)
    return outs
def traffic_short(video_path, hook):
    vd = VideoFileClip(video_path).duration
    c = VideoFileClip(video_path).subclipped(3, min(28, vd-6))
    c = c.resized(height=1920); w = c.size[0]
    c = c.cropped(x1=(w-1080)//2, x2=(w-1080)//2+1080)
    ov = ImageClip(ost_img(hook)).with_duration(min(4, c.duration)).with_start(3).with_position(("center",120))
    intro = tiktok_intro(hook)
    endc = ImageClip(card_img("FULL FILM ON YOUTUBE","search: SHADOW LEDGER")).with_duration(3).with_audio(silence(3))
    fin = concatenate_videoclips([intro, CompositeVideoClip([c, ov]), endc])
    p = f"{TMP}/tiktok_traffic.mp4"; fin.write_videofile(p, codec="libx264", audio_codec="aac", fps=24, logger=None)
    return p
def dubs(sc):
    full = " ".join(s["narration"] for s in sc["scenes"])[:6000]
    tr = qwen(f"Translate this documentary narration to Spanish and German, preserving tone. Return JSON {{'es':'...','de':'...'}}: {full}")
    import edge_tts, asyncio
    outs = {}
    for lang, v in (("es","es-ES-AlvaroNeural"), ("de","de-DE-ConradNeural")):
        try:
            p = f"{TMP}/dub_{lang}.mp3"
            asyncio.run(edge_tts.Communicate(tr.get(lang,""), v).save(p))
            outs[lang] = p
        except Exception: pass
    return outs

def srt_text(srt):
    out=[]
    for i,(a,b,txt) in enumerate(srt,1):
        f=lambda s:f"{int(s//3600):02d}:{int(s%3600//60):02d}:{int(s%60):02d},000"
        out.append(f"{i}\n{f(a)} --> {f(b)}\n{txt}\n")
    return "\n".join(out)
def thumbs(topic, hook):
    urls = wan_images(f"YouTube thumbnail 1280x720: {topic}. single dramatic subject, gold rim light on matte black, teal shadows, 35mm grain, negative space left, no words")
    ps=[]
    for j,u in enumerate(urls):
        img = Image.open(io.BytesIO(requests.get(u).content)).convert("RGB")
        d = ImageDraw.Draw(img)
        d.text((70,600), hook.upper(), font=F(92), fill=GOLD, stroke_width=6, stroke_fill=(0,0,0))
        p=f"{TMP}/thumb_{j}.png"; img.save(p); ps.append(p)
    return ps

CHECKLIST = """YOUTUBE UPLOAD CHECKLIST — SHADOW LEDGER (keep the boss happy)
[ ] Audience: NOT made for kids (channel default — already set)
[ ] Paid promotion: {sp}
[ ] Title/Description/Tags: AdSense-scrubbed automatically (see metadata.txt)
[ ] Viewer advisory included in description if present
[ ] Subtitles: upload subtitles.srt
[ ] End screen (last 20s): link NEXT episode + Subscribe
[ ] Cards: link series playlist
[ ] Pin pinned_comment.txt as the pinned comment
[ ] Post community_post.txt ~24h after publish
[ ] Category: Education or News & Politics
[ ] License: Standard YouTube License
[ ] THUMBS A/B: upload thumb_A now; after 24h check CTR in Studio; if thumb_B wins, swap.
[ ] SHORTS: publish Mon/Wed 12:00 EST
[ ] TIKTOK/REELS/FB: post TIKTOK_TRAFFIC + Shorts from the 'Shadow Ledger' brand account same day
[ ] SCHEDULE: auto-scheduled Fridays 16:00 EST (or manual via SCHEDULE.txt)
[ ] PHASE 2: upload the CASE_FILE pdf to Ko-fi Shop using kofi_product_*.txt listing
"""
RIGHTS = """RIGHTS RECORD — SHADOW LEDGER
Footage: Pexels-licensed stock video + original AI-generated clips (Wan, Alibaba Model Studio).
Voice: Qwen/CosyVoice neural TTS via licensed API with free neural fallbacks (Microsoft Edge / Google).
Music: ORIGINAL procedural score (synthesized in-studio, zero third-party rights).
Sponsor segments: supplied by sponsor or produced with disclosure. Script: original AI-assisted editorial commentary
on publicly documented events. Case File dossier: original compilation of public-source facts. Brand/logo/cards: original.
This record supports any copyright or monetization dispute.
"""
SHOP_BLURB = """📄 THE CASE FILE — {topic}
The full dossier behind this episode: timeline, key players, the numbers translated to
human scale, glossary and discussion questions. Beautifully typeset, black & gold.
Grab it for $5 (pay-what-you-want): [PASTE YOUR KO-FI SHOP LINK HERE]
The video stays free forever. Case Files fund the next investigation. Thank you for standing with the ledger.
"""

def pack_entries(it, ep, support, shop, series, do_shorts3=True, do_dubs=False):
    entries=[]; sc = it["script"]; sl = slug(it["topic"])
    extra = {"shorts":[], "tiktok":None, "cold_opens":[]}
    tp = thumbs(it["topic"], sc.get("hook_words",""))
    advline = f" Viewer advisory: {sc['advisory']}" if sc.get("advisory") else ""
    raw = qwen(f"Topic: {it['topic']}. Support: {support}. Pinned: {sc['pinned_question']}. Binge-pitch: {sc.get('binge_pitch','')}. Share line: {sc.get('share_line','')}.{advline} "
           f"Add disclaimer: 'Editorial commentary based on public sources; not financial advice.' Mention: full Case File dossier available via shop link. "
           f"Return JSON {{'title':'<60 chars, no clickbait', 'description':'hook + synopsis + chapters + support + case file line + advisory/disclaimer + 3 hashtags', 'tags':[15], 'shorts_titles':[2]}}")
    safe = {"title": adsense_scrub(raw["title"]), "description": adsense_scrub(raw["description"]),
            "tags": [adsense_scrub(t) for t in raw["tags"]], "shorts_titles": [adsense_scrub(t) for t in raw["shorts_titles"]]}
    if do_shorts3:
        hooks = (safe["shorts_titles"] + [sc.get("share_line","FOLLOW THE MONEY")])[:3]
        spaths = shorts_three(it["out"], hooks, ep)
        extra["shorts"] = spaths
        for k,p in enumerate(spaths):
            entries.append((f"SHORTS_{k+1}_{ep}_{sl}.mp4", p, True))
        tk = traffic_short(it["out"], hooks[0])
        extra["tiktok"] = tk
        entries.append((f"TIKTOK_TRAFFIC_{ep}_{sl}.mp4", tk, True))
    if do_dubs:
        for lang, p in dubs(sc).items():
            entries.append((f"DUB_{lang}_{ep}.mp3", p, True))
    dos = dossier(it["topic"], sc)
    cfp = f"{TMP}/case_file_{ep}.pdf"; case_file_pdf(it["topic"], series, dos, support, cfp, ep=ep)
    entries.append((f"EPISODE_{ep}_{sl}.mp4", it["out"], True))
    for j,p in enumerate(tp): entries.append((f"THUMB_{'AB'[j]}_{ep}_{sl}.png", p, True))
    entries.append(("subtitles.srt", srt_text(it["srt"]).encode(), False))
    entries.append(("metadata.txt", json.dumps(safe, indent=2).encode(), False))
    pin = sc["pinned_question"] + f"\n☕ Support the investigation: {support}"
    if shop: pin += f"\n📄 CASE FILE #{ep} for this episode: {shop}"
    entries.append(("pinned_comment.txt", pin.encode(), False))
    entries.append(("community_post.txt", json.dumps(sc["community_poll"]).encode(), False))
    entries.append((f"CASE_FILE_{ep}_{sl}.pdf", cfp, True))
    entries.append((f"kofi_product_{ep}.txt",
        (f"KO-FI PRODUCT LISTING — ready to paste\nProduct name: CASE FILE #{ep} — {it['topic']}\nPrice: $5 (enable pay-what-you-want)\n"
         f"Type: Digital product\nFile to upload: CASE_FILE_{ep}_{sl}.pdf\nProduct image: THUMB_A_{ep}_{sl}.png\n\nDescription:\n"
         + SHOP_BLURB.format(topic=f"#{ep} — {it['topic']}")).encode(), False))
    entries.append(("upload_checklist.txt", CHECKLIST.format(sp=f"YES — {it.get('sp','')} (tick paid promotion + disclose)" if it.get("sp") else "No").encode(), False))
    entries.append(("rights_record.txt", RIGHTS.encode(), False))
    entries.append(("decisions_log.txt", "\n".join(jload(DEC_F, [])).encode(), False))
    return entries, safe, extra

# ---------------- BACKGROUND WORKER ----------------
def batch_worker(topics=None, auto_upload=False, auto_schedule=True, auto_feed=False):
    JOB = job_load(); JOB["running"] = True; JOB["log"] = []; job_save(JOB)
    S = jload(SET_F, {})
    line = load_line()
    todo = [x for x in line if (not topics) or x["topic"] in topics]
    todo = [x for x in todo if x["status"] not in ("rendered","rejected")]
    for it in todo:
        idx = line.index(it); t0 = time.time()
        JOB["current"] = f"EP {idx+1}/{len(line)} · {it['topic'][:34]}"; job_save(JOB)
        try:
            if not it["script"]:
                it["angle"] = it.get("angle") or S.get("angle") or "Dark expose (default)"
                it["script"], g = script_with_floor(it["topic"], S.get("series","The Monopoly Files"), it["angle"])
                it["gate"] = g
                decide(f"EP{idx+1} Gate: slop-clean {g.get('slop_clean','-')}/100, yt-policy {g.get('yt_policy','-')}, legal fixes {g.get('legal_flags_fixed','-')}.")
            m_use = mood_for(idx) if S.get("auto_mood", True) else S.get("mood", "Calm investigator (default)")
            sp = jload(SPO_F, None)
            it["sp"] = sp["name"] if (sp and sp.get("approved")) else ""
            sups = jload(SUP_F, []) or None
            out, srt = render(it["script"], it["topic"], S.get("series","The Monopoly Files"), S.get("pilot", True),
                              S.get("music"), S.get("voice","longanyang"), m_use, sp,
                              angle=it.get("angle") or "Dark expose (default)", supporters=sups)
            it["out"], it["srt"], it["status"], it["err"] = out, srt, "rendered", ""
            el = int(time.time()-t0)
            secs, cost = estimate(it["script"], S.get("pilot", True))
            costs = jload(COST_F, []); costs.append({"ep":idx+1,"topic":it["topic"][:30],"est":round(cost,3),"engine":ENGINE["v"],"ts":datetime.now().isoformat()})
            jsave(COST_F, costs)
            JOB["log"].append(f"✅ EP {idx+1} {it['topic'][:30]} — {el//60}m{el%60:02d}s · voice {ENGINE['v']} · ~${cost:.2f}")
            decide(f"EP{idx+1} rendered in {el//60}m — voice {ENGINE['v']}, mood {m_use}.")
            if auto_upload and (os.path.exists(YT_TOK_F) or YT_RT):
                try:
                    advline = f" Viewer advisory: {it['script'].get('advisory','')}" if it['script'].get('advisory') else ""
                    raw = qwen(f"Topic: {it['topic']}. Support: {S.get('support','https://ko-fi.com/shadowledger')}. Pinned: {it['script'].get('pinned_question','')}. Binge-pitch: {it['script'].get('binge_pitch','')}. Share line: {it['script'].get('share_line','')}.{advline} "
                           f"Add disclaimer: 'Editorial commentary based on public sources; not financial advice.' "
                           f"Return JSON {{'title':'<60 chars, no clickbait', 'description':'hook + synopsis + chapters + support + case file line + advisory/disclaimer + 3 hashtags', 'tags':[15], 'shorts_titles':[2]}}")
                    safe = {"title": adsense_scrub(raw["title"]), "description": adsense_scrub(raw["description"]),
                            "tags": [adsense_scrub(t) for t in raw["tags"]], "shorts_titles": [adsense_scrub(t) for t in raw["shorts_titles"]]}
                    when = friday_for(idx) if auto_schedule else None
                    vid = yt_upload(out, safe["title"], safe["description"], safe["tags"], when=when)
                    if vid:
                        it["yt_id"] = vid
                        JOB["log"].append(f"☁️ Uploaded + {'scheduled ' + (when or '') if when else 'PRIVATE'}: {vid}")
                        decide(f"EP{idx+1} auto-uploaded {'scheduled '+when if when else 'private'} as {vid}.")
                        ep = f"{idx+1:03d}"
                        hooks = (safe["shorts_titles"] + [it['script'].get("share_line","FOLLOW THE MONEY")])[:3]
                        spaths = shorts_three(out, hooks, ep)
                        for k, p in enumerate(spaths):
                            if os.path.exists(p):
                                try:
                                    tt = (safe["shorts_titles"][k] if k < len(safe["shorts_titles"]) else "Follow the money") + " #shorts #finance"
                                    sw = monday_for(idx+k) if auto_schedule else None
                                    yt_upload(p, tt, f"Full investigation on Shadow Ledger (YouTube). {S.get('support','')}", ["shorts","finance","documentary"], when=sw)
                                    JOB["log"].append(f"☁️ Shorts #{k+1} uploaded{' + scheduled' if sw else ''}")
                                except Exception as e:
                                    JOB["log"].append(f"⚠️ Shorts #{k+1} upload failed: {str(e)[:50]}")
                except Exception as e:
                    JOB["log"].append(f"⚠️ Auto-upload failed: {str(e)[:80]}")
        except Exception as e:
            it["status"], it["err"] = "failed", str(e)[:120]
            JOB["log"].append(f"⚠️ EP {idx+1} {it['topic'][:30]} — {str(e)[:70]}")
        save_line(line); job_save(JOB)
    if auto_feed:
        try:
            n = 0
            for topic, sc, why in predict_spikes(S.get("series","finance"))[:6]:
                if sc >= 80 and queue_topic(topic, sc, "AUTO-ANTICIPATED"): n += 1
            JOB["log"].append(f"🤖 Auto-feed: {n} predicted ≥80 topics queued for next batch.")
        except Exception:
            pass
    JOB["running"] = False; JOB["current"] = ""; job_save(JOB)

# ---------------- REVENUE FORECAST ----------------
def revenue_forecast():
    rev = jload(REV_F, {"kofi_tips":[],"case_files":[]})
    line = load_line()
    subs_estimate = len([i for i in line if i["status"]=="rendered"]) * 80
    hours_estimate = len([i for i in line if i["status"]=="rendered"]) * 40
    yt_ready = subs_estimate >= 1000 and hours_estimate >= 4000
    total_kofi = sum(t.get("amount",0) for t in rev.get("kofi_tips",[]))
    total_cf = sum(t.get("amount",0) for t in rev.get("case_files",[]))
    monthly_kofi = total_kofi * 4 if rev.get("kofi_tips") else 0
    monthly_cf = total_cf * 4 if rev.get("case_files") else 0
    monthly_yt = len([i for i in line if i["status"]=="rendered"]) * 150 if yt_ready else 0
    monthly_total = monthly_kofi + monthly_cf + monthly_yt
    return {
        "subs_estimate": subs_estimate, "hours_estimate": hours_estimate, "yt_ready": yt_ready,
        "monthly_kofi": monthly_kofi, "monthly_cf": monthly_cf, "monthly_yt": monthly_yt,
        "monthly_total_usd": monthly_total, "monthly_total_zar": monthly_total * 18.5,
        "target_reached": monthly_total * 18.5 >= 100000,
    }

# ---------------- UI (MISSION CONTROL v39 — PERMANENT VAULT) ----------------
st.set_page_config(page_title="Shadow Ledger Studio", page_icon="🎬", layout="wide")
st.markdown("""<style>
 .stApp{background:linear-gradient(180deg,#0a1220 0%,#0e1a2e 60%,#0a1424 100%);}
 h1,h2,h3{color:#ffd76a !important;font-family:Georgia,serif;text-shadow:0 2px 12px rgba(245,197,66,.25);}
 p,span,div,label{color:#e8f0ff;}
 [data-testid="stCaptionContainer"],.stCaption{color:#9fb3d1 !important;}
 .console{display:flex;gap:1.2rem;align-items:center;padding:.55rem 1rem;margin:.4rem 0 .9rem;
   background:linear-gradient(180deg,#12213a,#0d1830);border:1px solid #24406b;border-radius:14px;
   box-shadow:inset 0 1px 0 #ffffff14, 0 6px 18px #0008;font-size:.8rem;letter-spacing:.08em;color:#9fb3d1;
   font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;flex-wrap:wrap;}
 .led{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:.45rem;box-shadow:0 0 10px currentColor;background:currentColor;}
 .led.g{color:#3ddc84;animation:pulse 2.2s infinite}.led.r{color:#ff5d5d}.led.y{color:#ffd76a;animation:pulse 1.4s infinite}
 .clk{margin-left:auto;color:#39d0ff}
 div.stButton>button{
   background:linear-gradient(180deg,#2a4a7a 0%,#1a3050 55%,#12233f 100%);
   color:#ffd76a;border:1px solid #3b6ea8;border-radius:14px;
   font-weight:800;letter-spacing:.07em;text-transform:uppercase;font-size:.8rem;
   padding:.7rem 1.2rem;text-shadow:0 1px 0 rgba(0,0,0,.6);
   box-shadow:0 4px 0 #0a1526,0 8px 20px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.22);
   transition:transform .12s, box-shadow .12s, border-color .12s, color .12s;}
 div.stButton>button:hover{transform:translateY(-2px);border-color:#f5c542;color:#fff;
   box-shadow:0 6px 0 #0a1526,0 12px 26px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.3),0 0 22px rgba(245,197,66,.25);}
 div.stButton>button:active{transform:translateY(2px);box-shadow:0 1px 0 #0a1526,0 4px 10px rgba(0,0,0,.5);}
 [data-testid="stTabs"] [data-testid="stTab"]{
   background:linear-gradient(180deg,#1b2c4a,#12203a);border:1px solid #2a4a7a;border-radius:12px;
   color:#9fb3d1;font-weight:800;letter-spacing:.06em;text-transform:uppercase;font-size:.76rem;
   padding:.65rem 1.1rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 3px 8px rgba(0,0,0,.4);}
 [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{
   background:linear-gradient(180deg,#35597f,#1a3050);color:#ffd76a;border-color:#f5c542;
   box-shadow:inset 0 2px 0 #f5c542,0 0 18px rgba(245,197,66,.25);}
 [data-testid="stTabs"] [data-testid="stTab"]:hover{color:#fff;border-color:#39d0ff}
 .card{background:linear-gradient(180deg,#13223c,#0e1a30);border:1px solid #24406b;border-radius:14px;
   padding:.7rem 1rem;margin:.45rem 0;color:#e8f0ff;box-shadow:inset 0 1px 0 #ffffff10,0 4px 14px #0007;}
 .chip{display:inline-block;padding:.28rem .75rem;border-radius:999px;margin:0 .3rem .3rem 0;font-size:.78rem;
   border:1px solid #33507c;font-weight:700;letter-spacing:.05em}
 .chip.done{background:#0f3524;color:#7ee2a8;border-color:#1d5c3a;box-shadow:0 0 12px #3ddc8422}
 .chip.now{background:#3a2f14;color:#ffd76a;border-color:#8a6d2f;box-shadow:0 0 14px #f5c54233;animation:pulse 1.8s infinite}
 .chip.todo{background:#141c2b;color:#7d8fa8}
 .stTextInput input,.stTextArea textarea,.stNumberInput input{
   background:#0d1830 !important;border:1px solid #2a4a7a !important;color:#e8f0ff !important;border-radius:10px;}
 .stTextInput input:focus,.stTextArea textarea:focus{border-color:#f5c542 !important;box-shadow:0 0 0 3px #f5c54222 !important}
 [data-testid="stSidebar"]{background:linear-gradient(180deg,#0c1626,#0a1220);border-right:1px solid #24406b}
 .stProgress > div > div{background:linear-gradient(90deg,#f5c542,#39d0ff) !important}
</style>""", unsafe_allow_html=True)

line = st.session_state.line
jb = job_load()
st.markdown(f"<div class='console'><span><span class='led {'y' if jb['running'] else 'g'}'></span>RENDER ENGINE {'ACTIVE' if jb['running'] else 'IDLE'}</span>"
            f"<span><span class='led {'g' if (os.path.exists(YT_TOK_F) or YT_RT) else 'r'}'></span>YOUTUBE LINK</span>"
            f"<span><span class='led g'></span>VOICE CHAIN</span><span><span class='led g'></span>CEO'S PILOT</span>"
            f"<span><span class='led g'></span>VAULT</span>"
            f"<span class='clk'>🕒 {datetime.now().strftime('%H:%M:%S')}</span></div>", unsafe_allow_html=True)

flags = {"scan": bool(st.session_state.get("scan")), "slate": bool(line),
 "series": bool(st.session_state.get("series_checked")),
 "script": any(i["status"] in ("scripted","approved","rendered") for i in line),
 "approve": any(i["status"] in ("approved","rendered") for i in line),
 "render": any(i["status"]=="rendered" for i in line),
 "pack": bool(st.session_state.get("packed"))}
order = ["scan","slate","series","script","approve","render","pack"]
labels = {"scan":"1 SCAN","slate":"2 SLATE","series":"3 SERIES","script":"4 SCRIPT+GATE","approve":"5 APPROVE","render":"6 RENDER","pack":"7 PACK"}
states = {}; cur_set = False
for k in order:
    if flags[k]: states[k] = "done"
    else: states[k] = "now" if not cur_set else "todo"; cur_set = True
pct = sum(flags.values())/len(order)
st.title("🎬 SHADOW LEDGER — Mission Control")
st.markdown("".join(f"<span class='chip {states[k]}'>{'✅ ' if states[k]=='done' else '⭐ ' if states[k]=='now' else '🔒 '}{labels[k]}</span>" for k in order), unsafe_allow_html=True)
st.progress(pct, text=f"Pipeline {int(pct*100)}% complete")
st.caption("💡 v39: ☁️ Permanent Vault (Drive backup + YouTube re-link) — a reboot can never erase you again.")

support = st.sidebar.text_input("☕ Support link (Ko-fi)", "https://ko-fi.com/shadowledger")
shop = st.sidebar.text_input("📄 Case File shop link", "")
ep_num = st.sidebar.text_input("Episode #", "001")
voice = st.sidebar.text_input("Narrator voice ID", "longanyang")
mood = st.sidebar.selectbox("Narration mood", list(MOODS))
auto_mood = st.sidebar.checkbox("🎭 Auto-rotate mood per episode", True)
auto_upload = st.sidebar.checkbox("☁️ Auto-upload after render", True)
auto_schedule = st.sidebar.checkbox("📅 Auto-schedule Fridays 16:00 EST", True)
auto_feed = st.sidebar.checkbox("🤖 Auto-feed: refill slate with ≥80 predictions after every batch", False)
if st.sidebar.button("🔊 Hear 10s voice audition"):
    try:
        ab = f"{TMP}/audition.mp3"
        open(ab,"wb").write(speak("In 2019, a single signature moved forty-one billion dollars. Nobody noticed. Until now.", voice, mood))
        st.sidebar.audio(ab)
        st.sidebar.caption(f"🎙️ Engine used: {ENGINE['v']}")
    except Exception as e:
        st.sidebar.error(f"🔇 Audition unavailable right now: {str(e)[:80]}")
music = st.sidebar.file_uploader("House score (optional)", type=["mp3","wav"])
music_path = None
if music:
    music_path = f"{TMP}/house_{music.name}"; open(music_path,"wb").write(music.getbuffer())
series = st.sidebar.text_input("Series brand", "The Monopoly Files")
with st.sidebar.expander("💳 CREDIT & RAMP CONSOLE", expanded=True):
    cr = cred_load()
    loaded = st.number_input("Loaded credits (ZAR)", 0, 100000, int(cr.get("loaded_zar",0)), 100)
    if int(loaded) != int(cr.get("loaded_zar",0)):
        cr["loaded_zar"] = int(loaded); cred_save(cr)
    costs = jload(COST_F, [])
    spent_usd = sum(c.get("est",0) for c in costs)
    spent_zar = spent_usd * 18.5
    remaining = loaded - spent_zar
    eps = len(costs) or 1
    burn = spent_zar/eps
    eps_left = int(remaining/burn) if burn>0 else 999
    st.caption(f"Spent: **R{spent_zar:.0f}** · Remaining: **R{remaining:.0f}**")
    st.caption(f"Burn/episode: **R{burn:.0f}** · Episodes left: **{eps_left}**")
    if loaded>0:
        frac = max(0.0, min(1.0, remaining/loaded))
        st.progress(frac, text=f"{int(100*frac)}% credits left")
        if frac < 0.2: st.warning("⚠️ Top up soon — under 20% credits")
        else: st.success("🟢 Healthy runway")
    ra = ramp_advisor()
    st.caption(f"Phase: **{ra['phase']}**")
    st.caption(f"Recommendation: **{ra['rec']}**")
    if ra["ctr"]: st.caption(f"Avg CTR so far: {ra['ctr']:.1f}%")
    st.caption("🏆 PRESTIGE MODE: always highest models")
with st.sidebar.expander("🧑✈️ CEO's Pilot (talk to your studio)"):
    st.caption("Plain words in → studio actions out.")
    pmsg = st.text_input("Your order, CEO")
    if st.button("📨 Send to Pilot"):
        if pmsg.strip():
            with st.spinner("🧑‍✈️ Pilot interpreting…"):
                reply, outs = ceo_pilot(pmsg)
            st.success(reply)
            for o in outs: st.caption(o)
with st.sidebar.expander("🔑 Connect YouTube + Vault"):
    if os.path.exists(YT_TOK_F) or YT_RT:
        st.success("Connected ✅")
        if st.button("🔁 Reconnect (grant Drive Vault)"):
            st.code(yt_auth_url())
            st.caption("Open, sign in, allow, then paste the new code below.")
    else:
        st.caption("Needs YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET in Secrets.")
        if YTC_ID and st.button("1️⃣ Get connect link"):
            st.code(yt_auth_url())
    code = st.text_input("2️⃣ Paste the code")
    if code and st.button("🔗 Connect"):
        try:
            rt = yt_connect(code.strip())
            st.success("Connected ✅ (YouTube + Drive Vault)")
            if rt: st.code(f'YT_REFRESH_TOKEN = "{rt}"')
        except Exception as e:
            st.error(str(e)[:120])
    if st.button("🔄 Recover rendered videos from YouTube"):
        ups = yt_channel_uploads()
        line = load_line(); hits = 0
        for vid, title in ups:
            for it in line:
                if it["topic"] and it["topic"][:25].lower() in title.lower() and it["status"]!="rendered":
                    it["yt_id"] = vid; it["status"]="rendered"; hits += 1
        save_line(line)
        st.success(f"✅ Re-linked {hits} uploaded episode(s) from your channel.")
with st.sidebar.expander("🧠 Director's decisions"):
    decs = jload(DEC_F, [])
    if decs:
        for d in decs[-14:]: st.caption("• " + d)
adv = balance_advice(line)
angle_list = list(ANGLES)
angle = st.sidebar.selectbox("Story angle", angle_list, index=angle_list.index(adv) if adv in angle_list else 0)
if adv: st.sidebar.info(f"🎨 Advisor (learned from analytics): **{adv}**")
pilot = st.sidebar.checkbox("PILOT MODE (60-90s test)", True)
jsave(SET_F, {"series":series,"pilot":pilot,"auto_mood":auto_mood,"mood":mood,"angle":angle,"voice":voice,"music":music_path,"support":support})
tab1,tab2,tabS,tab3,tab4 = st.tabs(["🥚 1·SCAN","🏭 2·PRODUCE","💼 SPONSOR","📦 3·PUBLISH","📈 STRATEGY"])

with tab1:
    st.markdown("### 🗺️ START HERE — press in this order")
    st.caption("1️⃣ 📰 Refresh bulletin → 2️⃣ ⚡ Send hot topics to Scan → 3️⃣ 🥚 STEP 1 Golden Egg scan → 4️⃣ 🏭 STEP 2–5 approve → 5️⃣ 🎬 STEP 6 render (background) → 6️⃣ 🔄 Refresh later → 7️⃣ 📦 pack / ☁️ upload.")
    if "seeds_str" not in st.session_state: st.session_state.seeds_str = load_seeds()
    pending = st.session_state.pop("seed_add", None)
    if pending and pending not in st.session_state.seeds_str:
        st.session_state.seeds_str += "\n" + pending
    pending_multi = st.session_state.pop("seed_add_multi", None)
    if pending_multi:
        curset = set(st.session_state.seeds_str.splitlines())
        for t in pending_multi:
            if t not in curset:
                st.session_state.seeds_str += "\n" + t
    with st.expander("📰 WHAT'S HOT — live trend bulletin (this week + 14-day forecast)", expanded=True):
        b = jload(BULL_F, {})
        if b.get("ts"):
            ago = datetime.now() - datetime.fromisoformat(b["ts"])
            st.caption(f"🕒 Last refreshed: {ago.days}d {ago.seconds//3600}h ago")
        else:
            st.caption("Never refreshed — press the button to listen to YouTube.")
        if st.button("📰 Refresh bulletin (listen to YouTube)"):
            with st.spinner("📡 Listening to YouTube search + scoring…"):
                st.session_state["bull"] = refresh_bulletin(st.session_state.seeds_str)
        items = st.session_state.get("bull") or jload(BULL_F, {}).get("items", [])
        for i in items[:10]:
            tag = "🔥" if i["sc"]>=80 else "⭐" if i["sc"]>=60 else "•"
            score_txt = f" — 🥚 {i['sc']}/100" if i["sc"] else ""
            c1, c2, c3 = st.columns([4,1,1])
            c1.markdown(f"{tag} **{i['t']}**{score_txt} · `{i['src']}`")
            if c2.button("➕", key=f"bq_{i['t']}"):
                if queue_topic(i["t"], i["sc"], i["src"]): st.success("✅ Queued to line")
            if c3.button("📋", key=f"bs_{i['t']}"):
                st.session_state["seed_add"] = i["t"]
        ca, cb = st.columns(2)
        if ca.button("⚡ Send ALL ≥70 to Scan seeds"):
            cur = [x for x in st.session_state.seeds_str.splitlines() if x.strip()]
            add = [i["t"] for i in items if i["sc"]>=70 and i["t"] not in cur]
            st.session_state["seed_add_multi"] = add
            st.success(f"✅ {len(add)} hot topics will appear in the Scan box below.")
        if cb.button("➕ Queue ALL ≥80 straight to line"):
            n = sum(1 for i in items if i["sc"]>=80 and queue_topic(i["t"], i["sc"], "BULLETIN"))
            st.success(f"✅ Queued {n} winners to the Production Line.")
    seeds = st.text_area("Seed topics (your ideas + hot topics you sent — scanned by Golden Egg)", st.session_state.seeds_str)
    st.session_state.seeds_str = seeds
    if st.button("🥚 STEP 1 · Run Golden Egg scan"):
        save_seeds(seeds)
        with st.spinner(" Scanning the market…"):
            results = []
            for s in [x for x in seeds.splitlines() if x.strip()]:
                score, why = golden_egg(s.strip())
                results.append((s.strip(), score, why))
            st.session_state.scan = sorted(results, key=lambda r: -r[1])
    if st.session_state.get("scan"):
        for j,(t, sc, w) in enumerate(st.session_state.scan):
            style = "border-color:#f5c542" if j==0 else ""
            pre = "🏆 " if j==0 else ""
            st.markdown(f"<div class='card' style='{style}'>{pre}<b>{t}</b> — 🥚 {sc}/100 · {w}</div>", unsafe_allow_html=True)
        st.caption("🏆 = winner (pre-ticked in PRODUCE). ➡️ Go to 🏭 2·PRODUCE.")
    with st.expander("🎯 Hunt 80+ engine"):
        htheme = st.text_input("Theme to hunt", st.session_state.get("hunt_theme","global financial scandals, monopolies and comebacks"))
        hmin = st.number_input("Minimum score", 50, 100, 80, 5)
        if st.button("🎯 Hunt high scorers"):
            with st.spinner("🎯 Generating + scoring candidates…"):
                st.session_state["hunt_res"] = hunt(htheme, int(hmin))
            if not st.session_state["hunt_res"]:
                st.warning(f"No topics ≥{int(hmin)} in this theme — broaden it or lower the bar.")
        for t, sc, why in st.session_state.get("hunt_res", []):
            st.markdown(f"**🔥 {t}** — 🥚 {sc}/100 · {why}")
            if st.button(f"➕ Queue {t[:44]}", key=f"hq_{t}"):
                if queue_topic(t, sc, "HUNTED"): st.success("✅ Queued")
    with st.expander("🔮 Trend Anticipation"):
        seed_topic = st.text_input("Seed a topic to predict what will spike", "BlackRock")
        if st.button("🔮 Predict next spikes"):
            with st.spinner("🔮 Scoring live search phrases…"):
                st.session_state["spikes"] = predict_spikes(seed_topic)
        for topic, sc, why in st.session_state.get("spikes", [])[:6]:
            pre = "🔥" if sc > 70 else "⭐" if sc > 50 else ""
            st.markdown(f"**{pre} {topic}** — 🥚 {sc}/100 · {why}")
            c1, c2 = st.columns(2)
            if c1.button("➕ Queue", key=f"aq_{topic}"):
                if queue_topic(topic, sc, "ANTICIPATED"): st.success("✅ Queued")
            if c2.button("🎯 Hunt similar", key=f"hs_{topic}"):
                st.session_state["hunt_theme"] = topic
    with st.expander("📊 Analytics loop (studio learns)"):
        if os.path.exists(YT_TOK_F) or YT_RT:
            vids = [(i.get("yt_id"), i.get("angle"), i["topic"]) for i in line if i.get("yt_id")]
            if vids and st.button("Fetch 48h metrics"):
                for vid, a, t in vids:
                    try:
                        m = yt_metrics(vid)
                        if m:
                            met = jload(MET_F, {}); met[vid] = {**m, "angle":a, "topic":t}
                            jsave(MET_F, met)
                            st.caption(f"• {t[:30]}: views {m['views']} · CTR {m['ctr']}%")
                            if m.get("ctr") and float(m["ctr"]) < 2.0:
                                queue_topic(f"RECOVERY: {t[:40]}", 60, "AUTO-RECOVERY")
                            hof_update(vid, (m.get("views",0)/1000) + (float(m.get("ctr") or 0)*5))
                    except Exception as e:
                        st.caption(f"• {t[:20]}: {str(e)[:50]}")
                st.success("Metrics saved — advisor + Hall of Fame updated.")
        else:
            st.caption("Connect YouTube (sidebar) to enable the learning loop.")
    with st.expander("🏆 Hall of Fame + auto-sequel"):
        h = jload(HOF_F, [])
        if h:
            best = hof_best()
            st.markdown(f"**🏆 Top episode so far:** score {best['score']:.1f}")
            if st.button("🎬 Auto-queue sequel to top episode"):
                top_topic = next((m.get("topic") for vid, m in jload(MET_F, {}).items() if vid == best["vid"]), None)
                if top_topic:
                    seq = next((e.get("sequel","") for e in jload(BIBLE_F, []) if top_topic in e.get("topic","")), "")
                    if queue_topic(seq or f"Sequel to: {top_topic}", 80, "HALL-OF-FAME-SEQUEL"): st.success("✅ Sequel queued")
        else:
            st.caption("Hall of Fame populates as episodes go live.")

with tab2:
    if not flags["scan"]:
        st.warning("⬅️ STEP 1 first: refresh the 📰 bulletin + run the Golden Egg scan in 🥚 1·SCAN.")
    else:
        st.markdown("## STEP 2 · Tick your slate")
        picks = []
        for j,(t, sc, w) in enumerate(st.session_state.scan):
            if st.checkbox(f"{t}  (🥚 {sc}/100)", value=(j==0), key=f"ck_{t}"): picks.append((t, sc))
        if st.button("➕ STEP 2 · Add ticked topics to Production Line"):
            for t, sc in picks: queue_topic(t, sc, "")
            st.success("✅ STEP 2 complete — slate locked.")
        with st.expander("➕ Add a custom topic instead"):
            custom = st.text_input("Custom topic", "")
            if custom.strip() and st.button("Add custom topic"):
                queue_topic(custom.strip(), 0, "CUSTOM")
        if flags["slate"]:
            st.markdown("## 📋 Your Production Line")
            for i, it in enumerate(line):
                tag_badge = f"<span class='chip done'>{it['tag']}</span>" if it["tag"] else ""
                st.markdown(f"<div class='card'>EP {i+1} · <b>{it['topic']}</b> {tag_badge} · {TONE_LABEL.get(it.get('angle') or 'Dark expose (default)','')} — <code>{it['status']}</code></div>", unsafe_allow_html=True)
            st.markdown("## STEP 3 · Series potential")
            c1, c2 = st.columns(2)
            if c1.button("🎭 STEP 3 · Check series potential"):
                with st.spinner(" Analysing…"): st.session_state.splan = series_plan(line[0]["topic"])
            if c2.button("⏭️ Standalone — skip series"):
                st.session_state.series_checked = True; st.session_state.splan = None
            if st.session_state.get("splan"):
                spn = st.session_state.splan
                st.markdown(f"**Verdict:** {'✅ YES — a series!' if spn['series'] else '❌ standalone'} — {spn['why']}")
                for e in spn.get("episodes",[]): st.markdown(f"• {e}")
                if spn["series"] and st.button("➕ Add series episodes to line"):
                    for e in spn.get("episodes",[]): queue_topic(e, line[0]["score"], "SERIES")
                    st.session_state.series_checked = True
                    st.success("✅ STEP 3 complete.")
        if flags["series"]:
            st.markdown("## STEP 4 · Script + 🛡️ Gate + 🚨 Guard + Quality Floor")
            if any(i["status"]=="queued" for i in line):
                if st.button("📜 STEP 4 · Write script + run Quality Gate"):
                    it = next(x for x in line if x["status"]=="queued")
                    idx_abs = line.index(it)
                    m_use = mood_for(idx_abs) if auto_mood else mood
                    a_use = it.get("angle") or angle
                    bar = st.progress(0.2, text="✍️ Writing Netflix-DNA script…")
                    it["angle"] = a_use
                    it["script"], g = script_with_floor(it["topic"], series, a_use)
                    it["gate"] = g
                    it["status"] = "scripted"; save_line(line)
                    st.session_state.edits = {i2:(s["narration"],s["visual"]) for i2,s in enumerate(it["script"]["scenes"])}
                    bar.progress(1.0, text="✅ Script + Gate complete")
                    st.success("✅ STEP 4 complete.")
        cur = next((x for x in line if x["status"]=="scripted"), None)
        if cur:
            st.markdown("## STEP 5 · Review & Approve (Director's Cut)")
            if cur.get("gate"):
                g = cur["gate"]
                st.markdown(f"<div class='card' style='border-color:#3ddc84'>🛡️ slop <b>{g.get('slop_clean','-')}/100</b> · emotion <b>{g.get('emotion','-')}/100</b> · yt-policy <b>{g.get('yt_policy','-')}</b></div>", unsafe_allow_html=True)
            st.markdown("### 🎯 Cold-Open A/B Test")
            if cur["script"].get("cold_open_A"): st.info(f"**A:** {cur['script']['cold_open_A']}")
            if cur["script"].get("cold_open_B"): st.info(f"**B:** {cur['script']['cold_open_B']}")
            if st.button("🎬 Generate 30s previews of A + B"):
                with st.spinner("🎬 Filming both cold opens…"):
                    st.session_state[f"cold_previews_{line.index(cur)}"] = render_cold_open_preview(cur["script"], voice, mood, line.index(cur))
            previews = st.session_state.get(f"cold_previews_{line.index(cur)}")
            if previews:
                for tag, p, txt in previews:
                    st.video(p); st.caption(f"**Cold open {tag}:** {txt}")
                    if st.button(f"✅ Lock cold open {tag}", key=f"pick_{tag}_{line.index(cur)}"):
                        for s in cur["script"]["scenes"][:1]: s["narration"] = txt
                        save_line(line); st.success(f"✅ Cold open {tag} locked in.")
            st.markdown("### 📝 Scene-by-scene edits")
            for i2, s in enumerate(cur["script"]["scenes"]):
                nar, vis = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                nn = st.text_area(f"Narration {i2+1}", nar, key=f"n_{i2}", height=90)
                vv = st.text_input(f"Visual {i2+1}", vis, key=f"v_{i2}")
                st.session_state.edits[i2] = (nn, vv)
            if st.button("✅ STEP 5 · Approve script → unlock Render"):
                for i2, s in enumerate(cur["script"]["scenes"]):
                    nn, vv = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                    s["narration"], s["visual"] = nn, vv
                cur["status"] = "approved"; save_line(line)
                bible_append(line.index(cur)+1, cur["topic"], cur["script"])
                st.success("✅ STEP 5 complete.")
        st.markdown("## STEP 6 · Render — ☁️ CLOUD BACKGROUND (close the laptop)")
        jb = job_load()
        if jb["running"]:
            st.info(f"🟢 Rendering: **{jb['current']}** — safe to close this tab/laptop.")
        else:
            st.caption("⚪ Render engine idle.")
        for ln in jb["log"][-8:]: st.caption(ln)
        st.button("🔄 Refresh status")
        cA, cB = st.columns(2)
        if cA.button("🎬 STEP 6 · Render next episode (background)"):
            if job_load()["running"]: st.warning("A render is already running.")
            else:
                threading.Thread(target=batch_worker, args=([next((x for x in line if x["status"]=="approved"), None)["topic"]] if next((x for x in line if x["status"]=="approved"), None) else [], auto_upload, auto_schedule, auto_feed), daemon=True).start()
                st.success("☁️ Started on the cloud.")
        if cB.button("🎬 RENDER ENTIRE LINE (background)"):
            if job_load()["running"]: st.warning("A render is already running.")
            else:
                threading.Thread(target=batch_worker, args=(None, auto_upload, auto_schedule, auto_feed), daemon=True).start()
                st.success("☁️ Series batch started on the cloud.")
        rendered = [i for i in line if i["status"]=="rendered" and i["out"] and os.path.exists(i["out"])]
        if rendered:
            st.markdown("### 📥 SERIES DOWNLOADS + PREVIEWS + ☁️ UPLOADS")
            base_n = int(ep_num)
            for i2, it in enumerate(rendered):
                ep = f"{base_n+i2:03d}"; sl = slug(it["topic"])
                st.markdown(f"**EP {ep} · {it['topic']}** {('· 🆔 '+it['yt_id']) if it.get('yt_id') else ''}")
                st.video(it["out"])
                c1, c2, c3 = st.columns(3)
                c1.download_button("⬇️ Episode MP4", open(it["out"],"rb").read(), f"EPISODE_{ep}_{sl}.mp4", key=f"dl_{ep}")
                if c2.button(f"📦 Build EP {ep} pack", key=f"pk_{ep}"):
                    with st.spinner("📦 Building pack…"):
                        entries, safe, extra = pack_entries(it, ep, support, shop, series)
                    st.session_state[f"extra_{ep}"] = extra; st.session_state[f"safe_{ep}"] = safe
                    z = io.BytesIO()
                    with zipfile.ZipFile(z,"w") as zf:
                        for name, data, is_path in entries:
                            if is_path: zf.write(data, name)
                            else: zf.writestr(name, data)
                    st.session_state[f"packzip_{ep}"] = z.getvalue()
                if st.session_state.get(f"packzip_{ep}"):
                    c3.download_button("⬇️ EP pack zip", st.session_state[f"packzip_{ep}"], f"SHADOW_LEDGER_PACK_{ep}.zip", key=f"dlz_{ep}")
    st.download_button("💾 Backup production line", json.dumps(line).encode(), "shadow_line.json")
    up = st.file_uploader("Restore backup", type=["json"])
    if up: st.session_state.line = json.load(up); save_line(st.session_state.line)

with tabS:
    st.markdown("## 💼 SPONSOR SUITE")
    spc = jload(SPO_F, None)
    if spc:
        st.success(f"Active slot: **{spc['name']}**")
        if st.button("🗑️ Clear sponsor slot"): jsave(SPO_F, None)
    sp_name = st.text_input("Sponsor name", "")
    sp_note = st.text_area("What does the sponsor do?", "")
    if st.button("✍️ Qwen draft the ad read"):
        if sp_name.strip(): st.session_state.ad_draft = ad_draft(sp_name.strip(), sp_note)["script"]
    sp_script = st.text_area("Ad read script", st.session_state.get("ad_draft",""))
    sp_place = st.selectbox("Placement", ["After cold open + title (TV style)", "Before the final reveal"])
    sp_ok = st.checkbox("✅ Sponsor approved this cut")
    if st.button("💾 Save sponsor slot"):
        if sp_name.strip():
            jsave(SPO_F, {"name": sp_name.strip(), "script": sp_script, "video": None, "image": None, "place": sp_place, "approved": sp_ok})
            st.success("✅ Slot saved.")
        else:
            st.warning("Enter a sponsor name first.")

with tab3:
    rendered = [i for i in line if i["status"]=="rendered" and i["out"] and os.path.exists(i["out"])]
    if not rendered:
        st.warning("⬅️ Render an episode first (🏭 2·PRODUCE → STEP 6). If a reboot cleared the cache, use 'Recover rendered videos from YouTube' in the sidebar, then re-render Shorts/packs.")
    else:
        st.markdown("## STEP 7 · Build the Publish Pack")
        choice = st.selectbox("Episode to pack", [i["topic"] for i in rendered])
        it = rendered[[i["topic"] for i in rendered].index(choice)]
        do_dubs = st.checkbox("🌍 Add ES + DE dub tracks", False)
        if st.button("📦 STEP 7 · Build SEO + Publish Pack + Case File"):
            with st.spinner("📦 Building the full pack…"):
                entries, safe, extra = pack_entries(it, ep_num, support, shop, series, do_dubs=do_dubs)
            z = io.BytesIO()
            with zipfile.ZipFile(z,"w") as zf:
                for name, data, is_path in entries:
                    if is_path: zf.write(data, name)
                    else: zf.writestr(name, data)
            st.session_state.packed = True
            st.download_button("📦 Download PUBLISH PACK (zip)", z.getvalue(), f"SHADOW_LEDGER_PACK_{ep_num}.zip")
            st.success(f"✅ Pack ready. 🏁")
            st.json(safe)

with tab4:
    rf = revenue_forecast()
    st.markdown("## 📈 Strategy + Forecast")
    st.markdown(f"**Projected monthly:** ${rf['monthly_total_usd']:.0f} USD ≈ R{rf['monthly_total_zar']:.0f}")
    st.markdown(f"Subs est: ~{rf['subs_estimate']} · Watch hrs est: ~{rf['hours_estimate']} · {'✅ YPP-ready' if rf['yt_ready'] else '⏳ building'}")
    st.markdown("""**v39 — PERMANENT VAULT.** NEW: ☁️ Drive Vault auto-backup of your production line on every change ·
    🔄 'Recover rendered videos from YouTube' re-links uploaded episodes after any reboot · boot-time auto-restore from
    Vault. A reboot can NEVER erase your pipeline again. PLUS the full v38 engine: Credit & Ramp Console, PRESTIGE lock,
    WHAT'S HOT bulletin, CEO's Pilot, Hunt 80+, Anticipation/Radar, auto-upload/schedule, auto-feed, HMI interface,
    self-healing auth, cold-open A/B, pattern interrupts, TikTok traffic, Hall of Fame, flop recovery, Episode Bible,
    dubs, sponsor suite, revenue forecast, numbered packs, SCHEDULE.txt. **Your studio now has permanent memory.** 🎬""")
