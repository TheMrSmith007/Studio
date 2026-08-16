import streamlit as st, requests, json, os, io, re, zipfile, hashlib
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
 "Comeback / positive": "Tone: triumphant human comeback inside finance. Dopamine via hope, ingenuity, victory.",
}
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

# ---------------- HOUSE DNA (The Prestige Cut) ----------------
DNA = """You are showrunner of SHADOW LEDGER, a prestige financial documentary series.
Topic: {topic}. Series: {series}. ANGLE: {angle}
STRUCTURE:
1. COLD OPEN + VIEWER STAKES: One human moment. MUST explicitly state how this macro-event affects the viewer's daily life, wallet, or future in the first 15 seconds.
2. ACT I THE SUSPECT/PROTAGONIST: Face, quote, defining moment.
3. ACT II THE MACHINE: Stakes escalate; NEW open loop every 90s.
4. ACT III THE REVEAL: Twist; numbers translated to human scale.
5. THE OPEN QUESTION: DO NOT tie it up in a neat bow. Do not preach. Present the facts, step back, and ask a haunting philosophical question for the audience to decide in the comments. Then ONE in-brand CTA, followed by a BINGE-PITCH (tease the next specific investigation).

RULES: Present tense, short cinematic sentences. NO ACCUSATIONS. Never state guilt as fact for ongoing/alleged matters. Use 'alleged', 'according to documents', 'regulators claim'. Frame controversial claims as questions. Let the audience be the jury.
ANTI-SLOP: BANNED: delve, tapestry, landscape, game-changer, uncover the truth. EVERY scene needs a concrete detail (number, date, place). Max 3 sentences per scene.
OUTPUT JSON: {{"title_options":[3], "hook_words":"MAX 4 WORDS", "scenes":[{{"narration":"", "visual":"", "ost":""}}], "pinned_question":"", "binge_pitch":"", "community_poll":{{"q":"","a":["",""]}}}}"""

GATE = """You are SHADOW LEDGER's ruthless executive editor AND media-legal reviewer.
Topic: {topic}. Review this script JSON: {script}
FIX: (1) AI-slop phrases -> rewrite with concrete specifics;
(2) legal risk / bias -> rewrite to remove accusations, frame as questions, use 'alleged/documents show';
(3) viewer stakes -> ensure the cold open explicitly connects to the viewer's life;
(4) dragging -> tighten to max 3 sentences; (5) clickbait -> title promise MUST be delivered.
Return JSON {{"slop_clean":0-100,"emotion":0-100,"viewer_stakes":"clear|added","legal_flags_fixed":N,"clickbait":"clear|fixed",
"pacing":"one line note","scenes":[polished scenes same schema],"title_options":[polished, <60 chars]}}"""

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
    return qwen(f"Prestige documentary topic: {topic}. Decide if it supports a 2-3 episode series WITHOUT dragging. Return JSON {'series':true/false,'why':'one line','episodes':[2-3 distinct titles]}")

# ---------------- ADSENSE SAFE SCRUBBER ----------------
TRIGGERS = {"scam":"alleged fraud", "scammer":"alleged fraudster", "kill":"fatality", "murder":"fatality", "suicide":"tragic death", "terrorist":"extremist", "cartel":"syndicate", "rape":"assault", "steal":"misappropriate"}
def adsense_scrub(text):
    for bad, good in TRIGGERS.items():
        text = re.sub(rf'\b{bad}\b', good, text, flags=re.IGNORECASE)
    return text

# ---------------- PIL CARDS ----------------
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

def sponsor_blocks(sp, voice, mood):
    b = [(ImageClip(card_img("A WORD FROM", sp["name"])).with_duration(2.5), silence(2.5), None)]
    if sp.get("video"):
        svc = VideoFileClip(sp["video"]).resized((1280,720)).with_fps(24)
        sa = svc.audio if svc.audio is not None else silence(svc.duration)
        b.append((svc, sa, f"[Sponsor segment: {sp['name']}]"))
    else:
        ap = f"{TMP}/sp.mp3"
        open(ap,"wb").write(speak(sp.get("script") or f"This investigation is brought to you by {sp['name']}.", voice, mood))
        ac = AudioFileClip(ap)
        b.append((ImageClip(card_img(sp["name"], "a word from our sponsor")).with_duration(ac.duration), ac, sp.get("script","")))
    b.append((ImageClip(card_img("NOW, BACK TO", "the investigation")).with_duration(2.5), silence(2.5), None))
    return b

def render(sc, topic, series, pilot, music, voice, mood, sp=None):
    scenes = sc["scenes"][:4] if pilot else sc["scenes"]
    parts = []
    for i, s in enumerate(scenes):
        ap = f"{TMP}/a{i}.mp3"; open(ap,"wb").write(speak(s["narration"], voice, mood))
        ac = AudioFileClip(ap)
        try: vu = wan_video(wan_video_prompt(s["visual"]))
        except Exception: vu = pexels_clip(s["visual"].split(".")[0])
        vc = VideoFileClip(fetch(vu,f"c{i}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration < ac.duration: vc = concatenate_videoclips([vc, vc.copy()])
        vc = vc.with_duration(ac.duration)
        if s.get("ost"):
            vc = CompositeVideoClip([vc, ImageClip(ost_img(s["ost"]))
                 .with_duration(min(3,ac.duration)).with_start(ac.duration*0.35).with_position((0,560))])
        parts.append((vc, ac, s["narration"]))
    title = (ImageClip(card_img("SHADOW LEDGER", series)).with_duration(3), silence(3), None)
    end   = (ImageClip(card_img("SUBSCRIBE", "the next ledger opens soon")).with_duration(5), silence(5), None)
    base = [parts[0], title] + parts[1:]
    if sp and sp.get("name"):
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
        mc = AudioFileClip(music); n = int(vid.duration//mc.duration)+1
        layers_a.append(concatenate_videoclips([mc]*n).with_duration(vid.duration).with_volume_scaled(0.10))
    markers.append(vid.duration*0.68)
    layers_a.append(sound_bed(vid.duration, markers).with_volume_scaled(0.6))
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

# ---------------- UI ----------------
st.set_page_config(page_title="Shadow Ledger Studio", page_icon="🎬", layout="wide")
st.title("🎬 SHADOW LEDGER — Digital Hollywood Studio")
support = st.sidebar.text_input("Support link (Ko-fi)", "https://ko-fi.com/shadowledger")
voice = st.sidebar.text_input("Narrator voice (CosyVoice v2 ID)", "longanyang")
mood = st.sidebar.selectbox("Narration mood (variety per episode)", list(MOODS))
music = st.sidebar.file_uploader("House score (optional ambient track)", type=["mp3","wav"])
tab1,tab2,tab3,tab4 = st.tabs(["🥚 Golden Egg + Radar","🏭 Production Line","📦 SEO & Publish Pack","📈 Strategy"])

with tab1:
    seeds = st.text_area("Seed topics (mix dark + positive — keep 5-8)", "BlackRock buying housing\nTicketmaster Live Nation monopoly\nThe janitor who left $6 million to his hospital\nHow Norway became the world's landlord\nThe teacher who out-traded Wall Street\nBoeing whistleblowers")
    if st.button("Run Golden Egg scan"):
        results = []
        for s in [x for x in seeds.splitlines() if x.strip()]:
            score, why = golden_egg(s.strip())
            results.append((s.strip(), score, why))
            st.markdown(f"**{s.strip()}** — 🥚 **{score}/100** · {why}")
        st.session_state.scan = sorted(results, key=lambda r: -r[1])
        st.caption("🏆 Sorted best-first. Go to the Production Line and tick your slate.")
    if st.button("Trend Radar"):
        for s in [x for x in seeds.splitlines() if x.strip()][:2]:
            sug, vel = trend_radar(s.strip())
            st.markdown(f"**{s}** → autocomplete: {', '.join(sug[:5])} · hot this week: {vel[:3]}")

with tab2:
    series = st.text_input("Series brand", "The Monopoly Files")
    angle = st.selectbox("Story angle (mix your slate: 70% dark / 20% mystery / 10% positive)", list(ANGLES))
    if st.session_state.get("scan"):
        st.subheader("🏆 Tick your slate (winner pre-ticked)")
        picks = []
        for j,(t, sc, w) in enumerate(st.session_state.scan):
            if st.checkbox(f"{t} — 🥚 {sc}/100", value=(j==0), key=f"ck_{t}"):
                picks.append((t, sc))
        if st.button("➕ Add ticked topics to production line"):
            for t, sc in picks:
                if not any(i["topic"]==t for i in st.session_state.line):
                    st.session_state.line.append({"topic":t,"score":sc,"tag":"","status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":""})
            save_line(st.session_state.line)
        if st.button("🎭 Check series potential (top scorer)"):
            st.session_state.splan = series_plan(st.session_state.scan[0][0])
        if st.session_state.get("splan"):
            spn = st.session_state.splan
            st.markdown(f"**Series verdict:** {'✅ YES' if spn['series'] else '❌ no'} — {spn['why']}")
            for e in spn.get("episodes",[]): st.markdown(f"• {e}")
            if spn["series"] and st.button("➕ Add series episodes to line"):
                for e in spn.get("episodes",[]):
                    if not any(i["topic"]==e for i in st.session_state.line):
                        st.session_state.line.append({"topic":e,"score":st.session_state.scan[0][1],"tag":"SERIES","status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":""})
                save_line(st.session_state.line)
    custom = st.text_input("➕ Or add a custom topic", "")
    if custom.strip() and st.button("Add custom topic"):
        st.session_state.line.append({"topic":custom.strip(),"score":0,"tag":"CUSTOM","status":"queued","script":None,"gate":None,"out":None,"srt":None,"err":""})
        save_line(st.session_state.line)
    st.subheader("🏭 Production line (auto-saved — survives crashes & sleeps)")
    if not st.session_state.line: st.caption("Line empty — scan & tick above.")
    for i, it in enumerate(st.session_state.line):
        st.markdown(f"**{i+1}.** {it['topic']} {('['+it['tag']+']' if it['tag'] else '')} — `{it['status']}` {it['err'] or ''}")
    pilot = st.checkbox("PILOT MODE (60-90s test renders — do first)", True)
    if st.button("📜 Script next + 🛡️ Quality Gate"):
        it = next((x for x in st.session_state.line if x["status"]=="queued"), None)
        if it:
            it["script"] = write_script(it["topic"], series, angle)
            try:
                g = quality_gate(it["topic"], it["script"])
                if g.get("scenes"): it["script"]["scenes"] = g["scenes"]
                if g.get("title_options"): it["script"]["title_options"] = g["title_options"]
                it["gate"] = g
            except Exception as e:
                it["gate"] = {"pacing": f"gate skipped: {str(e)[:80]}"}
            it["status"] = "scripted"; save_line(st.session_state.line)
            st.session_state.edits = {i2:(s["narration"],s["visual"]) for i2,s in enumerate(it["script"]["scenes"])}
    cur = next((x for x in st.session_state.line if x["status"]=="scripted"), None)
    if cur:
        if cur.get("gate"):
            g = cur["gate"]
            st.markdown(f"🛡️ **Quality Gate:** slop-clean **{g.get('slop_clean','-')}/100** · emotion **{g.get('emotion','-')}/100** · viewer stakes **{g.get('viewer_stakes','-')}** · legal flags fixed **{g.get('legal_flags_fixed','-')}** · clickbait **{g.get('clickbait','-')}** · pacing: {g.get('pacing','-')}")
        st.subheader(f"✂️ Director's Cut — {cur['topic']}")
        for i2, s in enumerate(cur["script"]["scenes"]):
            nar, vis = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
            nn = st.text_area(f"Narration {i2+1}", nar, key=f"n_{i2}", height=90)
            vv = st.text_input(f"Visual {i2+1}", vis, key=f"v_{i2}")
            st.session_state.edits[i2] = (nn, vv)
        if st.button("🛡️ Re-run Quality Gate on my edits"):
            for i2, s in enumerate(cur["script"]["scenes"]):
                nn, vv = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                s["narration"], s["visual"] = nn, vv
            g = quality_gate(cur["topic"], cur["script"])
            if g.get("scenes"): cur["script"]["scenes"] = g["scenes"]
            cur["gate"] = g; save_line(st.session_state.line)
            st.session_state.edits = {i2:(s["narration"],s["visual"]) for i2,s in enumerate(cur["script"]["scenes"])}
    with st.expander("💼 Sponsor segment (optional — TV-style break)"):
        sp_name = st.text_input("Sponsor name", "")
        sp_script = st.text_area("Sponsor read (you control every word)", "")
        sp_video = st.file_uploader("Sponsor's own video (optional)", type=["mp4","mov","webm"])
        sp_place = st.selectbox("Placement", ["After cold open + title (TV style)", "Before the final reveal"])
    if st.button("🎬 Render next in line (resumes where it left off)"):
        it = next((x for x in st.session_state.line if x["status"] in ("queued","scripted")), None)
        if it:
            try:
                if not it["script"]: it["script"] = write_script(it["topic"], series, angle)
                for i2, s in enumerate(it["script"]["scenes"]):
                    nn, vv = st.session_state.edits.get(i2, (s["narration"], s["visual"]))
                    s["narration"], s["visual"] = nn, vv
                mp3 = f"{TMP}/house_{music.name}" if music else None
                if music: open(mp3,"wb").write(music.getbuffer())
                sp = None
                if sp_name.strip():
                    spv = None
                    if sp_video: spv = f"{TMP}/sponsor_{sp_video.name}"; open(spv,"wb").write(sp_video.getbuffer())
                    sp = {"name": sp_name.strip(), "script": sp_script, "video": spv, "place": sp_place}
                out, srt = render(it["script"], it["topic"], series, pilot, mp3, voice, mood, sp)
                it["out"], it["srt"], it["status"], it["err"] = out, srt, "rendered", ""
                st.video(out)
                st.download_button("⬇️ Download this episode", open(out,"rb").read(), f"{it['topic'][:20]}.mp4")
            except Exception as e:
                it["status"], it["err"] = "failed", str(e)[:150]
            save_line(st.session_state.line)
    st.download_button("💾 Backup production line (json)", json.dumps(st.session_state.line).encode(), "shadow_line.json")
    up = st.file_uploader("Restore backup", type=["json"])
    if up: st.session_state.line = json.load(up); save_line(st.session_state.line)

with tab3:
    rendered = [i for i in st.session_state.line if i["status"]=="rendered" and i["out"]]
    if rendered:
        choice = st.selectbox("Episode to pack", [i["topic"] for i in rendered])
        it = rendered[[i["topic"] for i in rendered].index(choice)]
        hook = st.text_input("Thumbnail hook words (max 4)", it["script"].get("hook_words",""))
        if st.button("🖼️ Build SEO + Publish Pack"):
            tp = thumbs(it["topic"], hook)
            sc = it["script"]
            raw_seo = qwen(f"Topic: {it['topic']}. Support: {support}. Pinned: {sc['pinned_question']}. Binge-pitch: {sc.get('binge_pitch','')}. "
                       f"Add disclaimer: 'Editorial commentary based on public sources; not financial advice.' "
                       f"Return JSON {{'title':'<60 chars, no clickbait', 'description':'hook + synopsis + chapters + support + disclaimer + 3 hashtags', 'tags':[15], 'shorts_titles':[2]}}")
            # AdSense Safe Scrubber applied here
            safe_seo = {"title": adsense_scrub(raw_seo["title"]), "description": adsense_scrub(raw_seo["description"]), "tags": [adsense_scrub(t) for t in raw_seo["tags"]], "shorts_titles": [adsense_scrub(t) for t in raw_seo["shorts_titles"]]}
            sp = f"{TMP}/shorts.mp4"; shorts_cut(it["out"]).write_videofile(sp, codec="libx264", audio_codec="aac", fps=24, logger=None)
            z = io.BytesIO()
            with zipfile.ZipFile(z,"w") as zf:
                zf.write(it["out"], "episode.mp4"); zf.write(sp, "shorts_cut.mp4")
                for j,p in enumerate(tp): zf.write(p, f"thumb_{'AB'[j]}.png")
                zf.writestr("subtitles.srt", srt_text(it["srt"]))
                zf.writestr("metadata.txt", json.dumps(safe_reo, indent=2))
                zf.writestr("pinned_comment.txt", sc["pinned_question"] + f"\n☕ Support the investigation: {support}")
                zf.writestr("community_post.txt", json.dumps(sc["community_poll"]))
            st.download_button("📦 Download PUBLISH PACK (zip)", z.getvalue(), "publish_pack.zip")
            st.success("✅ AdSense Safe-Scrubber applied to Title, Description, and Tags.")
            st.json(safe_seo)
    else:
        st.caption("Render an episode first — then build its publish pack here.")

with tab4:
    st.markdown("""**v10 STUDIO (The Prestige Cut):** scan → slate → script + 🛡️ QUALITY GATE (anti-slop, 
    viewer stakes, legal-safe, open questions) → Director's Cut → render → SEO pack with **AdSense Safe-Scrubber**.
    DNA Rules: No accusations (let the audience decide), Viewer Stakes in first 15s, Binge-Loop Outros.
    House DNA in every episode: cold open → title card → acts → reveal → open question → end card · 
    emotional CosyVoice (6 moods) · procedural tension score · logo bug · ONE lower-third CTA · SRT · 
    A/B thumbs · pinned comment + Ko-fi · Shorts cut · community poll · TV-style sponsor mode · crash-resume line.
    **Phase-2:** OAuth auto-upload, dubbed tracks, analytics loop, memberships + Super Thanks, merch.""")
