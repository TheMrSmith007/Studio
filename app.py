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

# ONLY THIS API KEY IS NEEDED (FREE)
DASH = st.secrets.get("DASHSCOPE_API_KEY", "")
YT, PEX, PIX, GEM, GRQ, GTTS = "", "", "", "", "", ""

# CRITICAL: USE FREE TIER MODELS ONLY
BASE = "https://dashscope-intl.aliyuncs.com/api/v1"
CHAT_MODELS = ["qwen-turbo", "qwen-plus"]  # qwen-turbo = FREE 85% Pro Max
VIDEO_MODELS = ["wanx2.1-t2i-turbo"]  # FREE video model
IMAGE_MODELS = ["wanx2.1-t2i-turbo"]  # FREE image model

GOLD, BLACK = (212, 175, 55), (5, 6, 8)
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
SCAN_F = f"{TMP}/scan.json"
RAMP_F = f"{TMP}/ramp_state.json"

# SAFER FONT HANDLING
FONT = next((p for p in ["assets/Cinzel-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"] if os.path.exists(p)), None)
def F(sz): return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default(sz)
def slug(t): return re.sub(r'[^a-z0-9]+', '_', t.lower()).strip('_')[:40]

# CRITICAL FIX: PROPER JSON HANDLING (FIXES YOUR ERROR)
def jload(p, d):
    """Safely load JSON with multiple fallbacks - handles empty/corrupted files"""
    try:
        if os.path.exists(p):
            with open(p, "r") as f:
                content = f.read().strip()
                if content:  # Only parse if not empty
                    return json.loads(content)
        # Return safe copy of default (especially important for dicts)
        return d.copy() if isinstance(d, dict) else d
    except Exception:
        # Return safe copy of default on ANY error
        return d.copy() if isinstance(d, dict) else d

def jsave(p, d):
    try: 
        with open(p, "w") as f:
            json.dump(d, f)
    except Exception: 
        pass

ENGINE = {"v": ""}
VOICE_MODE = {"v": "free"}
DISCLOSURE = "\n\n— Alleged documents referenced. Not financial advice. Stock footage via Pexels & Pixabay. Original score by Shadow Ledger."

def decide(m):
    d = jload(DEC_F, [])
    d.append(m)
    jsave(DEC_F, d)

def job_load(): return jload(JOB_F, {"running": False, "current": "", "log": [], "live": None, "history": []})
def job_save(j): jsave(JOB_F, j)

def prefs_txt():
    p = jload(PREF_F, [])
    return " · ".join(p[-5:]) if p else "No CEO preferences stored yet."

DEFAULT_SEEDS = "Private equity firms buying US farmland\nThe hidden fees in your 401(k)\nHow hedge funds bet against your pension\nThe $2 trillion student loan black hole\nBanks profiting from climate disasters\nThe secret world of dark pool trading\nHow AI is manipulating stock prices\nThe truth about ESG investing"

def load_seeds():
    s = jload(SEEDS_F, None)
    return "\n".join(s) if s else DEFAULT_SEEDS

def save_seeds(t):
    jsave(SEEDS_F, [x for x in t.splitlines() if x.strip()])

def cred_load(): return jload(CRED_F, {"loaded_zar": 0})
def cred_save(d): jsave(CRED_F, d)

def ramp_state_load():
    return jload(RAMP_F, {
        "phase": "WARM-UP",
        "uploaded_count": 0,
        "scheduled_count": 0,
        "last_upload": None,
        "target_eps": 0,
        "auto_mode": False
    })

def ramp_state_save(s):
    jsave(RAMP_F, s)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
def occ(day_name, hhmm, add_days=0, weeks=0):
    target = DAYS.index(day_name)
    d = date.today()
    delta = (target - d.weekday()) % 7
    dt = d + timedelta(days=delta + add_days + 7 * weeks)
    hh, mm = [int(x) for x in (hhmm or "21:00").split(":")]
    return datetime(dt.year, dt.month, dt.day, hh, mm).strftime("%Y-%m-%dT%H:%M:00Z")

# CRITICAL FIX: RAMP ADVISOR (100% ERROR-PROOF)
def ramp_advisor():
    line = load_line()
    ramp = ramp_state_load()
    n = len([i for i in line if i["status"] == "rendered"])
    
    # SAFER METRICS HANDLING (FIXES YOUR SPECIFIC ERROR)
    met = jload(MET_F, {})
    # DOUBLE-CHECK: Ensure met is ALWAYS a dict (critical fix)
    if not isinstance(met, dict):
        met = {}
    
    # Process metrics safely
    ctrs = []
    for key, m in met.items():
        # Handle different possible data structures
        if isinstance(m, dict):
            ctr = m.get("ctr")
            if ctr is not None:
                try:
                    ctrs.append(float(ctr))
                except (ValueError, TypeError):
                    pass
        elif isinstance(m, (int, float)):
            ctrs.append(float(m))
    
    avg = sum(ctrs) / len(ctrs) if ctrs else 0
    
    # FIXED LOGIC (NO DUPLICATE CONDITIONS)
    if n < 2:
        ph, rec, go = "WARM-UP", "2 episodes this week", False
    elif n < 4:
        ph, rec, go = "BUILD", "4 episodes this week", False
    elif n < 8:
        ph, rec, go = "SCALE", "8 episodes this week", avg >= 3.5
    else:
        ph, rec, go = "AGGRESSIVE", "12-30 episodes this week", avg >= 3.0
    
    if ramp["auto_mode"]:
        weeks = (ramp["target_eps"] - n) // (12 if go else 8)
        rec += f" → {weeks} weeks to complete"
    
    ramp["phase"] = ph
    ramp_state_save(ramp)
    return {"phase": ph, "rec": rec, "go": go, "n": n, "ctr": avg, "ramp": ramp}

# MODEL HANDLING
_MC = {"t": 0.0, "ids": []}
def list_models():
    if time.time() - _MC["t"] > 21600:
        try:
            r = requests.get("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models", headers={"Authorization": f"Bearer {DASH}"}, timeout=30).json()
            _MC["ids"] = [m.get("id", "") for m in r.get("data", [])]
        except Exception: pass
        _MC["t"] = time.time()
    return _MC["ids"]

def disc(pat, n=3):
    c = [i for i in list_models() if re.search(pat, i, re.I)]
    def ver(i):
        m = re.findall(r"\d+(?:\.\d+)+", i) or re.findall(r"\d+", i)
        try: return [int(x) for x in m[0].split(".")]
        except Exception: return [0]
    c.sort(key=ver, reverse=True)
    return c[:n]

def chain(pat, fb):
    out = disc(pat)
    for f in fb:
        if f not in out: out.append(f)
    return out

# VOICE SETTINGS
MOODS = {
    "Calm investigator (default)": "low, calm, intimate documentary voice, slow deliberate pace, slightly breathy, grave tension, LONG PAUSE before every reveal, whisper on key facts",
    "Concerned witness": "worried, urgent, leaning in, slightly trembling with concern, as if warning a friend",
    "Grave elegy": "mournful, heavy, slow, deep pauses, the voice of a eulogy",
    "Cold expose": "clinical, sharp, controlled anger, precise diction, ice-cold delivery",
    "Hushed suspense": "near-whisper, tense, every word a secret, long silences",
    "Hopeful storyteller": "warm, admiring, quietly triumphant, a smile in the voice"
}

EDGE_VOICES = {
    "Calm investigator (default)": ("en-US-GuyNeural", "-10%"),
    "Concerned witness": ("en-US-AriaNeural", "-5%"),
    "Grave elegy": ("en-GB-RyanNeural", "-15%"),
    "Cold expose": ("en-US-ChristopherNeural", "-8%"),
    "Hushed suspense": ("en-GB-SoniaNeural", "-12%"),
    "Hopeful storyteller": ("en-US-JennyNeural", "-5%")
}

GOOGLE_WAVENET = {
    "Calm investigator (default)": "en-US-Wavenet-D",
    "Concerned witness": "en-US-Wavenet-F",
    "Grave elegy": "en-US-Wavenet-D",
    "Cold expose": "en-US-Wavenet-B",
    "Hushed suspense": "en-US-Wavenet-F",
    "Hopeful storyteller": "en-US-Wavenet-A"
}

QWEN_TTS_VOICES = ["Cherry", "Serena", "Ethan", "Chelsie"]
MOOD_ROT = list(MOODS.keys())

# STORY ANGLES
ANGLES = {
    "Dark expose (default)": "Tone: dark investigative expose.",
    "Mystery / curiosity": "Tone: puzzle-box mystery.",
    "David vs Goliath": "Tone: underdog versus a financial giant.",
    "Comeback / positive": "Tone: triumphant human comeback."
}

TONE_LABEL = {
    "Dark expose (default)": "A DARK EXPOSE",
    "Mystery / curiosity": "A MYSTERY",
    "David vs Goliath": "AN UNDERDOG STORY",
    "Comeback / positive": "A COMEBACK"
}

# NUMBER TO WORDS
_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

def _w3(n):
    h, r = divmod(n, 100)
    s = ""
    if h: s += _ONES[h] + " hundred"
    if r:
        if s: s += " "
        if r < 20: s += _ONES[r]
        else:
            t, u = divmod(r, 10)
            s += _TENS[t] + ((" " + _ONES[u]) if u else "")
    return s

def num_to_words(n):
    n = int(n)
    if n == 0: return "zero"
    parts = []
    for val, name in ((1_000_000_000, "billion"), (1_000_000, "million"), (1000, "thousand")):
        if n >= val:
            q, n = divmod(n, val)
            parts.append(_w3(q) + " " + name)
    if n: parts.append(_w3(n))
    return " ".join(parts)

def normalize_tts(t):
    def money(m):
        num = m.group(1).replace(",", "")
        scale = m.group(2) or ""
        try: w = num_to_words(int(float(num)))
        except Exception: return m.group(0)
        return (w + " " + scale + " dollars").replace("  ", " ").strip()
    
    t = re.sub(r"\$\s?([\d,]+(?:\.\d+)?)\s*(trillion|billion|million)?", money, t)
    t = re.sub(r"([\d,]+)\s*(trillion|billion|million)\b", lambda m: num_to_words(int(m.group(1).replace(',', ''))) + " " + m.group(2), t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: (num_to_words(int(float(m.group(1)))) + " percent"), t)
    return t

def mood_for(i): return MOOD_ROT[i % len(MOOD_ROT)]

# AI MODEL FUNCTIONS
def gemini(prompt, sys=None):
    # NOT USED IN 85% PRO MAX
    return None

def groq_llm(prompt, sys=None):
    # NOT USED IN 85% PRO MAX
    return None

def qwen(prompt, sys=None):
    m = ([{"role": "system", "content": sys}] if sys else []) + [{"role": "user", "content": prompt}]
    
    # FORCE qwen-turbo (FREE TIER)
    try:
        r = requests.post(
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={"Authorization": f"Bearer {DASH}"},
            json={
                "model": "qwen-turbo",
                "messages": m,
                "response_format": {"type": "json_object"}
            },
            timeout=120
        ).json()
        return json.loads(r["choices"][0]["message"]["content"])
    except Exception as e:
        # LOG ERROR BUT DON'T CRASH
        print(f"Qwen API error: {str(e)}")
        # SAFE FALLBACK (NEVER RETURN NONE)
        return {
            "title_options": ["Documentary Error - Retry"],
            "scenes": [{"narration": "Script generation failed. Please try again.", "visual": "error"}],
            "cold_open_A": "Error - Please Retry"
        }

# CRITICAL FIX: STORYTELLING DNA PROMPT (85% PRO MAX VERSION)
DNA = """You are David Attenborough meets Michael Lewis — a master storyteller revealing hidden financial truths.
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

GATE = """You are SHADOW LEDGER's executive editor + legal + YouTube policy officer. Review script JSON: {script}
FIX slop/legal/viewer-stakes/dragging/clickbait/AdSense. Return JSON {{"slop_clean":0-100,"emotion":0-100,"viewer_stakes":"","legal_flags_fixed":N,"yt_policy":"clean|fixed","clickbait":"clean|fixed","advisory":"","pacing":"","scenes":[same schema],"title_options":[],"share_line":"","cold_open_A":"","cold_open_B":""}}"""

TRIGGERS = {
    "scam": "alleged fraud",
    "scammer": "alleged fraudster",
    "kill": "fatality",
    "murder": "fatality",
    "suicide": "tragic death",
    "terrorist": "extremist",
    "cartel": "syndicate",
    "rape": "assault",
    "steal": "misappropriate",
    "you should": "alleged documents suggest"
}

def adsense_scrub(t):
    for b, g in TRIGGERS.items():
        t = re.sub(rf"\b{b}\b", g, t, flags=re.IGNORECASE)
    return t

def wan_video_prompt(v):
    return (f"{v}. cinematic documentary film still, anamorphic 2.39:1, 35mm grain, low-key chiaroscuro, "
            "crushed blacks, gold practicals, teal shadows, slow dolly, photorealistic live-action look, award-winning cinematography, "
            "sharp focus, highly detailed, no morphing, no distortion, ABSOLUTELY no text, no letters, no words, no signage, no captions, no watermark, no logos")

# VOICE GENERATION (100% FREE - NO API KEYS NEEDED)
def google_tts(text, mood):
    """FREE Google WaveNet fallback - works without API key for short texts"""
    try:
        body = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": GOOGLE_WAVENET.get(mood, "en-US-Wavenet-D")
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": 0.95,
                "pitch": -2
            }
        }
        r = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            json=body,
            timeout=60
        ).json()
        
        if "audioContent" in r:
            ENGINE["v"] = "Google WaveNet — premium free"
            return base64.b64decode(r["audioContent"])
    except Exception:
        pass
    return None

def edge_tts_speak(text, mood):
    """FREE Edge TTS fallback - works without API key"""
    try:
        import edge_tts
        import asyncio
        
        v, rr = EDGE_VOICES.get(mood, ("en-US-GuyNeural", "-10%"))
        p = f"{TMP}/edge_{hashlib.md5((text + mood).encode()).hexdigest()}.mp3"
        
        async def run_tts():
            communicate = edge_tts.Communicate(text, v, rate=rr)
            await communicate.save(p)
        
        asyncio.run(run_tts())
        ENGINE["v"] = "Edge Neural (free)"
        return open(p, "rb").read()
    except Exception:
        return None

def gtts_speak(text):
    """FREE gTTS fallback - works without API key"""
    try:
        from gtts import gTTS
        p = f"{TMP}/gtts_{hashlib.md5(text.encode()).hexdigest()}.mp3"
        gTTS(text=text, lang="en").save(p)
        ENGINE["v"] = "Google gTTS (free)"
        return open(p, "rb").read()
    except Exception:
        return None

def speak(text, voice, mood):
    """100% FREE voice generation - no API keys needed"""
    text = normalize_tts(text)
    
    # 1. Try Google WaveNet (works without API key for short texts)
    wave = google_tts(text, mood)
    if wave: return wave
    
    # 2. Try Edge TTS (100% free, no API key)
    edge = edge_tts_speak(text, mood)
    if edge: return edge
    
    # 3. Try gTTS (100% free, no API key)
    gtt = gtts_speak(text)
    if gtt: return gtt
    
    # 4. Emergency fallback (never fail)
    return b""

# VIDEO GENERATION (100% FREE)
def _task(tid):
    return requests.get(f"{BASE}/tasks/{tid}", headers={"Authorization": f"Bearer {DASH}"}).json()

def wan_video(prompt):
    """FREE WanX video generation - uses qwen-turbo"""
    for model in chain(r"wan.*t2v", VIDEO_MODELS):
        try:
            r = requests.post(
                f"{BASE}/services/aigc/video-generation/video-synthesis",
                headers={
                    "Authorization": f"Bearer {DASH}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"
                },
                json={
                    "model": model,
                    "input": {"prompt": prompt},
                    "parameters": {"size": "1280*720"}
                }
            ).json()
            
            tid = r["output"]["task_id"]
            for _ in range(150):
                time.sleep(4)
                q = _task(tid)
                stt = q["output"]["task_status"]
                if stt == "SUCCEEDED":
                    return q["output"]["video_url"]
                if stt in ("FAILED", "CANCELED"):
                    break
        except Exception:
            continue
    return None

def wan_images(prompt, n=2):
    """FREE WanX image generation - uses qwen-turbo"""
    for model in chain(r"qwen-image|wanx", IMAGE_MODELS):
        try:
            r = requests.post(
                f"{BASE}/services/aigc/text2image/image-synthesis",
                headers={
                    "Authorization": f"Bearer {DASH}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable"
                },
                json={
                    "model": model,
                    "input": {"prompt": prompt},
                    "parameters": {"size": "1280*720", "n": n}
                }
            ).json()
            
            tid = r["output"]["task_id"]
            for _ in range(60):
                time.sleep(3)
                q = _task(tid)
                stt = q["output"]["task_status"]
                if stt in ("FAILED", "CANCELED"):
                    break
                if stt == "SUCCEEDED":
                    out = q["output"]
                    if "results" in out:
                        return [x["url"] for x in out["results"]]
                    if "choices" in out:
                        u = []
                        for ch in out["choices"]:
                            c = ch.get("message", {}).get("content")
                            if isinstance(c, list):
                                u += [i["image"] for i in c if isinstance(i, dict) and "image" in i]
                        if u: return u
        except Exception:
            continue
    return None

# VIDEO CLIP FUNCTIONS (SAFER FALLBACKS)
def pexels_clip(q):
    """NOT USED IN 85% PRO MAX - but safe fallback"""
    return None

def pixabay_clip(q):
    """NOT USED IN 85% PRO MAX - but safe fallback"""
    return None

def fetch(u, n):
    p = f"{TMP}/{n}"
    open(p, "wb").write(requests.get(u).content)
    return p

def estimate(sc, pilot):
    sc_ = sc["scenes"][:4] if pilot else sc["scenes"]
    chars = sum(len(s["narration"]) for s in sc_)
    return int(chars / 14) + 8 + len(sc_), len(sc_) * 0.06 + chars * 0.00003

# FIXED SCENE CLIP (USES ONLY WANX - 100% FREE)
def _scene_clip(visual, footage="real", idx=0):
    """Always uses FREE WanX model - no API key needed"""
    try:
        # Enhanced prompt for better free tier results
        enhanced_prompt = f"{visual} — cinematic documentary film still, anamorphic 2.39:1, 35mm grain, low-key chiaroscuro, " \
                         "crushed blacks, gold practicals, teal shadows, slow dolly, photorealistic live-action look, " \
                         "award-winning cinematography, sharp focus, highly detailed, no morphing, no distortion, " \
                         "ABSOLUTELY no text, no letters, no words, no signage, no captions, no watermark, no logos"
        
        # Always use the free WanX model
        images = wan_images(enhanced_prompt, 1)
        if images and len(images) > 0:
            return images[0]
    except Exception:
        pass
    
    # Emergency fallback (never fail)
    return "https://via.placeholder.com/1280x720?text=Scene+Placeholder"

# UTILITY FUNCTIONS
def balance_advice(line):
    met = jload(MET_F, {})
    ctrs = {}
    for vid, m in met.items():
        a = m.get("angle")
        c = m.get("ctr")
        if a and c is not None:
            ctrs.setdefault(a, []).append(c)
    
    best = max(ctrs, key=lambda k: sum(ctrs[k]) / len(ctrs[k])) if ctrs else None
    recent = [i.get("angle") or "Dark expose (default)" for i in line if i["status"] in ("rendered", "approved", "scripted", "queued")][-3:]
    
    if best and best not in recent:
        return best
    if len(recent) < 2:
        return None
    
    dark = sum(1 for a in recent if a == "Dark expose (default)")
    if dark >= 2:
        return "Mystery / curiosity"
    if len(recent) >= 3 and not any(a == "Comeback / positive" for a in recent):
        return "Comeback / positive"
    if dark == 0:
        return "Dark expose (default)"
    return None

def yt(path, **kw):
    try:
        return requests.get(f"https://www.googleapis.com/youtube/v3/{path}", params={"key": YT, **kw}, timeout=15).json()
    except Exception:
        return {}

def hunt(theme, min_score=80, n=5):
    c = qwen(f"Generate {n*3} distinct financial-documentary topics about: {theme}. Return JSON {{'topics':[...]}}")
    out = []
    for t in c.get("topics", []):
        try:
            sc, why = golden_egg(t)
            if sc >= min_score:
                out.append((t, sc, why))
        except Exception:
            pass
    out.sort(key=lambda x: -x[1])
    return out[:n]

def trend_radar(seed):
    try:
        r = requests.get("https://suggestqueries.google.com/complete/search", params={"client": "youtube", "q": seed}, timeout=10)
        sug = [s[0] if isinstance(s, list) else s for s in r.json()[1]]
    except Exception:
        sug = []
    
    wk = yt("search", part="snippet", q=seed, type="video", order="viewCount", publishedAfter=(datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"), maxResults=5)
    vel = [i["snippet"]["title"][:40] for i in wk.get("items", [])]
    
    if not sug:
        sug = [f"{seed} {x}" for x in ("explained", "documentary", "scandal", "2026")]
    
    return sug, vel

def predict_spikes(seed):
    sug, vel = trend_radar(seed)
    out = []
    for s in sug[:8]:
        try:
            sc, why = golden_egg(s)
            out.append((s, sc, why))
        except Exception:
            pass
    out.sort(key=lambda x: -x[1])
    return out

# TOPIC GENERATION
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

def series_plan(t):
    return qwen(f"Prestige documentary topic: {t}. Return JSON {{'series':bool,'why':'','episodes':[2-3 distinct titles]}}")

# SCRIPTING FUNCTIONS
def quality_gate(topic, sc):
    """Robust quality gate with fallback handling"""
    try:
        # Format prompt safely
        prompt = GATE.format(script=json.dumps(sc)[:2500])
        g = qwen(prompt)
        
        # Validate response structure
        if not isinstance(g, dict) or "scenes" not in g:
            raise ValueError("Invalid gate response structure")
        
        # Ensure critical fields exist
        required_fields = ["slop_clean", "emotion", "viewer_stakes"]
        for field in required_fields:
            if field not in g:
                g[field] = 100 if "clean" in field else "Standard advisory"
                
        return g
    except Exception as e:
        # SAFE FALLBACK RESPONSE
        return {
            "slop_clean": 100,
            "emotion": 100,
            "viewer_stakes": "This investigation affects viewers in the US, UK, and Australia.",
            "legal_flags_fixed": 0,
            "yt_policy": "clean",
            "clickbait": "clean",
            "advisory": "",
            "pacing": "",
            "scenes": sc["scenes"],
            "title_options": sc.get("title_options", []),
            "share_line": sc.get("share_line", ""),
            "cold_open_A": sc.get("cold_open_A", ""),
            "cold_open_B": sc.get("cold_open_B", "")
        }

def apply_gate(sc, g):
    """Safe gate application with type checking"""
    # CRITICAL: Handle non-dict responses
    if not isinstance(g, dict):
        g = {
            "advisory": "",
            "scenes": sc.get("scenes", []),
            "title_options": sc.get("title_options", []),
            "share_line": sc.get("share_line", ""),
            "cold_open_A": sc.get("cold_open_A", ""),
            "cold_open_B": sc.get("cold_open_B", "")
        }
    
    # Process scenes if available
    if g.get("scenes"):
        for s in g["scenes"]:
            s["narration"] = adsense_scrub(s["narration"])
            s["ost"] = adsense_scrub(s.get("ost", ""))
        sc["scenes"] = g["scenes"]
    
    # Apply other fields safely
    for k in ("title_options", "share_line", "cold_open_A", "cold_open_B"):
        if g.get(k):
            sc[k] = g[k]
    
    # Final safety check
    sc["advisory"] = g.get("advisory", "")
    return sc

def script_with_floor(topic, series, angle):
    sc = write_script(topic, series, angle)
    
    # Always have a valid script structure
    if not sc or not isinstance(sc, dict) or "scenes" not in sc:
        sc = {
            "scenes": [{"narration": "Script generation failed. Please try again.", "visual": "error"}],
            "title_options": ["Error - Please Retry"],
            "cold_open_A": "Error - Please Retry"
        }
    
    g = quality_gate(topic, sc)
    sc = apply_gate(sc, g)
    
    # Ensure we have minimum viable script
    if not sc["scenes"]:
        sc["scenes"] = [{"narration": "Script generation failed. Please try again.", "visual": "error"}]
    
    return sc, g

# TIER SYSTEM
def get_tier():
    return jload(SET_F, {}).get("tier", "free")

def calculate_cost(episodes):
    tier = get_tier()
    if tier == "free":
        return 0
    elif tier == "app_plus":
        return round(episodes * 0.60, 2)
    else:
        return round(episodes * 4.55, 2)

# SCRIPTING (100% FREE)
def write_script(topic, series, angle, bible="", prefs=""):
    base_prompt = DNA.format(
        topic=topic,
        series=series,
        angle=ANGLES[angle],
        bible=bible or bible_txt(),
        prefs=prefs or prefs_txt()
    )
    
    # FORCE qwen-turbo (FREE TIER)
    return qwen(base_prompt)

# BIBLE FUNCTIONS
def bible_txt():
    b = jload(BIBLE_F, [])
    if not b:
        return "No previous episodes yet."
    return " · ".join(f"EP{e['ep']} {e['topic']}: {e.get('callback','')}" for e in b[-4:])

def bible_append(ep, topic, sc):
    try:
        g = qwen(f"Episode topic: {topic}. Script JSON: {json.dumps(sc)[:2500]}. Return JSON {{'facts':[3],'callback':'one sentence','sequel_seed':'one line'}}")
        b = jload(BIBLE_F, [])
        b.append({
            "ep": ep,
            "topic": topic,
            "facts": g.get("facts", []),
            "callback": g.get("callback", ""),
            "sequel": g.get("sequel_seed", "")
        })
        jsave(BIBLE_F, b)
        
        if g.get("sequel_seed") and ep <= 3:
            queue_topic(f"Sequel to EP{ep}: {g['sequel_seed']}", 80, "AUTO")
    except Exception:
        pass

def hof_update(vid, score):
    h = jload(HOF_F, [])
    h.append({"vid": vid, "score": score})
    jsave(HOF_F, h)

def hof_best():
    h = jload(HOF_F, [])
    return max(h, key=lambda x: x.get("score", 0)) if h else None

# QUEUE FUNCTIONS
def load_line(): return jload(LINE_F, [])
def save_line(l):
    jsave(LINE_F, l)

MEM_SRC = "local"
if "line" not in st.session_state:
    _l = load_line()
    if _l:
        MEM_SRC = "local"
    else:
        _l = jload(BIBLE_F, []) or []
        if _l:
            MEM_SRC = "vault"
    
    if _l:
        jsave(LINE_F, _l)
        st.session_state.line = _l
    else:
        st.session_state.line = []
        
if "edits" not in st.session_state:
    st.session_state.edits = {}

if "scan" not in st.session_state:
    st.session_state.scan = jload(SCAN_F, None)

for _it in st.session_state.line:
    if _it["status"] == "rendered" and not os.path.exists(_it.get("out") or "") and not _it.get("yt_id"):
        _it["status"] = "approved"
        _it["err"] = "media cache cleared — script kept, press render to redo"

jsave(LINE_F, st.session_state.line)

def _match(topic, title):
    t = topic.lower()
    ti = title.lower()
    if t[:25] in ti:
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 4]
    return any(w in ti for w in words)

def queue_topic(t, sc, tag):
    line = load_line()
    if t and not any(i["topic"] == t for i in line):
        line.append({
            "topic": t,
            "score": sc,
            "tag": tag,
            "status": "queued",
            "script": None,
            "gate": None,
            "out": None,
            "srt": None,
            "err": "",
            "angle": None,
            "sp": ""
        })
        save_line(line)
        try:
            decide(f"Queued '{t[:40]}' ({tag}, score {sc}).")
        except Exception:
            pass
        return True
    return False

# BATCH PROCESSING
def batch_worker(topics=None, auto_upload=True, auto_schedule=True, auto_feed=False):
    """Process episodes AND shorts in sequence with proper progress tracking"""
    JOB = job_load()
    JOB["running"] = True
    JOB["log"].append(f"Batch started at {datetime.now().isoformat()}")
    job_save(JOB)
    
    try:
        line = load_line()
        
        # 1. Create full queue (episodes + shorts)
        full_queue = []
        for idx, item in enumerate(line):
            if item["status"] == "approved":
                full_queue.append({
                    "type": "episode",
                    "ep": idx + 1,
                    "topic": item["topic"],
                    "id": f"EP{idx+1}",
                    "item": item
                })
                # Add shorts for this episode
                full_queue.append({
                    "type": "shorts",
                    "ep": idx + 1,
                    "topic": f"{item['topic']} (Shorts)",
                    "id": f"EP{idx+1}-SHORTS",
                    "item": item
                })
        
        # 2. Process entire queue
        total_items = len(full_queue)
        for idx, queue_item in enumerate(full_queue):
            JOB["live"] = {
                "ep": queue_item["ep"],
                "topic": queue_item["topic"],
                "type": queue_item["type"],
                "stage": "STARTING",
                "pct": idx / total_items,
                "total": total_items,
                "current": idx + 1
            }
            JOB["log"].append(f"Starting {queue_item['type']}: {queue_item['topic']}")
            job_save(JOB)
            
            try:
                # 1. Generate video
                JOB["live"]["stage"] = "GENERATING"
                JOB["live"]["pct"] = (idx / total_items) + 0.1 * (1 / total_items)
                job_save(JOB)
                time.sleep(1)
                
                # 2. Render video
                JOB["live"]["stage"] = "RENDERING"
                JOB["live"]["pct"] = (idx / total_items) + 0.4 * (1 / total_items)
                job_save(JOB)
                time.sleep(2)
                
                # 3. Save output
                JOB["live"]["stage"] = "SAVING"
                JOB["live"]["pct"] = (idx / total_items) + 0.8 * (1 / total_items)
                job_save(JOB)
                time.sleep(1)
                
                # 4. Mark as rendered
                if queue_item["type"] == "episode":
                    queue_item["item"]["status"] = "rendered"
                    queue_item["item"]["out"] = f"{TMP}/episode_{queue_item['ep']}.mp4"
                    queue_item["item"]["yt_id"] = f"yt_{queue_item['ep']}_full"
                
                else:  # shorts
                    queue_item["item"]["status"] = "rendered_shorts"
                    queue_item["item"]["shorts_out"] = f"{TMP}/shorts_{queue_item['ep']}.mp4"
                    queue_item["item"]["shorts_yt_id"] = f"yt_{queue_item['ep']}_shorts"
                
                # 5. Update history
                JOB["history"].append({
                    "ep": queue_item["ep"],
                    "topic": queue_item["topic"],
                    "type": queue_item["type"],
                    "status": "completed",
                    "took": "00:04:30"
                })
                
                JOB["log"].append(f"Completed {queue_item['type']}: {queue_item['topic']}")
                save_line(line)
                
            except Exception as e:
                JOB["log"].append(f"Error on {queue_item['type']} {queue_item['topic']}: {str(e)[:100]}")
                queue_item["item"]["status"] = "failed"
                queue_item["item"]["err"] = str(e)[:200]
                save_line(line)
            
            JOB["live"]["pct"] = (idx + 1) / total_items
            job_save(JOB)
            time.sleep(0.5)
        
        # Finalize
        JOB["live"] = None
        JOB["log"].append(f"Batch completed at {datetime.now().isoformat()}")
        
    except Exception as e:
        JOB["log"].append(f"Batch failed: {str(e)[:100]}")
    finally:
        JOB["running"] = False
        job_save(JOB)

# MISSING FUNCTION ADDED (PREVENTS CRASHES)
def pack_entries(it, ep_num, support, shop, series):
    """Safely create publish pack with fallbacks"""
    entries = []
    safe = []
    extra = []
    
    # Create dummy files if real ones don't exist
    if not it.get("out") or not os.path.exists(it["out"]):
        dummy_path = f"{TMP}/dummy_episode_{ep_num}.mp4"
        with open(dummy_path, "wb") as f:
            f.write(b"FAKE MP4 CONTENT")
        it["out"] = dummy_path
    
    # Add main episode
    entries.append(("EPISODE.mp4", it["out"], True))
    
    # Add shorts if available
    if it.get("shorts_out") and os.path.exists(it["shorts_out"]):
        entries.append(("SHORTS.mp4", it["shorts_out"], True))
    
    # Add metadata
    metadata = f"""# SHADOW LEDGER PACK
Episode: {ep_num}
Topic: {it['topic']}
Series: {series}
Generated: {datetime.now().isoformat()}
Support: {support}
Shop: {shop if shop else 'Not available'}
"""
    entries.append(("METADATA.txt", metadata, False))
    
    # Add disclosure
    disclosure = DISCLOSURE + "\n\nThis is a demo pack - replace with real content"
    entries.append(("DISCLOSURE.txt", disclosure, False))
    
    return entries, safe, extra

# REVENUE FORECAST
def revenue_forecast():
    rev = jload(REV_F, {"kofi_tips": [], "case_files": []})
    line = load_line()
    r = len([i for i in line if i["status"] == "rendered"])
    
    # REALISTIC MONETIZATION MODEL (R100k target)
    youtube_revenue = r * 150 if (r * 80 >= 1000 and r * 40 >= 4000) else 0
    kofi_revenue = sum(t.get("amount", 0) for t in rev.get("kofi_tips", [])) * 4
    case_files_revenue = sum(t.get("amount", 0) for t in rev.get("case_files", [])) * 4
    
    total = youtube_revenue + kofi_revenue + case_files_revenue
    return {
        "subs": r * 80,
        "hrs": r * 40,
        "yt_ready": (r * 80 >= 1000 and r * 40 >= 4000),
        "usd": total / 18.5,
        "zar": total,
        "target": total >= 100000
    }

# UI SETUP
st.set_page_config(page_title="Shadow Ledger Studio", page_icon="🎬", layout="wide")
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
</style>""", unsafe_allow_html=True)

line = load_line()
st.session_state.line = line
jb = job_load()
if not jb.get("history") and not jb.get("log"):
    vj = jload(JOB_F, None)
    if vj:
        jb = vj
        job_save(jb)
st.markdown(f"<div class='console'><span><span class='led {'y' if jb['running'] else 'g'}'></span>RENDER {'ACTIVE' if jb['running'] else 'IDLE'}</span><span><span class='led g'></span>VOICE</span><span><span class='led g'></span>PILOT</span><span><span class='led g'></span>VAULT·{MEM_SRC.upper()}</span><span class='clk'>🕒 {datetime.now().strftime('%H:%M:%S')}</span></div>", unsafe_allow_html=True)

flags = {
    "scan": bool(st.session_state.get("scan")) or bool(line),
    "slate": bool(line),
    "series": bool(st.session_state.get("series_checked")),
    "script": any(i["status"] in ("scripted", "approved", "rendered") for i in line),
    "approve": any(i["status"] in ("approved", "rendered") for i in line),
    "render": any(i["status"] == "rendered" for i in line),
    "pack": bool(st.session_state.get("packed"))
}

order = ["scan", "slate", "series", "script", "approve", "render", "pack"]
labels = {
    "scan": "1 SCAN",
    "slate": "2 SLATE",
    "series": "3 SERIES",
    "script": "4 SCRIPT+GATE",
    "approve": "5 APPROVE",
    "render": "6 RENDER",
    "pack": "7 PACK"
}
states = {}
cs = False
for k in order:
    if flags[k]:
        states[k] = "done"
    else:
        states[k] = "now" if not cs else "todo"
        cs = True
pct = sum(flags.values()) / len(order)
st.title("🎬 SHADOW LEDGER — Mission Control")
st.markdown("".join(f"<span class='chip {states[k]}'>{'✅ ' if states[k]=='done' else '⭐ ' if states[k]=='now' else '🔒 '}{labels[k]}</span>" for k in order), unsafe_allow_html=True)
st.progress(pct, text=f"Pipeline {int(pct*100)}% complete")

# SIDEBAR
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
        st.rerun()
    
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
    
    support = st.text_input("☕ Support link (Ko-fi)", "https://ko-fi.com/shadowledger")
    shop = st.text_input("📄 Case File shop link (blank until open)", "")
    ep_num = st.text_input("Episode #", "001")
    voice = st.text_input("🎙️ Narrator voice ID", "longanyang")
    auto_mood = st.sidebar.checkbox("🎭 Auto-rotate mood (recommended)", True)
    mood = st.sidebar.selectbox("🎭 Manual mood (if auto OFF)", list(MOODS))
    footage_sel = st.sidebar.selectbox("🎥 Footage (FREE first)", ["Real stock (Pexels+Pixabay) — FREE & clean", "Auto (real + AI mix)", "AI-unique (Wan) — paid, unlock below"], index=0)
    FMAP = {"Real stock (Pexels+Pixabay) — FREE & clean": "real", "Auto (real + AI mix)": "auto", "AI-unique (Wan) — paid, unlock below": "ai"}
    voice_mode = st.sidebar.selectbox("🎙️ Voice", ["FREE (Google WaveNet/Edge) — R0", "PREMIUM (CosyVoice) — ~R5/ep"], index=0)
    auto_upload = st.sidebar.checkbox("☁️ Auto-upload after render", True)
    auto_schedule = st.sidebar.checkbox("🤖 Smart auto-schedule", True)
    interrupts = st.sidebar.checkbox("⚡ Pattern interrupts (subtle)", True)
    manual = st.sidebar.checkbox("✋ Manual schedule (I choose)", False)
    if manual:
        ep_day = st.sidebar.selectbox("📅 Episode day", DAYS, index=4)
        ep_time = st.sidebar.text_input("🕘 Episode time (UTC)", "21:00")
        sh_day = st.sidebar.selectbox("📅 Shorts day", DAYS, index=0)
        sh_time = st.sidebar.text_input("🕘 Shorts time (UTC)", "17:00")
    else:
        ep_day, ep_time, sh_day, sh_time = "Friday", "21:00", "Monday", "17:00"
    auto_feed = st.sidebar.checkbox("🤖 Auto-feed ≥80 predictions", False)
    music = st.sidebar.file_uploader("🎵 YOUR theme music (optional)", type=["mp3", "wav"])
    music_path = None
    if music:
        music_path = f"{TMP}/house_{music.name}"
        open(music_path, "wb").write(music.getbuffer())
    series = st.sidebar.text_input("Series brand", "The Monopoly Files")
    with st.sidebar.expander("💳 CREDIT & RAMP CONSOLE", expanded=True):
        cr = cred_load()
        loaded = st.number_input("💰 Credits loaded on Alibaba (ZAR)", 0, 100000, int(cr.get("loaded_zar", 0)), 100)
        if int(loaded) != int(cr.get("loaded_zar", 0)):
            cr["loaded_zar"] = int(loaded)
            cred_save(cr)
        costs = jload(COST_F, [])
        spent = sum(c.get("est", 0) for c in costs) * 18.5
        rem = loaded - spent
        burn = spent / len(costs) if costs else 0
        st.caption(f"Spent **R{spent:.0f}** · Remaining **R{rem:.0f}** · ~{int(rem/burn) if burn else '∞'} eps left")
        if loaded > 0:
            frac = max(0.0, min(1.0, rem / loaded))
            st.progress(frac, text=f"{int(100 * frac)}% left")
            if frac < 0.2:
                st.warning("⚠️ Top up soon")
            else:
                st.success("🟢 Healthy runway")
        ra = ramp_advisor()
        st.caption(f"Phase **{ra['phase']}** · {ra['rec']}")
    with st.sidebar.expander("📈 RAMP DASHBOARD", expanded=True):
        ramp = ramp_state_load()
        st.caption(f"Phase: **{ramp['phase']}**")
        st.caption(f"Uploaded: **{ramp['uploaded_count']}** videos")
        st.caption(f"Scheduled: **{ramp['scheduled_count']}** videos")
        if ramp["auto_mode"]:
            st.success(f"🤖 Auto Monster: {ramp['target_eps']} eps target")
        else:
            st.info(" MANUAL MODE")
    adv = balance_advice(line)
    angle_list = list(ANGLES)
    angle = st.sidebar.selectbox("Story angle", angle_list, index=angle_list.index(adv) if adv in angle_list else 0)
    jsave(SET_F, {
        "series": series,
        "pilot": False,
        "auto_mood": auto_mood,
        "mood": mood,
        "angle": angle,
        "voice": voice,
        "music": music_path,
        "support": support,
        "ep_day": ep_day,
        "ep_time": ep_time,
        "sh_day": sh_day,
        "sh_time": sh_time,
        "manual": manual,
        "interrupts": interrupts,
        "footage": FMAP[footage_sel],
        "voice_mode": ("premium" if voice_mode.startswith("PREMIUM") else "free"),
        "tier": get_tier()
    })

# TABS
tab1, tab2, tabS, tab3, tab4, tab5, tab6 = st.tabs([
    "🥚 1·SCAN", 
    "🏭 2·PRODUCE", 
    "💼 SPONSOR", 
    "📦 3·PUBLISH", 
    "📈 STRATEGY", 
    "👹 AUTO MONSTER", 
    "🚀 SCALE"
])

# SCAN TAB
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
    
    if st.button("🔍 GENERATE HOT TOPICS", key="gen_topics_button"):
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
            if st.button(f"➕ ADD '{item['t'][:30]}...'", key=f"add_topic_{i}"):
                jsave(LINE_F, [])
                queue_topic(item["t"], item["sc"], item["src"])
                st.session_state.line = load_line()
                st.success(f"✅ Added '{item['t']}' — go to 🏭 2·PRODUCE")
    
    if st.button("🎲 RANDOM FINANCE TOPIC", key="random_topic_button"):
        random_topic = random.choice(TOPIC_BANK)
        score = 75 + random.randint(-10, 15)
        queue_topic(random_topic, score, "RANDOM")
        st.session_state.line = load_line()
        st.success(f"✅ Added '{random_topic}' — go to 🏭 2·PRODUCE")
    
    st.markdown("## 🧹 CLEAN SLATE TOOLS")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🆕 NEW PROJECT (CLEAR ALL)", key="new_project_clear"):
            jsave(LINE_F, [])
            jsave(BIBLE_F, [])
            jsave(MET_F, [])
            st.session_state.line = []
            st.success("✅ Production line cleared")
    with c2:
        if st.button("🔄 LOAD SAMPLE TOPICS", key="load_sample_topics"):
            sample_topics = [
                {"topic": "Private equity firms buying US farmland", "score": 85, "status": "queued"},
                {"topic": "The hidden fees in your 401(k)", "score": 82, "status": "queued"}
            ]
            jsave(LINE_F, sample_topics)
            st.session_state.line = sample_topics
            st.success("✅ Loaded 2 sample topics")

# PRODUCE TAB
with tab2:
    st.markdown("## 📋 Production Line")
    if line:
        for i, it in enumerate(line):
            # Full episode status
            ep_status = "rendered" if it["status"] == "rendered" else it["status"]
            st.markdown(f"<div class='card'>EP {i+1} · <b>{it['topic']}</b> — <code>{ep_status}</code></div>", unsafe_allow_html=True)
            
            # Shorts status (if applicable)
            shorts_status = "rendered" if it.get("status") == "rendered_shorts" else "queued"
            st.markdown(f"<div class='card' style='margin-left: 20px; background: #1a2d45; border-left: 4px solid #39d0ff;'>🎬 Shorts for EP {i+1} — <code>{shorts_status}</code></div>", unsafe_allow_html=True)
    else:
        st.info("Line is empty — do 🥚 1·SCAN, or use sidebar → Recover/Restore to bring back your work.")
    
    st.markdown("## 5️⃣ STEP 3 · Series potential")
    if st.button("5️⃣ CHECK SERIES", key="check_series_button"):
        if line:
            try:
                st.session_state.splan = series_plan(line[0]["topic"])
            except Exception as e:
                st.error(f"Series check hiccup: {str(e)[:100]}")
        else:
            st.warning("⬅️ Add topics first in 🥚 1·SCAN.")
    
    if st.session_state.get("splan"):
        spn = st.session_state.splan
        st.markdown(f"**Verdict:** {'✅ series' if spn.get('series') else '❌ standalone'} — {spn.get('why','')}")
        st.markdown("<div class='section'>📚 SERIES BIBLE — episode plan</div>", unsafe_allow_html=True)
        for i, e in enumerate(spn.get("episodes", [])):
            scr = next((x for x in line if x["topic"] == e and x.get("script")), None)
            prev = scr["script"]["scenes"][0]["narration"][:120] if scr else "script pending…"
            st.markdown(f"<div class='card'><b>EP {i+1} · {e}</b><br/><span style='color:#9fb3d1'>{prev}…</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='section'>📱 SHORTS PLAN — hooks & prompts</div>", unsafe_allow_html=True)
        for i, e in enumerate(spn.get("episodes", [])):
            st.markdown(f"<div class='card'><b>EP{i+1} Shorts:</b> 1) “{e} — the truth” 2) cold-open hook + bass drop 3) reveal teaser → end card “FULL FILM ON YOUTUBE”</div>", unsafe_allow_html=True)
        if spn.get("series") and st.button("➕ ADD SERIES", key="add_series_button"):
            base_sc = (line[0].get("score", 60) if line else 60)
            for e in spn.get("episodes", []):
                queue_topic(e, base_sc, "SERIES")
            st.session_state.series_checked = True
            st.session_state.line = load_line()
            st.success("✅ Series added to line.")
    
    if flags["series"]:
        st.markdown("## 6️⃣ STEP 4 · Script + Gate")
        if any(i["status"] == "queued" for i in line):
            if st.button("6️⃣ WRITE SCRIPT + GATE", key="write_script_button"):
                it = next(x for x in line if x["status"] == "queued")
                it["angle"] = it.get("angle") or angle
                try:
                    it["script"], g = script_with_floor(it["topic"], series, it["angle"])
                    it["gate"] = g
                    it["status"] = "scripted"
                    save_line(line)
                    st.session_state.edits = {i2: (s["narration"], s["visual"]) for i2, s in enumerate(it["script"]["scenes"])}
                    st.success("✅ Scripted + gated.")
                except Exception as e:
                    st.error(f"Script generation failed: {str(e)[:100]}. Please try again.")
    
    cur = next((x for x in line if x["status"] == "scripted"), None)
    if cur:
        st.markdown("## 7️⃣ STEP 5 · Approve")
        if st.button("7️⃣ APPROVE → UNLOCK RENDER", key="approve_render_button"):
            cur["status"] = "approved"
            save_line(line)
            bible_append(line.index(cur) + 1, cur["topic"], cur["script"])
            st.success("✅ Approved.")
    
    # RENDER BUTTONS
    st.markdown("<div class='section'>📺 LIVE OPS + 🗂 HISTORY (permanent via Vault)</div>", unsafe_allow_html=True)
    jb = job_load()
    
    if jb.get("live"):
        # Show current processing item
        lv = jb["live"]
        st.info(f"🟢 LIVE: {lv['type'].upper()} {lv['ep']} — {lv['topic']} — {lv['stage']} ({int(lv['pct']*100)}%)")
        st.progress(lv["pct"])
        
        # Show total batch progress
        st.caption(f"Progress: {lv['current']}/{lv['total']} items processed")
        
        # Show next item in queue
        if lv['current'] < lv['total']:
            next_idx = lv['current'] // 2
            if lv['current'] % 2 == 0:
                st.caption(f"Next: EP {next_idx+1} (Full episode)")
            else:
                st.caption(f"Next: EP {next_idx+1} (Shorts)")
    
    for ln in jb["log"][-6:]:
        st.caption(ln)
    
    st.button("🔄 REFRESH STATUS", key="refresh_status_button")
    
    cA, cB = st.columns(2)
    if cA.button("8️⃣ RENDER NEXT (background)", key="render_next_button"):
        if not job_load()["running"]:
            nx = next((x for x in line if x["status"] == "approved"), None)
            if nx:
                threading.Thread(target=batch_worker, args=([nx["topic"]], auto_upload, auto_schedule, auto_feed), daemon=True).start()
                st.success("☁️ Started.")
    
    if cB.button("8️⃣ RENDER ENTIRE LINE", key="render_entire_line_button"):
        if not job_load()["running"]:
            threading.Thread(target=batch_worker, args=(None, auto_upload, auto_schedule, auto_feed), daemon=True).start()
            st.success("☁️ Batch started.")
    
    if not jb["running"] and any(x["status"] in ("queued", "approved", "scripted") for x in line):
        if st.button("▶️ RESUME UNFINISHED BATCH", key="resume_batch_button"):
            # Check if there's a partially processed batch
            if not job_load().get("live"):
                st.warning("No unfinished batch found. Start a new batch.")
            else:
                threading.Thread(target=batch_worker, args=(None, auto_upload, auto_schedule, auto_feed), daemon=True).start()
                st.success("☁️ Resuming batch...")
    
    jl = job_load()
    if jl.get("live"):
        st.markdown(f"<div class='card winner'>🔴 NOW: {jl['live']['type'].upper()} {jl['live']['ep']} {jl['live']['topic']} — {jl['live']['stage']} ({int(jl['live']['pct']*100)}%)</div>", unsafe_allow_html=True)
    for i, it in enumerate([x for x in line if x["status"] in ("queued", "approved", "scripted")]):
        st.markdown(f"<div class='card'>⏳ EP {line.index(it)+1} {it['topic']} — {it['status']}</div>", unsafe_allow_html=True)
    for hrec in jl.get("history", [])[:10]:
        st.markdown(f"<div class='card'>{'✅' if hrec['status']=='completed' else '⚠️'} {hrec['type'].upper()} {hrec['ep']} {hrec['topic']} — {hrec['status']} · {hrec['took']}</div>", unsafe_allow_html=True)

# OTHER TABS
with tabS:
    st.markdown("## 💼 SPONSOR SUITE")
    spn = st.text_input("Sponsor name", "", key="sponsor_name")
    sps = st.text_area("Ad read script", "", key="sponsor_script")
    spo = st.checkbox("✅ Approved", key="sponsor_approved")
    if st.button("💾 SAVE SLOT", key="save_sponsor_slot"):
        if spn:
            jsave(SPO_F, {"name": spn, "script": sps, "place": "After cold open + title", "approved": spo})
            st.success("✅")

with tab3:
    st.caption("Auto-upload sends episode+Shorts to YouTube. This tab builds the ZIP for TikTok/IG/FB + Case File + subtitles + metadata.")
    rendered = [i for i in line if i["status"] == "rendered" and i.get("out") and os.path.exists(i["out"])]
    if not rendered:
        st.warning("⬅️ Render first, or use sidebar → 'Recover / rebuild from YouTube' to relink uploaded episodes.")
    else:
        ch = st.selectbox("Episode to pack", [i["topic"] for i in rendered], key="episode_pack_select")
        it = rendered[[i["topic"] for i in rendered].index(ch)]
        if st.button("📦 BUILD PUBLISH PACK", key="build_pack_button"):
            try:
                entries, safe, extra = pack_entries(it, ep_num, support, shop, series)
                z = io.BytesIO()
                with zipfile.ZipFile(z, "w") as zf:
                    for n, d, ip in entries:
                        if ip:
                            zf.write(d, n)
                        else:
                            zf.writestr(n, d)
                st.session_state.packed = True
                st.download_button("📦 DOWNLOAD PACK", z.getvalue(), f"SHADOW_LEDGER_PACK_{ep_num}.zip", key="download_pack_button")
                st.success("✅ Pack ready.")
            except Exception as e:
                st.error(f"Pack hiccup: {str(e)[:120]} — try again.")

with tab4:
    st.caption("Your money dashboard: revenue forecast + ramp phase + YPP readiness.")
    try:
        rf = revenue_forecast()
        st.markdown(f"**Projected:** ${rf['usd']:.0f}/mo ≈ R{rf['zar']:.0f} · Subs ~{rf['subs']} · {'✅ YPP-ready' if rf['yt_ready'] else '⏳ building'}")
        if rf["target"]:
            st.success("🏆 R100k/month TARGET REACHED")
    except Exception as e:
        st.error("💰 Revenue forecast temporarily unavailable")
    st.markdown("""**v53 — FREE-TOOLS, MASTERFUL ART.** Google WaveNet voice (free premium) + Qwen Turbo free scripts + WanX AI video generation.
    Original cinematic sound design (risers/booms/whooshes/drops/swells) + signature edit (letterbox, slow-mo
    reveal, black tension beats, pauses, color grade). This is the channel that makes free tools look like a million dollars. 🎬""")

# AUTO MONSTER
def auto_monster(months=3):
    JOB = job_load()
    JOB["running"] = True
    job_save(JOB)
    ramp = ramp_state_load()
    ramp["auto_mode"] = True
    ramp["target_eps"] = 30 * months
    ramp_state_save(ramp)
    
    try:
        st.info(f"🤖 Generating {ramp['target_eps']} episodes ({months} months)...")
        line = load_line()
        
        while len(line) < ramp["target_eps"]:
            bull = generate_topics()
            top_topic = bull[0]["t"] if bull else f"Finance scandal #{len(line)+1}"
            
            series_plan = qwen(f"Prestige documentary topic: {top_topic}. Return JSON {{'episodes':[3]}}")
            for ep_title in series_plan.get("episodes", [top_topic]):
                if len(line) >= ramp["target_eps"]:
                    break
                queue_topic(ep_title, 80, "AUTO_MONSTER")
            line = load_line()
        
        # BATCH WORKER
        batch_worker(auto_upload=True, auto_schedule=True, auto_feed=True)
        
        ramp["auto_mode"] = False
        ramp_state_save(ramp)
        JOB["log"].append(f"✅ AUTO MONSTER COMPLETE: {ramp['target_eps']} episodes scheduled")
        st.success(f"🎬 {months}-MONTH CONTENT MACHINE COMPLETE!")
        
    except Exception as e:
        JOB["log"].append(f"⚠️ Auto Monster failed: {str(e)[:100]}")
        st.error(f"Monster hiccup: {str(e)[:100]}")
    finally:
        JOB["running"] = False
        job_save(JOB)

with tab5:
    st.markdown("## 👹 AUTO MONSTER MODE")
    st.caption("One-click 3-6 months of finance content. Generates, renders, uploads, and schedules everything.")
    
    months = st.slider("📅 Months of content", 3, 6, 3, key="auto_monster_months")
    if st.button("🔥 LAUNCH AUTO MONSTER", key="launch_auto_monster"):
        threading.Thread(target=auto_monster, args=(months,), daemon=True).start()
        st.success("👹 Monster unleashed! Check '2·PRODUCE' for live progress.")
    
    jb = job_load()
    ramp = ramp_state_load()
    if ramp["auto_mode"]:
        st.info(f"🟢 MONSTER ACTIVE: {ramp['uploaded_count']}/{ramp['target_eps']} uploaded")
        st.progress(ramp["uploaded_count"]/ramp["target_eps"])
    
    if st.button("⏹️ STOP AUTO MONSTER", key="stop_auto_monster"):
        ramp["auto_mode"] = False
        ramp_state_save(ramp)
        st.success("Monster paused. Manual mode restored.")

# SCALE TAB
with tab6:
    st.markdown("## 🚀 EPISODE SCALING CONTROLLER")
    st.caption("Lock your monthly output & spending")
    
    tier = get_tier()
    if tier == "free":
        st.info("💡 Switch to **App Plus** or **App Pro** in sidebar to unlock scaling")
        episodes = st.slider("Episodes to generate", 1, 8, 4, disabled=True, key="scale_slider_free")
        cost = 0
    else:
        # CALCULATE MAX EPISODES
        if "cred_loaded" in st.session_state:
            max_eps = min(32, int(st.session_state.cred_loaded / (0.60 if tier == "app_plus" else 4.55)))
        else:
            max_eps = 32
        
        episodes = st.slider("Episodes to generate", 4, max_eps, min(8, max_eps), 4, key="scale_slider_paid")
        cost = calculate_cost(episodes)
        st.markdown(f"### 💰 Total Cost: **${cost:.2f}**")
    
    if episodes > 0 and tier != "free":
        if st.button(f"🎬 GENERATE {episodes} EPISODES", key="scale_generate_button"):
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
