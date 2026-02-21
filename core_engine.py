import numpy as np
from scipy.interpolate import UnivariateSpline

def calculate_metrics(speeds, lactates, hr, v_max, app_type="hybrid", is_all_out=True):
    # FIX: Umwandlung in NumPy-Arrays
    speeds = np.array(speeds)
    lactates = np.array(lactates)
    hr = np.array(hr)
    
    # UPGRADE 1: Idiotensicherung (Zwangssortierung)
    # Garantiert, dass die X-Achse strikt aufsteigend ist, egal wie der User tippt
    sort_idx = np.argsort(speeds)
    speeds = speeds[sort_idx]
    lactates = lactates[sort_idx]
    hr = hr[sort_idx]
    
    # 1. Splines für Laktat & Herzfrequenz
    spline = UnivariateSpline(speeds, lactates, s=0.5)
    hr_spline = UnivariateSpline(speeds, hr, s=0.5)
    
    v_range = np.linspace(speeds[0], speeds[-1], 100)
    
    # UPGRADE 3: Physikalisches Clipping
    # Verhindert, dass die mathematische Glättung in negative oder absurde Werte abrutscht
    l_range = np.clip(spline(v_range), a_min=0.5, a_max=None)
    h_range = np.clip(hr_spline(v_range), a_min=40.0, a_max=250.0) 

    # 2. Schwellenberechnung (IAS / LT2)
    baseline = lactates[0]
    ias_laktat = baseline + 1.5
    
    # UPGRADE 2: Mathematische Finesse (Exakte Nullstellensuche statt Annäherung)
    # Wir verschieben die Kurve nach unten und suchen den exakten X-Schnittpunkt
    ias_spline = UnivariateSpline(speeds, lactates - ias_laktat, s=0.5)
    ias_roots = ias_spline.roots()
    # Nur Schnittpunkte im gemessenen Geschwindigkeitsbereich zulassen
    valid_ias_roots = [r for r in ias_roots if speeds[0] <= r <= speeds[-1]]
    
    if valid_ias_roots:
        v_ias = float(valid_ias_roots[0])  # Der exakte Punkt
    else:
        # Fallback, falls die Kurve den Wert nie trifft
        v_ias = v_range[np.argmin(np.abs(l_range - ias_laktat))].item()

    # 3. VO2max & RADIKALE VLAMAX-ANALYSE (Last-Step-Focus)
    vo2max_est = 3.5 * v_max
    last_slope = 0.0  # Sicherheits-Initialisierung
    
    if len(speeds) >= 2:
        last_delta_l = lactates[-1] - lactates[-2]
        last_delta_v = speeds[-1] - speeds[-2]
        
        if last_delta_v != 0:
            last_slope = last_delta_l / last_delta_v
        else:
            last_slope = 0.0
        
        vlamax_score = np.clip(last_slope / 2.5, 0.3, 1.0)
    else:
        vlamax_score = 0.5
        last_slope = 0.0

    # 4. STABILITÄTS-INDEX & SPEZIFISCHE TYPISIERUNG
    stab_val = round(100 - (vlamax_score * 90), 1)
    if not is_all_out: stab_val *= 0.8

    if app_type == "run":
        if vlamax_score < 0.35: 
            m_type, color, f_factor = "DIESEL / ENDURANCE", "#00FF41", 0.96
        elif vlamax_score < 0.52:
            m_type, color, f_factor = "ALLROUNDER", "#FFD700", 0.90
        else:
            m_type, color, f_factor = "SPRINTER / POWER", "#FF003C", 0.82
    else:
        if vlamax_score < 0.40: 
            m_type, color, f_factor = "DIESEL / EKONOM", "#00FF41", 0.94
        elif vlamax_score < 0.58:
            m_type, color, f_factor = "HYBRID / ALLROUNDER", "#FFD700", 0.88
        else:
            m_type, color, f_factor = "POWER / SPRINTER", "#FF003C", 0.80
            
    # 5. Spezifische FatMax & Riegel Prognose (Differenziert nach Sportart)
    if app_type == "run":
        riegel_exponent = 1.05 if vlamax_score < 0.35 else 1.07 if vlamax_score < 0.52 else 1.10
    else:
        riegel_exponent = 1.06 if vlamax_score < 0.40 else 1.08 if vlamax_score < 0.58 else 1.12

    v_fatmax = v_ias * f_factor
    
    # HF absichern, falls die Kurve wilde Dinge tut
    hf_ias = int(np.clip(hr_spline(v_ias), 40, 250))
    hf_fatmax = int(np.clip(hr_spline(v_fatmax), 40, 250))

    # 6. LT1 (Aerobe Schwelle) - Ebenfalls mit exakter Nullstellensuche
    ias_lt1 = baseline + 0.5
    lt1_spline = UnivariateSpline(speeds, lactates - ias_lt1, s=0.5)
    lt1_roots = lt1_spline.roots()
    valid_lt1_roots = [r for r in lt1_roots if speeds[0] <= r <= speeds[-1]]
    
    if valid_lt1_roots:
        v_lt1 = float(valid_lt1_roots[0])
    else:
        v_lt1 = v_range[np.argmin(np.abs(l_range - ias_lt1))].item()
        
    hf_lt1 = int(np.clip(hr_spline(v_lt1), 40, 250))

    # 7. Finaler Return
    return {
        "v_ias": v_ias, "lt2": v_ias,
        "v_lt1": v_lt1, "lt1": v_lt1,
        "l_ias": ias_laktat, "hf_ias": hf_ias, "hf_lt2": hf_ias, "hf_lt1": hf_lt1,
        "vo2max": vo2max_est, "v_max": v_max,
        "vlamax_val": round(vlamax_score, 2),
        "vlamax_label": m_type,
        "vlamax_color": color,
        "color": color,
        "m_type": m_type,
        "slope": round(last_slope, 2),
        "flush_rate": stab_val,
        "stab": stab_val,
        "re": stab_val,
        "is_stable": vlamax_score < 0.58,
        "v_range": v_range, "l_range": l_range,
        "v_fine": v_range, "l_fine": l_range, "h_fine": h_range,           
        "v_orig": speeds, "l_orig": lactates, "h_orig": hr,
        "fatmax": round(v_fatmax, 1), 
        "hf_fatmax": hf_fatmax,
        "riegel_exp": riegel_exponent
    }
