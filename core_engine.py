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

    # 2. Schwellenberechnung (Die "Srdan-Weiche": Dmax vs. Dickhuth)
    
    # --- SCHRITT A: Die echte Laktat-Senke (Baseline) finden ---
    # Wir suchen das absolute Minimum auf unserer feinen Spline-Kurve
    min_idx = np.argmin(l_range)
    v_min = v_range[min_idx]
    baseline = l_range[min_idx]  # Der tiefste Punkt, nicht zwingend der erste!
    
    # --- SCHRITT B: Die Dickhuth-Schwelle (Minimum + 1.5) berechnen ---
    ias_laktat_dickhuth = baseline + 1.5
    ias_spline = UnivariateSpline(speeds, lactates - ias_laktat_dickhuth, s=0.5)
    ias_roots = ias_spline.roots()
    valid_ias_roots = [r for r in ias_roots if v_min <= r <= speeds[-1]]
    
    if valid_ias_roots:
        v_ias_dickhuth = float(valid_ias_roots[0])
    else:
        v_ias_dickhuth = v_range[np.argmin(np.abs(l_range - ias_laktat_dickhuth))].item()

    # --- SCHRITT C: Die Modifizierte Dmax-Schwelle berechnen ---
    v_max_point = speeds[-1]
    l_max_point = l_range[-1]
    
    # Lineare Gleichung für das "Seil" zwischen Minimum und Maximum (y = mx + b)
    m = (l_max_point - baseline) / (v_max_point - v_min) if v_max_point != v_min else 0
    b = baseline - m * v_min
    
    # Abstand zwischen Kurve und Seil berechnen (nur für den ansteigenden Teil)
    valid_indices = np.where(v_range >= v_min)[0]
    v_valid = v_range[valid_indices]
    l_valid = l_range[valid_indices]
    
    dmax_distances = (m * v_valid + b) - l_valid
    best_idx_sub = np.argmax(dmax_distances)
    v_ias_dmax = v_valid[best_idx_sub].item()

    # --- SCHRITT D: DIE WEICHE (Entscheidung durch UI-Input) ---
    if is_all_out:
        # Athlet war am Limit -> Individuelle Kurvenform ist verlässlich
        v_ias = round(v_ias_dmax, 2)
        calc_method = "DMAX"
    else:
        # Submaximaler Test -> Dmax wäre fehlerhaft, wir nutzen den sicheren Anker
        v_ias = round(v_ias_dickhuth, 2)
        calc_method = "DICKHUTH (+1.5)"

    # Den dazugehörigen Laktatwert auf der Kurve ablesen
    ias_laktat = round(spline(v_ias).item(), 2)
    
# 3. VO2max & RADIKALE VLAMAX-ANALYSE (Last-Step-Focus)
    vo2max_est = 3.5 * v_max
    last_slope = 0.0  # Sicherheits-Initialisierung
    
    # Wir schauen uns explizit die Steigung der LETZTEN BEIDEN Punkte an
    # Das ist der Moment der maximalen Ausbelastung
    if len(speeds) >= 2:
        last_delta_l = lactates[-1] - lactates[-2]
        last_delta_v = speeds[-1] - speeds[-2]
        
        # Sicherstellen, dass keine Division durch Null passiert
        if last_delta_v != 0:
            last_slope = last_delta_l / last_delta_v
        else:
            last_slope = 0.0
        
        # DIE KALIBRIERUNG: Teiler 4.0 skaliert den Anstieg auf realistische VLaMax-Werte (0.3 - 0.9)
        # Ein Anstieg von 2.0 mmol/l auf der letzten Stufe ergibt exakt 0.5 (Perfekter Allrounder)
        vlamax_score = np.clip(last_slope / 4.0, 0.3, 1.0)
    else:
        # Standardwert, falls zu wenig Daten vorliegen
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

  # 6. LT1 (Aerobe Schwelle) - Jetzt auch basierend auf dem Minimum
    ias_lt1 = baseline + 0.5
    lt1_spline = UnivariateSpline(speeds, lactates - ias_lt1, s=0.5)
    lt1_roots = lt1_spline.roots()
    valid_lt1_roots = [r for r in lt1_roots if v_min <= r <= speeds[-1]]
    
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
