import numpy as np
from scipy.interpolate import UnivariateSpline

def calculate_metrics(speeds, lactates, hr, v_max, app_type="hybrid", is_all_out=True):
    # FIX: Umwandlung in NumPy-Arrays für mathematische Operationen
    speeds = np.array(speeds)
    lactates = np.array(lactates)
    hr = np.array(hr)
    
    # 1. Splines für Laktat & Herzfrequenz
    # s=0.5 erlaubt eine leichte Glättung der Messfehler
    spline = UnivariateSpline(speeds, lactates, s=0.5)
    hr_spline = UnivariateSpline(speeds, hr, s=0.5)
    
    v_range = np.linspace(speeds[0], speeds[-1], 100)
    l_range = spline(v_range)
    h_range = hr_spline(v_range) 

    # 2. Schwellenberechnung (IAS / LT2)
    baseline = lactates[0]
    ias_laktat = baseline + 1.5
    # .item() stellt sicher, dass wir einen float bekommen, kein 0-d Array
    v_ias = v_range[np.argmin(np.abs(l_range - ias_laktat))].item()

  # 3. VO2max & RADIKALE VLAMAX-ANALYSE (Last-Step-Focus)
    vo2max_est = 3.5 * v_max
    
    # Wir schauen uns explizit die Steigung der LETZTEN BEIDEN Punkte an
    # Das ist der Moment der maximalen Ausbelastung
    if len(speeds) >= 2:
        last_delta_l = lactates[-1] - lactates[-2]
        last_delta_v = speeds[-1] - speeds[-2]
        last_slope = last_delta_l / last_delta_v
        
        # Radikale Sensitivität: Ein Zuwachs von 2 mmol pro km/h (wie bei dir)
        # muss den Score sofort in den Power-Bereich treiben.
        # Wir setzen den Teiler auf 2.5 statt 4.5
        vlamax_score = np.clip(last_slope / 2.5, 0.3, 1.0)
    else:
        vlamax_score = 0.5

# 4. STABILITÄTS-INDEX & SPEZIFISCHE TYPISIERUNG
    stab_val = round(100 - (vlamax_score * 90), 1)
    if not is_all_out: stab_val *= 0.8

    if app_type == "run":
        # --- LOGIK FÜR REINE LÄUFER (RUN APP) ---
        # Läufer müssen ökonomischer sein, daher engere Grenzen
        if vlamax_score < 0.35: 
            m_type, color, f_factor = "DIESEL / ENDURANCE", "#00FF41", 0.96
        elif vlamax_score < 0.52:
            m_type, color, f_factor = "ALLROUNDER", "#FFD700", 0.90
        else:
            m_type, color, f_factor = "SPRINTER / POWER", "#FF003C", 0.82
            
    else:
        # --- LOGIK FÜR HYBRID-ATHLETEN (VECTR-X APP) ---
        # Hyrox braucht mehr anaerobe Kapazität für die Stationen
        if vlamax_score < 0.40: 
            m_type, color, f_factor = "DIESEL / EKONOM", "#00FF41", 0.94
        elif vlamax_score < 0.58:
            m_type, color, f_factor = "HYBRID / ALLROUNDER", "#FFD700", 0.88
        else:
            m_type, color, f_factor = "POWER / SPRINTER", "#FF003C", 0.80
            
    # 5. FatMax & Riegel Prognose
    v_fatmax = v_ias * f_factor
    hf_ias = int(hr_spline(v_ias))
    hf_fatmax = int(hr_spline(v_fatmax))
    riegel_exponent = 1.06 if vlamax_score < 0.48 else 1.08 if vlamax_score < 0.72 else 1.12

    # 6. LT1 (Aerobe Schwelle)
    ias_lt1 = baseline + 0.5
    v_lt1 = v_range[np.argmin(np.abs(l_range - ias_lt1))].item()
    hf_lt1 = int(hr_spline(v_lt1))

# 7. Finaler Return (Maximale Kompatibilität für Björn)
    return {
        # Core & Schwellen
        "v_ias": v_ias, "lt2": v_ias,
        "v_lt1": v_lt1, "lt1": v_lt1,
        "l_ias": ias_laktat, "hf_ias": hf_ias, "hf_lt2": hf_ias, "hf_lt1": hf_lt1,
        "vo2max": vo2max_est, "v_max": v_max,
        
        # Identität & VLaMax (Hier liegen oft die Fehlerquellen)
        "vlamax_val": round(vlamax_score, 2),
        "vlamax_label": m_type,      # "POWER / SPRINTER"
        "vlamax_color": color,       # Das ist der Hex-Code (Rot/Gelb/Grün)
        "color": color,              # Alias falls Björn nur 'color' nutzt
        "m_type": m_type,            # Alias falls Björn nur 'm_type' nutzt
        "slope": round(last_slope, 2),
        
        # Die "Björn-Brücke"
        "flush_rate": stab_val,
        "stab": stab_val,
        "re": stab_val,
        "is_stable": vlamax_score < 0.58, # Synchronisiert mit deinen neuen Grenzen
        
        # Grafik-Daten
        "v_range": v_range, "l_range": l_range,
        "v_fine": v_range, "l_fine": l_range, "h_fine": h_range,           
        "v_orig": speeds, "l_orig": lactates, "h_orig": hr,
        
        # Hyrox-Value
        "fatmax": round(v_fatmax, 1), 
        "hf_fatmax": hf_fatmax,
        "riegel_exp": riegel_exponent
    }
