import streamlit as st
from core_engine import calc_metrics
import matplotlib.pyplot as plt
import numpy as np
import urllib.parse
import matplotlib

# --- STABILISIERUNG ---
matplotlib.use('Agg')

# --- CONFIG ---
st.set_page_config(page_title="VECTR-X // CYBER-LAB", layout="wide")

# --- URL PARAMETER CHECK ---
params = st.query_params
is_athlete = "w" in params
is_view_mode = params.get("mode", "edit") == "view"

# --- NEU: ATHLETEN-ANTENNE (GLOBAL) ---
# Diese Variablen holen sich die Daten direkt aus der URL, sobald die App startet
f_name = params.get("fn", "")
l_name = params.get("ln", "")
bday = params.get("bd", "")
sport = params.get("sp", "")
gender = params.get("g", "")
full_n = f"{f_name} {l_name}".strip()

# --- SPRACH-ENGINE ---
if 'lang' not in st.session_state: st.session_state.lang = 'GER'
def t(german, english): return german if st.session_state.lang == 'GER' else english

# --- HELPER ---
def fmt_pace(s):
    if s <= 0.1: return "-:--"
    sec = 3600 / s
    return f"{int(sec//60)}:{int(sec%60):02d}"

def fmt_time(seconds):
    h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

def get_benchmark_html(val, metric_type, color_hex):
    # VECTR-X "HARD TRUTH" BENCHMARKS
    if metric_type == "vo2max": 
        levels = [("ELITE", 65, 999), ("ATHLETE", 55, 65), ("AMATEUR", 45, 55), ("ROOKIE", 0, 45)]
    elif metric_type == "lt2": 
        levels = [("ELITE", 17.5, 99), ("ATHLETE", 15.0, 17.5), ("AMATEUR", 12.0, 15.0), ("ROOKIE", 0, 12.0)]
    elif metric_type == "fatmax": 
        levels = [("ELITE", 15.0, 99), ("ATHLETE", 12.5, 15.0), ("AMATEUR", 10.0, 12.5), ("ROOKIE", 0, 10.0)]
    elif metric_type == "re": 
        levels = [("ELITE", 0, 0.30), ("ATHLETE", 0.30, 0.55), ("AMATEUR", 0.55, 0.85), ("ROOKIE", 0.85, 9.99)]
    elif metric_type == "stab": 
        levels = [("ELITE", 75, 100), ("ATHLETE", 60, 75), ("AMATEUR", 40, 60), ("ROOKIE", 0, 40)]
    else: levels = []

    html_out = "<div style='display:flex; flex-direction:column; align-items:flex-end; gap:2px; font-family:monospace;'>"
    for label, low, high in levels:
        is_active = low <= val < high
        style = f"color:{color_hex}; font-weight:700; text-shadow: 0 0 10px {color_hex};" if is_active else "color:#444; font-weight:400;"
        icon = "●" if is_active else "○"
        range_txt = f"<{high}" if low == 0 else f">{low}" if high > 90 else f"{low}-{high}"
        html_out += f"<div style='font-size:11px; {style}'>{label} <span style='font-size:9px; opacity:0.7;'>({range_txt})</span> {icon}</div>"
    return html_out + "</div>"

# --- CSS (ORIGINAL V8 + FIX + VIEW MODE) ---
hide_sidebar_style = ""
if is_view_mode:
    hide_sidebar_style = """
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stSidebarNav"] {display: none;}
        .st-emotion-cache-16ids99 {display: none;}
    """

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@400;600&display=swap');
    .main {{ background-color: #0A0A0B; color: #E0E0E0; }}
    h1, h2, h3 {{ font-family: 'Orbitron', sans-serif; letter-spacing: 2px; color: #00F2FF; }}
    {hide_sidebar_style}
    
    /* ANIMATIONS */
    @keyframes pulse-green {{ 0% {{ color: #39FF14; text-shadow: 0 0 5px #39FF14; }} 50% {{ text-shadow: 0 0 25px #39FF14; color: #39FF14; }} 100% {{ color: #39FF14; text-shadow: 0 0 5px #39FF14; }} }}
    @keyframes pulse-red {{ 0% {{ color: #FF3131; text-shadow: 0 0 5px #FF3131; }} 50% {{ text-shadow: 0 0 25px #FF3131; color: #FF3131; }} 100% {{ color: #FF3131; text-shadow: 0 0 5px #FF3131; }} }}
    @keyframes pulse-cyan {{ 0% {{ box-shadow: 0 0 5px #00F2FF; }} 50% {{ box-shadow: 0 0 20px #00F2FF; }} 100% {{ box-shadow: 0 0 5px #00F2FF; }} }}
    @keyframes pulse-crit {{ 0% {{ box-shadow: 0 0 5px #FF3131; border-color: #FF3131; }} 50% {{ box-shadow: 0 0 30px #FF3131; border-color: #FF0000; }} 100% {{ box-shadow: 0 0 5px #FF3131; border-color: #FF3131; }} }}

    .glow-up {{ animation: pulse-green 2s infinite; font-weight: 800 !important; }}
    .glow-down {{ animation: pulse-red 2s infinite; font-weight: 800 !important; }}

    /* CARDS */
    .set-card {{ padding: 20px; border-radius: 12px; margin-bottom: 15px; background-color: #161618; border: 1px solid #2C2C2E; border-left: 8px solid #00F2FF; }}
    .set-card-tall {{ padding: 20px; border-radius: 14px; margin-bottom: 18px; background-color: #161618; border: 1px solid #2C2C2E; border-left: 8px solid #00F2FF; min-height: 240px; display: flex; flex-direction: column; justify-content: space-between; }}
    
    .card-title {{ font-weight: 700; font-size: 14px; color: #00F2FF; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; display: block; }}
    .card-content-split {{ display: flex; justify-content: space-between; align-items: center; }}
    .card-val-big {{ font-weight: 700; font-size: 34px; color: #FFFFFF; font-family: monospace; line-height: 1; }}
    .card-unit-white {{ font-weight: 600; font-size: 16px; color: #FFFFFF; font-family: monospace; margin-left: 6px; }}
    .card-expl {{ font-size: 12px; color: #B0B0B5; line-height: 1.4; margin-top: 12px; border-top: 1px solid #2C2C2E; padding-top:8px; }}
    
    .uni-pace {{ font-size: 14px; color: #636366 !important; font-family: monospace; }}
    .hf-section {{ text-align: right; color: #FF3131; }}
    .hf-val {{ font-size: 28px; font-weight: 700; font-family: monospace; display: block; }}
    .hf-label {{ font-size: 10px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px; }}
    
    /* STABILITY BOX */
    .stability-box {{ padding: 20px; border-radius: 12px; text-align: center; margin-top: 20px; font-family: 'Orbitron'; letter-spacing: 3px; background: rgba(255,255,255,0.02); }}
    .res-ultra {{ border: 2px solid #00F2FF !important; color: #00F2FF !important; animation: pulse-cyan 3s infinite; }}
    .res-stable {{ border: 2px solid #39FF14 !important; color: #39FF14 !important; }}
    .res-limit {{ border: 2px solid #FFCC00 !important; color: #FFCC00 !important; }}
    .res-critical {{ border: 2px solid #FF3131 !important; color: #FF3131 !important; animation: pulse-crit 1.5s infinite; }}

    .metric-wrapper {{ display: flex; flex-direction: column; min-height: 120px; }}
    .delta-section {{ font-size: 15px; font-family: monospace; margin-top: 8px; padding-top: 8px; border-top: 1px solid #1C1C1E; }}

    .blue-neon {{ border-left-color: #00F2FF; }} .green-neon {{ border-left-color: #34C759; }} .orange-neon {{ border-left-color: #FF9500; }} .red-neon {{ border-left-color: #FF3131; }} .yellow-neon {{ border-left-color: #FFCC00; }}

    /* SHARE BUTTON */
    .share-btn {{ 
        background-color: #1A1A1D; 
        color: #BC13FE; 
        padding: 12px; 
        border-radius: 8px; 
        text-align: center; 
        font-weight: bold; 
        font-family: 'Orbitron'; 
        border: 1px solid #BC13FE; 
        box-shadow: 0 0 10px #BC13FE; 
        transition: 0.3s; 
        cursor: pointer; 
        text-decoration: none; 
        display: block; 
        margin-top: 15px;
    }}
    .share-btn:hover {{ 
        background-color: #BC13FE; 
        color: black; 
        box-shadow: 0 0 25px #BC13FE; 
    }}
    </style>
    """, unsafe_allow_html=True)

# --- DATEN-EXTRAKTION ---
w_def = float(params.get("w", 75.0))
h_def = float(params.get("h", 180.0))
s_def = float(params.get("s", 42.0))
v_def = [float(x) for x in params.get("v", "10,12,14,16,18").split(",")]
l_def = [float(x) for x in params.get("l", "1.2,1.8,3.5,6.5,7.8").split(",")]
hr_def = [float(x) for x in params.get("hr", "135,148,162,178,184").split(",")]

# --- SIDEBAR LOGIK ---
if not is_athlete and not is_view_mode:
    with st.sidebar:
        st.markdown(f"## // VECTR-X LAB")
        
        # Reihe 1: Name
        c_n1, c_n2 = st.columns(2)
        f_name = c_n1.text_input("VORNAME", value=params.get("fn", ""))
        l_name = c_n2.text_input("NACHNAME", value=params.get("ln", ""))
    
        # Reihe 2: Stammdaten
        c_s1, c_s2 = st.columns(2)
        # Logik für das automatische Setzen des Geschlechts aus der URL
        g_idx = 0 if params.get("g") == "M" else 1 if params.get("g") == "W" else 2
        gender = c_s1.selectbox("GESCHLECHT", ["M", "W", "D"], index=g_idx)
        bday = c_s2.text_input("GEBURTSTAG", value=params.get("bd", "01.01.1990"), help="Format: DD.MM.YYYY")
    
        # Reihe 3: Disziplin
        sport = st.text_input("SPORTART / POSITION", value=params.get("sp", "RUNNING"))
    
        full_n = f"{f_name} {l_name}".strip()
        st.write("---")
        st.session_state.lang = st.radio("LANGUAGE", ["GER", "ENG"], horizontal=True)
        st.write("---")
        st.subheader(t("// BIOMETRIE //", "// BIOMETRICS //"))
        
        weight = st.number_input(t("Gewicht (kg)", "Weight"), value=w_def, step=0.1, format="%.1f")
        height = st.number_input(t("Größe (cm)", "Height"), value=h_def, step=0.1, format="%.1f")
        sw = st.number_input(t("Schulterbreite (cm)", "Shoulder"), value=s_def, step=0.1, format="%.1f")
        
        st.write("---")
        level_select = st.selectbox(t("LEVEL", "SKILL_LEVEL"), ["Amateur", "Ambitioniert", "Elite"])
        compare_mode = st.checkbox(t("> REF_SYNC AKTIVIEREN", "> ACTIVATE_REF_SYNC"), value=False)
        
        def input_block(label, key_p, def_v, def_l, def_h):
            st.markdown(f"**// {label}**")
            c1, c2, c3 = st.columns(3)
            v = [c1.number_input(f"SPD_{i+1}", key=f"{key_p}v{i}", value=def_v[i], step=0.1, format="%.1f") for i in range(len(def_v))]
            l = [c2.number_input(f"LAC_{i+1}", key=f"{key_p}l{i}", value=def_l[i], step=0.1, format="%.1f") for i in range(len(def_l))]
            h = [c3.number_input(f"HF_{i+1}", key=f"{key_p}h{i}", value=int(def_h[i]), step=1, format="%d") for i in range(len(def_h))]
            return v, l, h

        v1, l1, h1 = input_block(t("LIVE_SITZUNG", "LIVE_SESSION"), "t1", v_def, l_def, hr_def)
        metrics_t1 = calc_metrics(v1, l1, h1, height, weight, sw)
        
        metrics_t2 = None
        if compare_mode:
            # Standardwerte für Vergleich (etwas schlechter simuliert)
            v2, l2, h2 = input_block(t("ARCHIV_DATEN", "ARCHIVE_DATA"), "t2", v_def, [x+0.5 for x in l_def], [x+5 for x in hr_def])
            metrics_t2 = calc_metrics(v2, l2, h2, height, weight, sw)

       # --- SHARE BUTTON LOGIK ---
        st.write("---")
        share_query = urllib.parse.urlencode({
            'fn': f_name,
            'ln': l_name,
            'bd': bday,
            'sp': sport,
            'g': gender,
            'w': weight, 'h': height, 's': sw, 
            'v': ",".join(map(str,v1)), 
            'l': ",".join(map(str,l1)), 
            'hr': ",".join(map(str,h1)), 
            'mode': 'view'
        })
        
        full_url = "https://vectr-x-system-4udwk2bg799tpknjor4hmb.streamlit.app/?" + share_query
        mail_link = f"mailto:?subject=VECTR-X%20Lab%20Report&body=Hi!%20Hier%20sind%20deine%20Performance-Daten:%0D%0A%0D%0A{urllib.parse.quote(full_url)}"
        st.markdown(f'<a href="{mail_link}" class="share-btn">✉ SEND TO ATHLETE</a>', unsafe_allow_html=True)

else:
    # --- ATHLETEN ANSICHT (EMPFÄNGER-LOGIK) ---
    # Hier liest das Handy die Namen und Daten aus der URL
    f_name = params.get("fn", "")
    l_name = params.get("ln", "")
    full_n = f"{f_name} {l_name}".strip()
    bday = params.get("bd", "")
    sport = params.get("sp", "")
    gender = params.get("g", "")
    
    # Die biometrischen Daten aus der URL laden
    weight, height, sw = w_def, h_def, s_def
    v1, l1, h1 = v_def, l_def, hr_def
    
    level_select = "Ambitioniert"
    metrics_t1 = calc_metrics(v1, l1, h1, height, weight, sw)
    metrics_t2 = None

# --- APP RENDERER ---
if metrics_t1:
    full_n = f"{f_name} {l_name}".strip()
    st.markdown(f"""
        <div style='text-align: center; margin-bottom: 25px; padding: 15px; border-bottom: 1px solid #1C1C1E;'>
            <h2 style='color: white; letter-spacing: 5px; margin-bottom: 0;'>// {full_n.upper() if full_n else 'GUEST'} //</h2>
            <p style='color: #00F2FF; font-family: "Orbitron", sans-serif; font-size: 13px; letter-spacing: 2px; margin-top: 8px; opacity: 0.8;'>
                {sport.upper()} | {gender} | {bday}
            </p>
        </div>
    """, unsafe_allow_html=True)
    tabs = st.tabs([t("[ ANALYSE ]", "[ ANALYZE ]"), t("[ ZONEN ]", "[ ZONES ]"), t("[ PROGNOSE ]", "[ FORECAST ]"), t("[ SET CARD ]", "[ SET CARD ]")])

    with tabs[0]: # ANALYSE
        st.markdown(f"### // {t('DEIN IST-ZUSTAND', 'CURRENT STATE')}")
        cols = st.columns(4)
        m_show = [(t("BASE // FATMAX", "BASE // FATMAX"), "fatmax", "KM/H", True), (t("SCHWELLE // iANS", "THRESHOLD // iANS"), "lt2", "KM/H", True), (t("SPEED-TAX", "SPEED-TAX"), "re", "MMOL/KMH", False), (t("VO2MAX (est.)", "VO2MAX (est.)"), "vo2max", "ML/MIN/KG", False)]
        
        for col, (lab, k, unit, show_hf) in zip(cols, m_show):
            val = metrics_t1[k]
            delta = (val - metrics_t2[k]) if metrics_t2 else None
            
            if k == "re": glow_class = "glow-up" if delta and delta < 0 else "glow-down" if delta and delta > 0 else ""
            else: glow_class = "glow-up" if delta and delta > 0 else "glow-down" if delta and delta < 0 else ""
            
            v_disp = f"{int(val)}" if "ML" in unit else f"{val:.2f}"
            delta_html = f'<div class="delta-section {glow_class}">Δ {delta:+.2f}</div>' if delta is not None else ""
            hf_key = "hf_fatmax" if k == "fatmax" else "hf_lt2"
            hf_html = f'<div style="margin-top:8px; color:#FF3131; font-weight:700;">{metrics_t1[hf_key]} <span style="font-size:12px;">BPM</span></div>' if show_hf else ""
            pace_html = f"<span class='uni-pace' style='padding-left:8px;'>{fmt_pace(val)} /KM</span>" if "KM/H" in unit else ""
            
            with col:
                st.markdown(f"""<div class="metric-wrapper"><span style='color:#8E8E93; font-size:13px; font-weight:600;'>{lab}</span><div class='{glow_class}' style='font-size:32px; font-weight:700;'>{v_disp} <span style='font-size:14px;'>{unit}</span></div>{pace_html}{hf_html}{delta_html}</div>""", unsafe_allow_html=True)

        st.divider()
        # --- GRAFIK MIT LEGENDE & ACHSEN ---
        fig, ax = plt.subplots(figsize=(10, 4.2), facecolor='#0A0A0B')
        ax.set_facecolor('#0A0A0B')
        
        # Achsen Beschriftung
        ax.set_xlabel("SPEED (KM/H)", color='#E0E0E0', fontsize=9, fontweight='bold', labelpad=8)
        ax.set_ylabel("LACTATE (MMOL)", color='#FFCC00', fontsize=9, fontweight='bold', labelpad=8)
        ax.tick_params(axis='x', colors='#E0E0E0', labelsize=9)
        ax.tick_params(axis='y', colors='#FFCC00', labelsize=9)
        for spine in ax.spines.values(): spine.set_color('#2C2C2E')

        if metrics_t2: ax.plot(metrics_t2["v_fine"], metrics_t2["l_fine"], '--', color='#6E3CBC', lw=1.5, alpha=0.5, label=t('ARCHIV', 'ARCHIVE'))
        ax.plot(metrics_t1["v_fine"], metrics_t1["l_fine"], '-', color='#FFCC00', lw=2.5, label=t('LIVE', 'LIVE'))
        ax.scatter(metrics_t1["v_orig"], metrics_t1["l_orig"], color='#FF00FF', s=40, edgecolors='white', zorder=6)
        
        # HF Achse
        ax2 = ax.twinx()
        ax2.plot(metrics_t1["v_fine"], metrics_t1["h_fine"], ':', color='#FF3131', alpha=0.6, lw=1.5, label="HF")
        ax2.set_ylabel("HF (BPM)", color='#FF3131', fontsize=9, fontweight='bold', rotation=270, labelpad=15)
        ax2.tick_params(axis='y', colors='#FF3131', labelsize=9)
        ax2.spines['top'].set_visible(False)
        ax2.spines['bottom'].set_visible(False)
        ax2.spines['left'].set_visible(False)
        ax2.spines['right'].set_color('#2C2C2E')

        ax.grid(True, color='#1C1C1E', lw=0.5)
        # Legende
        ax.legend(loc='upper left', frameon=False, labelcolor='#E0E0E0', fontsize=9)
        
        st.pyplot(fig)
        plt.close(fig)
        
        s_val = metrics_t1['slope']
        res_status, res_class = (t("ULTRA STABIL", "ULTRA STABLE"), "res-ultra") if s_val < 0.45 else (t("METABOLISCH RESILIENT", "METABOLIC RESILIENT"), "res-stable") if s_val < 0.75 else (t("STABILITÄTS-LIMIT", "STABILITY LIMIT"), "res-limit") if s_val < 1.1 else (t("KRITISCHER BEREICH", "CRITICAL ZONE"), "res-critical")
        st.markdown(f'<div class="stability-box {res_class}">// {t("METABOLISCHE RESILIENZ", "METABOLIC RESILIENCE")} // <br><span style="font-size:18px; font-weight:700;">{res_status}</span><br><span style="font-size:12px; opacity:0.8;">VECTR-SCORE: {int(metrics_t1["stab"])}%</span></div>', unsafe_allow_html=True)

    with tabs[1]: # ZONEN
        st.markdown(f"### // {t('ZONEN', 'ZONES')}")
        l1, l2, fmax = metrics_t1["lt1"], metrics_t1["lt2"], metrics_t1["fatmax"]
        hf1, hf2, hf_f = metrics_t1["hf_lt1"], metrics_t1["hf_lt2"], metrics_t1["hf_fatmax"]
        
        z_data = [
            ("blue-neon", t("RECOVERY", "RECOVERY"), f"< {fmax*0.9:.1f}", "KM/H", f"< {hf_f-10}"),
            ("green-neon", t("LONG RUN", "LONG RUN"), f"{fmax*0.9:.1f}-{l1:.1f}", "KM/H", f"{hf_f-10}-{hf1}"),
            ("yellow-neon", t("TEMPO", "TEMPO"), f"{l1:.1f}-{l2*0.95:.1f}", "KM/H", f"{hf1}-{int(hf2*0.95)}"),
            ("orange-neon", t("SCHWELLE", "THRESHOLD"), f"{l2*0.95:.1f}-{l2*1.05:.1f}", "KM/H", f"{int(hf2*0.95)}-{int(hf2*1.03)}"),
            ("red-neon", t("HIT", "HIT"), f"> {l2*1.05:.1f}", "KM/H", f"> {int(hf2*1.03)}")
        ]
        
        for cls, n, sp, unit, hf_r in z_data:
            st.markdown(f"""
                <div class="set-card {cls}" style="padding: 12px; min-height: 70px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div style="flex: 1;">
                            <span class="card-title" style="font-size: 11px; margin-bottom: 4px;">{n}</span>
                            <div style="display: flex; align-items: baseline; gap: 4px;">
                                <span style="font-size: 24px; font-weight: 700; color: white; font-family: monospace;">{sp}</span>
                                <span style="font-size: 12px; color: #8E8E93; font-weight: 600;">{unit}</span>
                            </div>
                        </div>
                        <div style="text-align: right; min-width: 80px;">
                            <span style="font-size: 9px; font-weight: 800; color: #FF3131; text-transform: uppercase;">Ziel HF</span>
                            <span style="font-size: 20px; font-weight: 700; color: #FF3131; font-family: monospace; display: block; line-height: 1;">{hf_r}</span>
                            <span style="font-size: 9px; font-weight: 700; color: #FF3131; opacity: 0.8;">BPM</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    with tabs[2]:
        f_d, f_cs, f_dr = (500, 1.02, 0.02) if level_select=="Elite" else (350, 1.0, 0.04) if level_select=="Ambitioniert" else (150, 0.96, 0.08)
        for dist, name in [(5000, "5K SPRINT"), (10000, "10K POWER"), (21097, t("HALBMARATHON", "HALF MARATHON")), (42195, t("MARATHON", "FULL MARATHON"))]:
            v_eff = metrics_t1["lt2"] * f_cs / 3.6
            t_s = (dist-f_d)/v_eff if dist<=10000 else dist/(v_eff*(1-(f_dr*(dist/v_eff/3600/2))))
            st.markdown(f'<div class="set-card blue-neon" style="min-height: auto;"><span class="card-title" style="margin-bottom: 12px;">{name}</span><div style="display: flex; align-items: baseline;"><span class="card-val-big" style="color:#00F2FF;">{fmt_time(t_s)}</span><span class="uni-pace" style="padding-left: 15px;">{fmt_pace((dist/t_s)*3.6)} /KM</span></div></div>', unsafe_allow_html=True)

    with tabs[3]:
        # ORIGINAL TEXTE UND FARBEN
        st.markdown(f"### // {t('VECTR-X // SET CARD', 'VECTR-X // SET CARD')}")
        
        bench_vo2 = get_benchmark_html(metrics_t1['vo2max'], "vo2max", "#FF3131")
        st.markdown(f"""<div class="set-card-tall red-neon"><div class="card-content-split"><div class="card-left"><span class="card-title">{t("MOTOR // VO2MAX (est.)", "VO2MAX // ENGINE (est.)")}</span><div class="val-unit-row"><span class="card-val-big" style="font-size: 48px;">{int(metrics_t1['vo2max'])}</span><span class="card-unit-white">ML/MIN/KG</span></div></div>{bench_vo2}</div><p class="card-expl">{t('Die aerobe Kapazität. Die absolute Basis für deine Performance.', 'Your engine size (estimated). Foundation of your aerobic capacity.')}</p></div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1: 
            bench_fat = get_benchmark_html(metrics_t1['fatmax'], "fatmax", "#34C759")
            st.markdown(f"""<div class="set-card-tall green-neon"><div class="card-content-split"><div class="card-left"><span class="card-title">{t("BASE // FATMAX", "BASE // FATMAX")}</span><div class="val-unit-row"><span class="card-val-big">{metrics_t1['fatmax']:.1f}</span><span class="card-unit-white">KM/H</span></div><span class="uni-pace" style="margin-top:2px;">{fmt_pace(metrics_t1['fatmax'])} /KM</span></div>{bench_fat}</div><p class="card-expl">{t('Dein Flow-Modus. Maximale Energie aus Fettstoffwechsel für endlose Ausdauer.', 'Flow State. Max energy from fat oxidation.')}</p></div>""", unsafe_allow_html=True)
        
        with c2: 
            bench_re = get_benchmark_html(metrics_t1['re'], "re", "#00F2FF")
            st.markdown(f"""<div class="set-card-tall blue-neon"><div class="card-content-split"><div class="card-left"><span class="card-title">{t("SPEED-TAX", "SPEED-TAX")}</span><div class="val-unit-row"><span class="card-val-big">{metrics_t1['re']:.2f}</span><span class="card-unit-white">MMOL/KMH</span></div></div>{bench_re}</div><p class="card-expl">{t('Deine Laktat-Steuer. Der energetische Preis für jedes km/h Beschleunigung.', 'Lactate cost per km/h. Your price for speed.')}</p></div>""", unsafe_allow_html=True)
        
        c3, c4 = st.columns(2)
        with c3: 
            bench_lt2 = get_benchmark_html(metrics_t1['lt2'], "lt2", "#FF9500")
            st.markdown(f"""<div class="set-card-tall orange-neon"><div class="card-content-split"><div class="card-left"><span class="card-title">{t("SCHWELLE // iANS", "THRESHOLD // iANS")}</span><div class="val-unit-row"><span class="card-val-big">{metrics_t1['lt2']:.2f}</span><span class="card-unit-white">KM/H</span></div><span class="uni-pace" style="margin-top:2px;">{fmt_pace(metrics_t1['lt2'])} /KM</span></div>{bench_lt2}</div><p class="card-expl">{t('Dein High-Speed Limit. Maximale Pace für 45-60min kontrollierte Belastung.', "Max sustainable pace. Your metabolic red line.")}</p></div>""", unsafe_allow_html=True)
        
        with c4:
            res_col = "#FFCC00" if metrics_t1['is_stable'] else "#FF3131"
            res_neon = "yellow-neon" if metrics_t1['is_stable'] else "red-neon"
            bench_stab = get_benchmark_html(metrics_t1['stab'], "stab", res_col)
            st.markdown(f"""<div class="set-card-tall {res_neon}"><div class="card-content-split"><div class="card-left"><span class="card-title">{t("METABOLISCHE RESILIENZ", "METABOLIC RESILIENCE")}</span><div class="val-unit-row"><span class="card-val-big">{int(metrics_t1['stab'])}</span><span class="card-unit-white">%</span></div></div>{bench_stab}</div><p class="card-expl">{t('Deine System-Härte. Wie stabil dein Motor läuft, nachdem die Schwelle überschritten hast.', 'System stability under high-speed load.')}</p></div>""", unsafe_allow_html=True)
else:
    st.error("Warten auf Eingabedaten...")
