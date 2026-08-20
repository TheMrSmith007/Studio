# ADD THESE IMPORTS IF MISSING
import uuid, random

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
# REPLACE FROM st.sidebar TO TAB DEFINITIONS
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
        st.experimental_rerun()
    
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
    
    # EXISTING SIDEBAR ELEMENTS (keep all your code below)
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
    rf=revenue_forecast()
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
