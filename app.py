import streamlit as st, requests, json, os, io, re, zipfile, hashlib, textwrap
from datetime import datetime, timedelta
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import dashscope
from dashscope import VideoSynthesis, ImageSynthesis
from dashscope.audio.tts_v2 import SpeechSynthesizer
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip
from moviepy.audio.AudioClip import AudioClip, CompositeAudioClip, AudioArrayClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
import moviepy.video.fx as vfx

# ---------------- CONFIG ----------------
DASH, YT, PEX = st.secrets["DASHSCOPE_API_KEY"], st.secrets["YOUTUBE_API_KEY"], st.secrets["PEXELS_API_KEY"]
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
GOLD, BLACK = (212,175,55), (5,6,8)
TMP = "/tmp"
FONT = next((p for p in ["assets/Cinzel-Bold.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"] if os.path.exists(p)), None)
def F(sz): return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default(sz)
def slug(t): return re.sub(r'[^a-z0-9]+','_', t.lower()).strip('_')[:40]
MOODS = {
 "Calm investigator (default)": "low, calm, intimate documentary voice, slow deliberate pace, slightly breathy, grave tension, long pause before every reveal",
 "Concerned witness": "worried, urgent, leaning in, slightly trembling with concern, as if warning a friend",
 "Grave elegy": "mournful, heavy, slow, deep pauses, the voice of a eulogy for something that should never have happened",
 "Cold expose": "clinical, sharp, controlled anger, precise diction, ice-cold delivery",
 "Hushed suspense": "near-whisper, tense, every word a secret, long silences",
 "Hopeful storyteller": "warm, admiring, quietly triumphant, a smile in the voice, still slow and cinematic",
}
ANGLES = {
 "Dark expose (default)": "Tone: dark investigative expose. Dopamine via outrage, justice, revelation.",
 "Mystery / curiosity": "Tone: puzzle-box mystery. Dopamine via curiosity loops and the final click of understanding.",
 "David vs Goliath": "Tone: underdog versus a financial giant. Dopamine via fairness and clever resistance.",
 "Comeback / positive": "Tone: triumphant human comeback inside finance. NOT a forced happy ending — earned, bittersweet, still leaves an open question.",
}
TONE_LABEL = {"Dark expose (default)":"A DARK EXPOSE","Mystery / curiosity":"A MYSTERY","David vs Goliath":"AN UNDERDOG STORY","Comeback / positive":"A COMEBACK"}
LINE_F = f"{TMP}/shadow_line.json"
def load_line():
    try:
        if os.path.exists(LINE_F): return json.load(open(LINE_F))
    except Exception: pass
    return []
def save_line(l):
    try: json.dump(l, open(LINE_F,"w"))
    except Exception: pass
if "line" not in st.session_state: st.session_state.line = load_line()
if "edits" not in st.session_state: st.session_state.edits = {}

# ---------------- HOUSE DNA ----------------
DNA = """You are showrunner of SHADOW LEDGER, a prestige financial documentary series.
Topic: {topic}. Series: {series}. ANGLE: {angle}
STRUCTURE:
1. COLD OPEN + VIEWER STAKES: One human moment. MUST state how this affects the viewer's daily life, wallet or future in the first 15 seconds.
2. ACT I THE SUSPECT/PROTAGONIST: face, quote, defining moment.
3. ACT II THE MACHINE: stakes escalate; NEW open loop every 90s.
4. ACT III THE REVEAL: twist; numbers translated to human scale.
5. THE OPEN QUESTION: no neat bow, no preaching. Present facts, step back, ask a haunting question for the audience to decide in the comments. Then ONE in-brand CTA + a BINGE-PITCH teasing the next investigation.
RULES: present tense, short cinematic sentences. NO ACCUSATIONS; use 'alleged', 'according to documents', 'regulators claim'; frame controversy as questions; let the audience be the jury. Retention DNA in EVERY angle: open loops, pattern interrupts, concrete specifics.
ANTI-SLOP: BANNED: delve, tapestry, landscape, game-changer, uncover the truth. EVERY scene needs a concrete detail (number, date, place). Max 3 sentences per scene.
OUTPUT JSON: {{"title_options":[3], "hook_words":"MAX 4 WORDS", "share_line":"max 10 words, quotable, makes a viewer send this video to a friend", "scenes":[{{"narration":"", "visual":"", "ost":""}}], "pinned_question":"", "binge_pitch":"", "community_poll":{{"q":"","a":["",""]}}}}"""

GATE = """You are SHADOW LEDGER's ruthless executive editor, media-legal reviewer AND YouTube policy compliance officer.
Topic: {topic}. Review this script JSON: {script}
FIX: (1) AI-slop -> concrete specifics; (2) legal/bias -> remove accusations, frame as questions, 'alleged/documents show';
(3) viewer stakes -> cold open must connect to the viewer's life; (4) dragging -> max 3 sentences; (5) clickbait -> title promise delivered;
(6) shareability -> share_line quotable and human;
(7) YOUTUBE ADVERTISER-FRIENDLY POLICY: no profanity, no graphic descriptions, sensitive events framed factually; rewrite any narration/ost words that trigger limited ads;
(8) advisory: if themes warrant, ONE professional viewer advisory (max 14 words, Netflix-style), else "".
Return JSON {{"slop_clean":0-100,"emotion":0-100,"viewer_stakes":"clear|added","legal_flags_fixed":N,"yt_policy":"clean|fixed",
"clickbait":"clear|fixed","advisory":"","pacing":"one line note","scenes":[polished scenes same schema],
"title_options":[polished, <60 chars],"share_line":"polished max 10 words"}}"""

def qwen(prompt, sys=None):
    m = ([{"role":"system","content":sys}] if sys else []) + [{"role":"user","content":prompt}]
    r = requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers={"Authorization": f"Bearer {DASH}"},
        json={"model":"qwen-plus","messages":m,"response_format":{"type":"json_object"}}).json()
    return json.loads(r["choices"][0]["message"]["content"])

def wan_video_prompt(v): return (f"{v}. cinematic documentary film still, anamorphic 2.39:1, "
    "35mm grain, low-key chiaroscuro, crushed blacks, gold practicals, teal shadows, slow dolly, no text, no watermark")

# ---------------- GENERATORS ----------------
def speak(text, voice, mood):
    try: return SpeechSynthesizer(model="cosyvoice-v2", voice=voice, instruction=MOODS[mood]).call(text)
    except Exception: return SpeechSynthesizer(model="cosyvoice-v2", voice=voice).call(text)
def wan_video(prompt):
    r = VideoSynthesis.wait(VideoSynthesis.async_call(model="wan2.1-t2v-turbo", prompt=prompt, size="1280*720"))
    return r.output.video_url
def wan_images(prompt, n=2):
    r = ImageSynthesis.call(model="wanx2.1-t2i-turbo", prompt=prompt, n=n, size="1280*720")
    return [x["url"] for x in r.output.results]
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
    recent = [i.get("angle") or "Dark expose (default)" for i in line if i["status"] in ("rendered","approved","scripted","queued")][-3:]
    if len(recent) < 2: return None
    dark = sum(1 for a in recent if a=="Dark expose (default)")
    if dark >= 2: return "Mystery / curiosity"
    if len(recent) >= 3 and not any(a=="Comeback / positive" for a in recent): return "Comeback / positive"
    if dark == 0: return "Dark expose (default)"
    return None
def ad_draft(name, note):
    return qwen(f"Write a 20-30 second YouTube mid-roll ad read for sponsor '{name}'. About them: {note}. "
        f"House style: calm investigator voice, NO hype, NO false or superlative claims, factual benefits only. "
        f"Start with 'This segment is sponsored by {name}.' End with ONE dry, clever line tying back to following the money. "
        f"Return JSON {{'script':'...'}}")
def dossier(topic, sc):
    return qwen(f"Topic: {topic}. Script JSON: {json.dumps(sc)[:3000]}. Produce a premium 'Case File' dossier JSON: "
        "{{'timeline':[6-8 items 'YYYY-MM — event (publicly documented)'], 'key_players':[4-6 'name — role'], "
        "'follow_the_money':[4-6 'number — what it means in human terms'], 'glossary':[4-6 'term — plain-English definition'], "
        "'discussion':[3 questions]}}")

# ---------------- YOUTUBE RESEARCH ----------------
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
def trend_radar(seed):
    sug = requests.get("https://suggestqueries.google.com/complete/search", params={"client":"youtube","q":seed}).json()[1]
    wk = yt("search", part="snippet", q=seed, type="video", order="viewCount", publishedAfter=(datetime.utcnow()-timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"), maxResults=5)
    vel = [f"{i['snippet']['title'][:40]}…" for i in wk.get("items",[])]
    return [s[0] if isinstance(s,list) else s for s in sug], vel
def series_plan(topic):
    return qwen(f"Prestige documentary topic: {topic}. Decide if it supports a 2-3 episode series WITHOUT dragging. Return JSON {{'series':true/false,'why':'one line','episodes':[2-3 distinct titles]}}")

TRIGGERS = {"scam":"alleged fraud","scammer":"alleged fraudster","kill":"fatality","murder":"fatality","suicide":"tragic death","terrorist":"extremist","cartel":"syndicate","rape":"assault","steal":"misappropriate"}
def adsense_scrub(text):
    for bad, good in TRIGGERS.items():
        text = re.sub(rf'\b{bad}\b', good, text, flags=re.IGNORECASE)
    return text

# ---------------- PIL CARDS + CASE FILE PDF ----------------
def card_img(title, sub="", w=1280, h=720, transparent=False):
    img = Image.new("RGBA" if transparent else "RGB", (w,h), (0,0,0,0) if transparent else BLACK)
    d = ImageDraw.Draw(img)
    if not transparent: d.rectangle([0,h//2-90,w,h//2+90], fill=(8,9,12))
    d.text((w//2, h//2-30), title, font=F(64), fill=GOLD, anchor="mm")
    if sub: d.text((w//2, h//2+50), sub, font=F(30), fill=(220,220,220), anchor="mm")
    d.rectangle([w//2-260, h//2+95, w//2+260, h//2+98], fill=GOLD)
    return np.array(img)
def ost_img(text):
    img = Image.new("RGBA",(1280,160),(0,0,0,0)); d = ImageDraw.Draw(img)
    d.text((640,80), text.upper(), font=F(72), fill=GOLD, anchor="mm", stroke_width=5, stroke_fill=(0,0,0))
    return np.array(img)
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
    section("KEY PLAYERS", dos.get("key_players",[]))
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

# ---------------- PROCEDURAL SOUND DESIGN ----------------
SR = 22050
def sound_bed(dur, markers):
    n = int(dur*SR); t = np.arange(n)/SR
    bed = 0.10*np.sin(2*np.pi*52*t)*(0.6+0.4*np.sin(2*np.pi*0.11*t)) + 0.05*np.sin(2*np.pi*78*t+1.3)
    rng = np.random.default_rng(7)
    noise = np.convolve(rng.standard_normal(n), np.ones(40)/40, mode="same")
    for m in markers:
        s, e = max(0,int((m-3)*SR)), int(m*SR)
        if e > s:
            seg = np.arange(e-s)/(e-s); bed[s:e] += noise[s:e]*0.12*seg**2
        s, e = int(m*SR), min(n, int((m+1.6)*SR)); tt = np.arange(e-s)/SR
        bed[s:e] += 0.35*np.sin(2*np.pi*45*tt)*np.exp(-3*tt)
    step = int(1.4*SR); tk = int(0.03*SR)
    tt = np.arange(tk)/SR; tick = 0.05*np.sin(2*np.pi*1800*tt)*np.exp(-80*tt)
    for s in range(0, n-tk, step): bed[s:s+tk] += tick
    bed = bed/np.max(np.abs(bed))*0.5
    return AudioArrayClip(np.stack([bed,bed],axis=1), fps=SR)

# ---------------- SCRIPT + GATE + RENDER ----------------
def write_script(topic, series, angle):
    return qwen(DNA.format(topic=topic, series=series, angle=ANGLES[angle]))
def quality_gate(topic, sc):
    return qwen(GATE.format(topic=topic, script=json.dumps(sc)))
def apply_gate(sc, g):
    if g.get("scenes"):
        for s in g["scenes"]:
            s["narration"] = adsense_scrub(s["narration"]); s["ost"] = adsense_scrub(s.get("ost",""))
        sc["scenes"] = g["scenes"]
    if g.get("title_options"): sc["title_options"] = g["title_options"]
    if g.get("share_line"): sc["share_line"] = g["share_line"]
    sc["advisory"] = g.get("advisory","")
    return sc

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

def render(sc, topic, series, pilot, music, voice, mood, sp=None, prog=None, angle="Dark expose (default)"):
    def P(p, t):
        if prog: prog(min(p,1.0), t)
    scenes = sc["scenes"][:4] if pilot else sc["scenes"]
    parts = []; n = len(scenes)
    for i, s in enumerate(scenes):
        P(0.05+0.65*i/n, f"🎙️ Voicing + 🎥 filming scene {i+1}/{n}…")
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
    P(0.75, "🎞️ Cutting cold open → title → acts…")
    title = (ImageClip(card_img("SHADOW LEDGER", f"{series} · {TONE_LABEL.get(angle,'A DARK EXPOSE')}")).with_duration(3), silence(3), None)
    adv = sc.get("advisory") or ""
    advclip = (ImageClip(card_img("VIEWER NOTE", adv)).with_duration(3), silence(3), None) if adv else None
    end   = (ImageClip(card_img("SUBSCRIBE", sc.get("share_line") or "the next ledger opens soon")).with_duration(5), silence(5), None)
    base = [parts[0], title] + ([advclip] if advclip else []) + parts[1:]
    if sp and sp.get("name") and sp.get("approved"):
        idx = 2 if sp.get("place","").startswith("After") else max(2, len(base)-1)
        base = base[:idx] + sponsor_blocks(sp, voice, mood) + base[idx:]
    order = base + [end]
    vids, auds, srt, markers, t = [], [], [], [], 0.0
    for vc, ac, txt in order:
        vids.append(vc.with_audio(ac)); auds.append(ac)
        if txt: markers.append(t); srt.append((t, t+ac.duration, txt))
        t += ac.duration
    vid = concatenate_videoclips(vids)
    aud = concatenate_videoclips(auds)
    layers_a = [aud]
    if music:
        mc = AudioFileClip(music); nn2 = int(vid.duration//mc.duration)+1
        layers_a.append(concatenate_videoclips([mc]*nn2).with_duration(vid.duration).with_volume_scaled(0.10))
    markers.append(vid.duration*0.68)
    layers_a.append(sound_bed(vid.duration, markers).with_volume_scaled(0.6))
    P(0.85, "🎵 Scoring tension bed + branding…")
    final = vid.with_audio(CompositeAudioClip(layers_a).with_duration(vid.duration))
    layers = [final]
    if os.path.exists(f"{TMP}/bug.png"):
        layers.append(ImageClip(f"{TMP}/bug.png").resized(height=64).with_position((28,28)).with_duration(final.duration))
    layers.append(ImageClip(card_img("IF YOU FOLLOW THE MONEY,","subscribe - new investigations weekly",transparent=True))
                  .with_duration(5).with_start(final.duration*0.68).with_position((76,540))
                  .with_effects([vfx.FadeIn(0.6), vfx.FadeOut(0.8)]))
    final = CompositeVideoClip(layers)
    out = f"{TMP}/episode_{hashlib.md5(topic.encode()).hexdigest()}.mp4"
    final.write_videofile(out, codec="libx264", audio_codec="aac", fps=24, logger=None)
    P(1.0, "✅ Episode complete")
    return out, srt

def shorts_cut(video_path):
    c = VideoFileClip(video_path).subclipped(3, min(38, VideoFileClip(video_path).duration-6))
    c = c.resized(height=1920); w = c.size[0]
    return c.cropped(x1=(w-1080)//2, x2=(w-1080)//2+1080).with_fps(24)
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
[ ] Thumbnail: upload THUMB_A file (test B later via A/B tool)
[ ] PHASE 2: upload the CASE_FILE pdf to Ko-fi Shop using kofi_product_*.txt listing (already prepared)
"""
RIGHTS = """RIGHTS RECORD — SHADOW LEDGER
Footage: Pexels-licensed stock video + original AI-generated clips (Wan2.1, Alibaba Model Studio).
Voice: CosyVoice v2 via licensed API. Music: ORIGINAL procedural score (synthesized in-studio, zero third-party rights).
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

# ---------------- UI (MISSION CONTROL v16 FINAL) ----------------
st.set_page_config(page_title="Shadow Ledger Studio", page_icon="🎬", layout="wide")
st.markdown("""<style>
 .stApp{background:#0b0e13}
 h1,h2,h3{color:#e8c766 !important;font-family:Georgia,serif}
 div.stButton>button{background:linear-gradient(135deg,#1a1f2b,#10141c);color:#e8c766;border:1px solid #e8c76655;border-radius:12px;font-weight:700;padding:.5rem 1.1rem;transition:.2s}
 div.stButton>button:hover{border-color:#e8c766;box-shadow:0 0 18px #e8c76633;color:#fff}
 div[data-testid="stCheckbox"] label span{color:#dfe6f2;font-size:1.05rem}
 .chip{display:inline-block;padding:.25rem .7rem;border-radius:999px;margin:0 .3rem .3rem 0;font-size:.85rem;border:1px solid #333}
 .chip.done{background:#123524;color:#7ee2a8;border-color:#1d5c3a}
 .chip.now{background:#3a2f14;color:#e8c766;border-color:#8a6d2f;box-shadow:0 0 10px #e8c76622}
 .chip.todo{background:#141821;color:#7a8394}
 .card{background:#12161f;border:1px solid #232a38;border-radius:14px;padding:.7rem 1rem;margin:.5rem 0;color:#dfe6f2}
</style>""", unsafe_allow_html=True)

line = st.session_state.line
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
st.markdown("".join(f"<span class='chip {states[k]}'>{labels[k]}</span>" for k in order), unsafe_allow_html=True)
st.progress(pct, text=f"Pipeline {int(pct*100)}% complete")

support = st.sidebar.text_input("☕ Support link (Ko-fi)", "https://ko-fi.com/shadowledger")
shop = st.sidebar.text_input("📄 Case File shop link (Phase 2 — leave blank for now)", "")
ep_num = st.sidebar.text_input("Episode # (auto-names PDF/thumbs)", "001")
voice = st.sidebar.text_input("Narrator voice (CosyVoice v2 ID)", "longanyang")
mood = st.sidebar.selectbox("Narration mood", list(MOODS))
if st.sidebar.button("🔊 Hear 10s voice audition"):
    ab = f"{TMP}/audition.mp3"
    open(ab,"wb").write(speak("In 2019, a single signature moved forty-one billion dollars. Nobody noticed. Until now.", voice, mood))
    st.sidebar.audio(ab)
music = st.sidebar.file_uploader("House score (optional)", type=["mp3","wav"])
series = st.sidebar.text_input("Series brand", "The Monopoly Files")
adv = balance_advice(line)
angle_list = list(ANGLES)
angle = st.sidebar.selectbox("Story angle", angle_list, index=angle_list.index(adv) if adv in angle_list else 0)
if adv: st.sidebar.info(f"🎨 Slate Balance Advisor: next flavor → **{adv}**")
pilot = st.sidebar.checkbox("PILOT MODE (60-90s test)", True)
tab1,tab2,tabS,tab3,tab4 = st.tabs(["🥚 1·SCAN","🏭 2·PRODUCE","💼 SPONSOR SUITE","📦 3·PUBLISH","📈 Strategy"])

with tab1:
    if flags["scan"]: st.success("✅ STEP 1 complete. ➡️ NEXT: open 🏭 2·PRODUCE and tick your slate.")
    seeds = st.text_area("Seed topics (mix dark + positive, 5-8)", "BlackRock buying housing\nTicketmaster Live Nation monopoly\nThe janitor who left $6 million to his hospital\nHow Norway became the world's landlord\nThe teacher who out-traded Wall Street\nBoeing whistleblowers")
    if st.button("🥚 STEP 1 · Run Golden Egg scan"):
        results = []
        for s in [x for x in seeds.splitlines() if x.strip()]:
            score, why = golden_egg(s.strip())
            results.append((s.strip(), score, why))
        st.session_state.scan = sorted(results, key=lambda r: -r[1])
    if st.session_state.get("scan"):
        for j,(t, sc, w) in enumerate(st.session_state.scan):
            style = "border-color:#e8c766" if j==0 else ""
            pre = "🏆 " if j==0 else ""
            st.markdown(f"<div class='card' style='{style}'>{pre}<b>{t}</b> — 🥚 {sc}/100 · {w}</div>", unsafe_allow_html=True)
        st.caption("🏆 = winner (pre-ticked in PRODUCE). ➡️ Go to 🏭 2·PRODUCE.")
    with st.expander("📡 Trend Radar (optional extra intel)"):
        if st.button("Run Trend Radar"):
            for s in [x for x in seeds.splitlines() if x.strip()][:2]:
                sug, vel = trend_radar(s.strip())
                st.markdown(f"**{s}** → autocomplete: {', '.join(sug[:5])} · hot this week: {vel[:3]}")

with tab2:
    if not flags["scan"]:
        st.warning("⬅️ STEP 1 first: run the Golden Egg scan in 🥚 1·SCAN.")
    else:
        st.markdown("## STEP 2 · Tick your slate")
        st.caption("Tick every topic you want queued. The 🏆 winner is pre-ticked.")
        picks = []
        for j,(t, sc, w) in enumerate(st.session_state.scan):
            if st.checkbox(f"{t}  (🥚 {sc}/100)", value=(j==0), key=f"ck_{t}"): picks.append((t, sc))
        if st.button("➕ STEP 2 · Add ticked topics to Production Line"):
            for t, sc in picks:
                if not any(i["topic"]==t for i in line):
                    line.append({"topic":t,"score":sc,"tag":"","status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":""})
            save_line(line)
            st.success("✅ Slate locked. ➡️ NEXT: STEP 3 series check appeared below.")
        with st.expander("➕ Add a custom topic instead"):
            custom = st.text_input("Custom topic", "")
            if custom.strip() and st.button("Add custom topic"):
                line.append({"topic":custom.strip(),"score":0,"tag":"CUSTOM","status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":""})
                save_line(line)
        if flags["slate"]:
            st.markdown("## 📋 Your Production Line")
            for i, it in enumerate(line):
                st.markdown(f"<div class='card'>EP {i+1} · <b>{it['topic']}</b> {('['+it['tag']+']' if it['tag'] else '')} · {TONE_LABEL.get(it.get('angle') or 'Dark expose (default)','')} {('· 💼 '+it['sp']) if it.get('sp') else ''} — <code>{it['status']}</code></div>", unsafe_allow_html=True)
            st.markdown("## STEP 3 · Series potential")
            c1, c2 = st.columns(2)
            if c1.button("🎭 STEP 3 · Check series potential"):
                st.session_state.splan = series_plan(line[0]["topic"])
            if c2.button("⏭️ Standalone episode — skip series"):
                st.session_state.series_checked = True; st.session_state.splan = None
            if st.session_state.get("splan"):
                spn = st.session_state.splan
                st.markdown(f"**Verdict:** {'✅ YES — a series!' if spn['series'] else '❌ standalone is stronger'} — {spn['why']}")
                for e in spn.get("episodes",[]): st.markdown(f"• {e}")
                if spn["series"] and st.button("➕ Add series episodes to line"):
                    for e in spn.get("episodes",[]):
                        if not any(i["topic"]==e for i in line):
                            line.append({"topic":e,"score":line[0]["score"],"tag":"SERIES","status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":"","angle":None,"sp":""})
                    save_line(line)
                    st.session_state.series_checked = True
                    st.success("✅ Series added. ➡️ NEXT: STEP 4 below.")
        if flags["series"]:
            st.markdown("## STEP 4 · Script + 🛡️ Quality Gate + 🚨 YouTube Guard")
            if any(i["status"]=="queued" for i in line):
                if st.button("📜 STEP 4 · Write script + run Quality Gate"):
                    it = next(x for x in line if x["status"]=="queued")
                    bar = st.progress(0.2, text="✍️ Writing Netflix-DNA script…")
                    it["angle"] = angle
                    it["script"] = write_script(it["topic"], series, angle)
                    bar.progress(0.6, text="🛡️ Gate + 🚨 YouTube policy review…")
                    try:
                        g = quality_gate(it["topic"], it["script"])
                        it["script"] = apply_gate(it["script"], g)
                        it["gate"] = g
                    except Exception as e:
                        it["gate"] = {"pacing": f"gate skipped: {str(e)[:80]}"}
                    it["status"] = "scripted"; save_line(line)
                    st.session_state.edits = {i2:(s["narration"],s["visual"]) for i2,s in enumerate(it["script"]["scenes"])}
                    bar.progress(1.0, text="✅ Script + Gate complete")
                    st.success("✅ STEP 4 complete. ➡️ NEXT: review & APPROVE below.")
        cur = next((x for x in line if x["status"]=="scripted"), None)
        if cur:
            st.markdown("## STEP 5 · Review & Approve (Director's Cut)")
            if cur.get("gate"):
                g = cur["gate"]
                st.markdown(f"<div class='card' style='border-color:#7ee2a8'>🛡️ slop-clean <b>{g.get('slop_clean','-')}/100</b> · emotion <b>{g.get('emotion','-')}/100</b> · viewer stakes <b>{g.get('viewer_stakes','-')}</b> · legal flags fixed <b>{g.get('legal_flags_fixed','-')}</b> · 🚨 yt-policy <b>{g.get('yt_policy','-')}</b> · clickbait <b>{g.get('clickbait','-')}</b> · {g.get('pacing','-')}</div>", unsafe_allow_html=True)
                if cur["script"].get("advisory"):
                    st.caption(f"🎬 Viewer advisory (auto): “{cur['script']['advisory']}”")
            for i2, s in enumerate(cur["script"]["scenes"]):
                nar, vis = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                nn = st.text_area(f"Narration {i2+1}", nar, key=f"n_{i2}", height=90)
                vv = st.text_input(f"Visual {i2+1}", vis, key=f"v_{i2}")
                st.session_state.edits[i2] = (nn, vv)
            if st.button("🛡️ Re-run Gate on my edits"):
                for i2, s in enumerate(cur["script"]["scenes"]):
                    nn, vv = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                    s["narration"], s["visual"] = nn, vv
                g = quality_gate(cur["topic"], cur["script"])
                cur["script"] = apply_gate(cur["script"], g)
                cur["gate"] = g; save_line(line)
                st.session_state.edits = {i2:(s["narration"],s["visual"]) for i2,s in enumerate(cur["script"]["scenes"])}
            if st.button("✅ STEP 5 · Approve script → unlock Render"):
                for i2, s in enumerate(cur["script"]["scenes"]):
                    nn, vv = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                    s["narration"], s["visual"] = nn, vv
                cur["status"] = "approved"; save_line(line)
                st.success("✅ Approved. ➡️ NEXT: optional 💼 SPONSOR SUITE, then STEP 6 Render.")
        if flags["approve"]:
            st.markdown("## STEP 6 · Render (live progress bar)")
            itn = next((x for x in line if x["status"]=="approved"), None)
            if itn and itn.get("script"):
                secs, cost = estimate(itn["script"], pilot)
                st.caption(f"⏱️ Est. runtime ~{secs}s · 💰 est. cost ~${cost:.2f} (free quota first) · 🏷️ {TONE_LABEL.get(itn.get('angle') or 'Dark expose (default)','')}")
            if st.button("🎬 STEP 6 · Render episode"):
                it = next((x for x in line if x["status"]=="approved"), None)
                if it:
                    bar = st.progress(0.05, text="🚀 Starting render…")
                    try:
                        mp3 = None
                        if music:
                            mp3 = f"{TMP}/house_{music.name}"; open(mp3,"wb").write(music.getbuffer())
                        sp = st.session_state.get("sponsor")
                        it["sp"] = sp["name"] if (sp and sp.get("approved")) else ""
                        out, srt = render(it["script"], it["topic"], series, pilot, mp3, voice, mood, sp, prog=bar.progress, angle=it.get("angle") or "Dark expose (default)")
                        it["out"], it["srt"], it["status"], it["err"] = out, srt, "rendered", ""
                        save_line(line)
                        st.video(out)
                        st.download_button("⬇️ Download this episode", open(out,"rb").read(), f"EPISODE_{ep_num}_{slug(it['topic'])}.mp4")
                        st.success("✅ STEP 6 complete. ➡️ NEXT: 📦 3·PUBLISH tab.")
                    except Exception as e:
                        it["status"], it["err"] = "failed", str(e)[:150]; save_line(line)
                        st.error(f"Render failed (line saved — press Render to retry): {e}")
    st.download_button("💾 Backup production line", json.dumps(line).encode(), "shadow_line.json")
    up = st.file_uploader("Restore backup", type=["json"])
    if up: st.session_state.line = json.load(up); save_line(st.session_state.line)

with tabS:
    st.markdown("## 💼 SPONSOR SUITE — brand deals, woven in seamlessly")
    if st.session_state.get("sponsor"):
        spc = st.session_state.sponsor
        st.success(f"Active slot: **{spc['name']}** · {spc['place']} · {'✅ approved' if spc['approved'] else '⏳ awaiting sponsor approval'}")
        if st.button("🗑️ Clear sponsor slot"):
            st.session_state.sponsor = None
    sp_name = st.text_input("Sponsor name", "")
    sp_note = st.text_area("What does the sponsor do? (one line — Qwen uses this)", "")
    if st.button("✍️ Qwen draft the ad read (20-30s, brand-safe)"):
        if sp_name.strip():
            st.session_state.ad_draft = ad_draft(sp_name.strip(), sp_note)["script"]
    sp_script = st.text_area("Ad read script (editable — send to sponsor for approval)", st.session_state.get("ad_draft",""))
    sp_video = st.file_uploader("Sponsor video (optional)", type=["mp4","mov","webm"])
    sp_image = st.file_uploader("Sponsor image/poster (optional — auto-cropped + gold lower-third)", type=["png","jpg","jpeg"])
    if st.button("🔊 Audition ad read"):
        if sp_script.strip():
            ap = f"{TMP}/ad_audition.mp3"; open(ap,"wb").write(speak(sp_script, voice, mood))
            st.audio(ap)
    sp_place = st.selectbox("Placement", ["After cold open + title (TV style)", "Before the final reveal"])
    sp_ok = st.checkbox("✅ Sponsor approved this cut")
    if st.button("💾 Save sponsor slot → attaches to next render"):
        if sp_name.strip():
            spv = spi = None
            if sp_video: spv = f"{TMP}/sponsor_{sp_video.name}"; open(spv,"wb").write(sp_video.getbuffer())
            if sp_image: spi = f"{TMP}/sponsorimg_{sp_image.name}"; open(spi,"wb").write(sp_image.getbuffer())
            st.session_state.sponsor = {"name": sp_name.strip(), "script": sp_script, "video": spv, "image": spi, "place": sp_place, "approved": sp_ok}
            st.success("✅ Slot saved. STEP 6 weaves it in: 'A WORD FROM…' → their cut → 'NOW, BACK TO THE INVESTIGATION.'")
        else:
            st.warning("Enter a sponsor name first.")

with tab3:
    rendered = [i for i in line if i["status"]=="rendered" and i["out"]]
    if not rendered:
        st.warning("⬅️ Render an episode first (🏭 2·PRODUCE → STEP 6).")
    else:
        st.markdown("## STEP 7 · Build the Publish Pack (auto-numbered, shop-ready)")
        choice = st.selectbox("Episode to pack", [i["topic"] for i in rendered])
        it = rendered[[i["topic"] for i in rendered].index(choice)]
        sl = slug(it["topic"])
        hook = st.text_input("Thumbnail hook words (max 4)", it["script"].get("hook_words",""))
        if st.button("📦 STEP 7 · Build SEO + Publish Pack + Case File"):
            tp = thumbs(it["topic"], hook)
            sc = it["script"]
            advline = f" Viewer advisory: {sc['advisory']}" if sc.get("advisory") else ""
            raw = qwen(f"Topic: {it['topic']}. Support: {support}. Pinned: {sc['pinned_question']}. Binge-pitch: {sc.get('binge_pitch','')}. Share line: {sc.get('share_line','')}.{advline} "
                   f"Add disclaimer: 'Editorial commentary based on public sources; not financial advice.' Mention: full Case File dossier available via shop link. "
                   f"Return JSON {{'title':'<60 chars, no clickbait', 'description':'hook + synopsis + chapters + support + case file line + advisory/disclaimer + 3 hashtags', 'tags':[15], 'shorts_titles':[2]}}")
            safe = {"title": adsense_scrub(raw["title"]), "description": adsense_scrub(raw["description"]),
                    "tags": [adsense_scrub(t) for t in raw["tags"]], "shorts_titles": [adsense_scrub(t) for t in raw["shorts_titles"]]}
            spf = f"{TMP}/shorts.mp4"; shorts_cut(it["out"]).write_videofile(spf, codec="libx264", audio_codec="aac", fps=24, logger=None)
            dos = dossier(it["topic"], sc)
            cfp = f"{TMP}/case_file_{ep_num}.pdf"; case_file_pdf(it["topic"], series, dos, support, cfp, ep=ep_num)
            z = io.BytesIO()
            with zipfile.ZipFile(z,"w") as zf:
                zf.write(it["out"], f"EPISODE_{ep_num}_{sl}.mp4")
                zf.write(spf, f"SHORTS_{ep_num}_{sl}.mp4")
                for j,p in enumerate(tp): zf.write(p, f"THUMB_{'AB'[j]}_{ep_num}_{sl}.png")
                zf.writestr("subtitles.srt", srt_text(it["srt"]))
                zf.writestr("metadata.txt", json.dumps(safe, indent=2))
                pin = sc["pinned_question"] + f"\n☕ Support the investigation: {support}"
                if shop: pin += f"\n📄 CASE FILE #{ep_num} for this episode: {shop}"
                zf.writestr("pinned_comment.txt", pin)
                zf.writestr("community_post.txt", json.dumps(sc["community_poll"]))
                zf.writestr(f"CASE_FILE_{ep_num}_{sl}.pdf", open(cfp,"rb").read())
                zf.writestr(f"kofi_product_{ep_num}.txt",
                    f"KO-FI PRODUCT LISTING — ready to paste\n"
                    f"Product name: CASE FILE #{ep_num} — {it['topic']}\n"
                    f"Price: $5 (enable pay-what-you-want)\n"
                    f"Type: Digital product\n"
                    f"File to upload: CASE_FILE_{ep_num}_{sl}.pdf\n"
                    f"Product image: THUMB_A_{ep_num}_{sl}.png\n\n"
                    f"Description:\n" + SHOP_BLURB.format(topic=f"#{ep_num} — {it['topic']}"))
                zf.writestr("upload_checklist.txt", CHECKLIST.format(sp=f"YES — {it['sp']} (tick paid promotion + disclose)" if it.get("sp") else "No"))
                zf.writestr("rights_record.txt", RIGHTS)
            st.session_state.packed = True
            st.download_button("📦 Download PUBLISH PACK (zip)", z.getvalue(), f"SHADOW_LEDGER_PACK_{ep_num}.zip")
            st.success(f"✅ STEP 7 complete — EP#{ep_num} pack ready: numbered episode, shorts, thumbs, Case File PDF + Ko-fi listing. 🏁")
            st.json(safe)

with tab4:
    st.markdown("""**v16 FINAL MISSION CONTROL.** Pipeline: scan → slate → series → script+Gate+Guard → Director's Cut →
    render → publish pack with AUTO-NUMBERED shop-ready assets (CASE_FILE_###, THUMB_###, kofi_product_### listing).
    **PHASED REVENUE:** PHASE 1 ☕ Ko-fi tips (auto everywhere) · PHASE 2 📄 Case Files $5 (folder builds itself; drag to
    Ko-fi when ready) · PHASE 3 📚 affiliates · PHASE 4 💼 sponsors + memberships + merch. Core video FREE forever;
    supporters buy depth & belonging. Plus: Sponsor Suite, tone badges, balance advisor, auditions, estimates, retries,
    crash-resume, rights record + upload checklist. **Roadmap:** PWA → native app → OAuth upload → dubs → analytics.""")
