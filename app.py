import streamlit as st, requests, json, os, io, re, zipfile, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import dashscope
from dashscope import VideoSynthesis, ImageSynthesis
from dashscope.audio.tts_v2 import SpeechSynthesizer
from moviepy import (VideoFileClip, AudioFileClip, ImageClip, AudioClip,
                     CompositeVideoClip, concatenate_videoclips, vfx)

# ---------------- CONFIG ----------------
DASH, YT, PEX = st.secrets["DASHSCOPE_API_KEY"], st.secrets["YOUTUBE_API_KEY"], st.secrets["PEXELS_API_KEY"]
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
VOICE = "longanyang"                      # CosyVoice v2 (swap via docs voice list)
GOLD, BLACK = (212,175,55), (5,6,8)
TMP = "/tmp"
FONT = next((p for p in ["assets/Cinzel-Bold.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"] if os.path.exists(p)), None)
def F(sz): return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default(sz)

# ---------------- HOUSE DNA (Netflix-crime style) ----------------
DNA = """You are showrunner of SHADOW LEDGER, a prestige Netflix-style financial-crime
documentary series. Episode topic: {topic}. Series: {series}.
STRUCTURE: COLD OPEN (one human moment, shocking concrete detail, ends on a question) /
ACT I THE SUSPECT (villain with face, quote, arrogance) / ACT II THE MACHINE (stakes
escalate; NEW open loop every 90s) / ACT III THE REVEAL (twist; numbers translated to
human scale) / THE WOUND (quiet haunting question; then ONE in-brand CTA max 12 words,
e.g. 'Subscribe - the next ledger opens Friday.'). NEVER a CTA earlier.
RULES: present tense, short cinematic sentences, no keyword stuffing, no 'in today's
video', no AI slop. Every scene: an on_screen_text beat (2-5 words, every 10-15s).
OUTPUT JSON: {{"title_options":[3], "hook_words":"MAX 4 WORDS", "scenes":[{{"narration":"",
"visual":"", "ost":""}}], "pinned_question":"", "community_poll":{{"q":"","a":["",""]}}}}"""

def qwen(prompt, sys=None):
    m = ([{"role":"system","content":sys}] if sys else []) + [{"role":"user","content":prompt}]
    r = requests.post("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        headers={"Authorization": f"Bearer {DASH}"},
        json={"model":"qwen-plus","messages":m,"response_format":{"type":"json_object"}}).json()
    return r.json() if isinstance(r, dict) and "choices" not in r else json.loads(r["choices"][0]["message"]["content"])

def wan_video_prompt(v): return (f"{v}. cinematic documentary film still, anamorphic 2.39:1, "
    "35mm grain, low-key chiaroscuro, crushed blacks, gold practicals, teal shadows, slow dolly, no text, no watermark")

# ---------------- GENERATORS ----------------
def speak(text):
    return SpeechSynthesizer(model="cosyvoice-v2", voice=VOICE).call(text)
def wan_video(prompt):
    r = VideoSynthesis.wait(VideoSynthesis.async_call(model="wan2.1-t2v-turbo", prompt=prompt, size="1280*720"))
    return r.output.video_url
def wan_images(prompt, n=2):
    r = ImageSynthesis.call(model="wanx2.1-t2i-turbo", prompt=prompt, n=n, size="1280*720")
    return [x["url"] for x in r.output.results]
def pexels_clip(q):
    v = requests.get("https://api.pexels.com/videos/search", headers={"Authorization":PEX},
                     params={"query":q,"per_page":5}).json()["videos"]
    return v[0]["video_files"][0]["link"]
def fetch(url, name):
    p = f"{TMP}/{name}"; open(p,"wb").write(requests.get(url).content); return p

# ---------------- YOUTUBE RESEARCH ----------------
def yt(path, **kw): return requests.get(f"https://www.googleapis.com/youtube/v3/{path}",
    params={"key":YT, **kw}).json()
def golden_egg(topic):
    s = yt("search", part="snippet", q=topic, type="video", maxResults=10, order="viewCount")
    ids = [i["id"]["videoId"] for i in s.get("items",[])]
    if not ids: return 50, "no data"
    vs = yt("videos", part="statistics,snippet", id=",".join(ids))["items"]
    views = [int(v["statistics"]["viewCount"]) for v in vs]
    demand = min(45, int(sum(views)/len(views)/1_000_000*9))
    ages = [(1599999999999 - int(v["snippet"]["publishedAt"][:4])*31536000000) for v in vs]
    fresh = min(20, int(sum(1 for a in ages if a < 2*31536000000)*2.5))
    chans = {v["snippet"]["channelId"] for v in vs}
    comp = max(0, 20 - len(chans)*2)                     # many distinct channels = low comp
    break_out = min(15, sum(1 for v in vs if int(v["statistics"]["viewCount"])>200_000)*5)
    return min(100, demand+fresh+comp+break_out), f"demand {demand}/45 · momentum {fresh}/20 · open field {comp}/20 · small-channel proof {break_out}/15"
def trend_radar(seed):
    sug = requests.get("https://suggestqueries.google.com/complete/search",
        params={"client":"youtube","q":seed}).json()[1]
    wk = yt("search", part="snippet", q=seed, type="video", order="viewCount",
            publishedAfter=st.session_state.get("week_ago","2026-08-08T00:00:00Z"), maxResults=5)
    vel = [f"{i['snippet']['title'][:40]}…" for i in wk.get("items",[])]
    return [s[0] if isinstance(s,list) else s for s in sug], vel

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
    d.text((640,80), text.upper(), font=F(72), fill=GOLD, anchor="mm",
           stroke_width=5, stroke_fill=(0,0,0))
    return np.array(img)
def make_bug():
    if os.path.exists("assets/sl_logo.png") and not os.path.exists(f"{TMP}/bug.png"):
        a = np.array(Image.open("assets/sl_logo.png").convert("RGBA"))
        m = a[...,:3].sum(axis=2) < 135; a[m,3]=0; a[~m,3]=150
        img = Image.fromarray(a); w,h = img.size
        img.resize((int(w*160/h),160), Image.LANCZOS).save(f"{TMP}/bug.png")
make_bug()
def silence(d): return AudioClip(lambda t: [0,0], d, fps=44100)

# ---------------- PRODUCTION ENGINE ----------------
def produce(topic, series, pilot, support, music):
    sc = qwen(DNA.format(topic=topic, series=series))
    scenes = sc["scenes"][:4] if pilot else sc["scenes"]
    vclips, acls, srt, t = [], [], [], 0.0
    for i, s in enumerate(scenes):
        ap = f"{TMP}/a{i}.mp3"; open(ap,"wb").write(speak(s["narration"]))
        ac = AudioFileClip(ap); acls.append(ac)
        try: vu = wan_video(wan_video_prompt(s["visual"]))
        except Exception: vu = pexels_clip(s["visual"].split(".")[0])
        vc = VideoFileClip(fetch(vu,f"c{i}.mp4")).without_audio().resized((1280,720)).with_fps(24)
        while vc.duration < ac.duration: vc = concatenate_videoclips([vc, vc.copy()])
        vc = vc.with_duration(ac.duration).with_audio(ac)
        if s.get("ost"):
            vc = CompositeVideoClip([vc, ImageClip(ost_img(s["ost"]))
                 .with_duration(min(3,ac.duration)).with_start(ac.duration*0.35).with_position((0,560))])
        srt.append((t, t+ac.duration, s["narration"])); t += ac.duration
        vclips.append(vc)
    title = ImageClip(card_img("SHADOW LEDGER", series)).with_duration(3).with_audio(silence(3))
    end   = ImageClip(card_img("SUBSCRIBE", "the next ledger opens soon")).with_duration(5).with_audio(silence(5))
    vid = concatenate_videoclips([title]+vclips+[end])
    aud = concatenate_videoclips([silence(3)]+acls+[silence(5)])
    if music:
        mc = AudioFileClip(music); n = int(vid.duration//mc.duration)+1
        bed = concatenate_videoclips([mc]*n).with_duration(vid.duration).with_volume_scaled(0.12)
        aud = CompositeVideoClip([]) and aud  # placeholder keep
        from moviepy import CompositeAudioClip
        aud = CompositeAudioClip([aud, bed]).with_duration(vid.duration)
    final = vid.with_audio(aud)
    layers = [final]
    if os.path.exists(f"{TMP}/bug.png"):
        layers.append(ImageClip(f"{TMP}/bug.png").resized(height=64).with_position((28,28)).with_duration(final.duration))
    layers.append(ImageClip(card_img("IF YOU FOLLOW THE MONEY,","subscribe - new investigations weekly",transparent=True))
                  .with_duration(5).with_start(final.duration*0.68).with_position((76,540))
                  .with_effects([vfx.FadeIn(0.6), vfx.FadeOut(0.8)]))
    final = CompositeVideoClip(layers)
    out = f"{TMP}/{hashlib.md5(topic.encode()).hexdigest()}.mp4"
    final.write_videofile(out, codec="libx264", audio_codec="aac", fps=24, logger=None)
    return out, sc, srt
def shorts_cut(video_path, idx=0):
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
music = st.sidebar.file_uploader("House score (one ambient track, reused forever)", type=["mp3","wav"])
tab1,tab2,tab3,tab4 = st.tabs(["🥚 Golden Egg + Radar","🎬 Production","🖼️ SEO & Publish Pack","📈 Strategy"])

with tab1:
    seeds = st.text_area("Seed topics (one per line)", "Ticketmaster Live Nation monopoly\nBoeing whistleblowers\nBlackRock buying housing\nWeWork collapse")
    if st.button("Run Golden Egg scan"):
        for s in [x for x in seeds.splitlines() if x.strip()]:
            score, why = golden_egg(s.strip())
            st.markdown(f"**{s.strip()}** — 🥚 **{score}/100** · {why}")
    if st.button("Trend Radar"):
        for s in [x for x in seeds.splitlines() if x.strip()][:2]:
            sug, vel = trend_radar(s.strip())
            st.markdown(f"**{s}** → autocomplete: {', '.join(sug[:5])} · hot this week: {vel[:3]}")

with tab2:
    topic = st.text_input("Episode topic", "How Ticketmaster Became the Most Hated Monopoly in America")
    series = st.text_input("Series", "The Monopoly Files · Ep 1")
    pilot = st.checkbox("PILOT MODE (60-90s test render — do this first)", True)
    if st.button(" Produce episode"):
        with st.spinner("Writing, voicing, filming, cutting… this is the good part."):
            out, sc, srt = produce(topic, series, pilot, support,
                                   music.name if music and hasattr(music,"name") and os.path.exists(music.name) else None)
        st.video(out)
        st.download_button("⬇️ Download episode MP4", open(out,"rb").read(), "episode.mp4")
        st.session_state.pack = (out, sc, srt)

with tab3:
    if st.button("🖼️ Build SEO + Publish Pack") and st.session_state.get("pack"):
        out, sc, srt = st.session_state.pack
        tp = thumbs(st.session_state.get("topic","monopoly"), sc["hook_words"])
        seo = qwen(f"Topic: {topic}. Support: {support}. Pinned question: {sc['pinned_question']}. "
                   f"Return JSON {{'title':'<60 chars, curiosity gap, keyword first 40', 'description':'hook line + 3-act synopsis + chapters + support line + 3 hashtags', 'tags':[15], 'shorts_titles':[2]}}")
        z = io.BytesIO()
        with zipfile.ZipFile(z,"w") as zf:
            zf.write(out, "episode.mp4")
            for j,p in enumerate(tp): zf.write(p, f"thumb_{'AB'[j]}.png")
            zf.writestr("subtitles.srt", srt_text(srt))
            zf.writestr("metadata.txt", json.dumps(seo, indent=2))
            zf.writestr("pinned_comment.txt", sc["pinned_question"] + f"\n☕ Support the investigation: {support}")
            zf.writestr("community_post.txt", json.dumps(sc["community_poll"]))
        st.download_button("📦 Download PUBLISH PACK (zip)", z.getvalue(), "publish_pack.zip")
        st.json(seo)

with tab4:
    st.markdown("""**House rules baked in:** bug top-left always · ONE lower-third CTA at 68% · pinned comment
    + Ko-fi · Shorts funnel · A/B thumbs · community polls · SRT · house score · pattern interrupts.
    **Phase-2 upgrades (post-proof):** OAuth auto-upload, dubbed audio tracks, analytics feedback loop,
    memberships + Super Thanks, merch store with the logo.""")
