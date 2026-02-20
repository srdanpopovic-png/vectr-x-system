import numpy as np
from scipy.interpolate import UnivariateSpline

def calculate_metrics(speeds, lactates, hr, v_max, is_all_out=True):
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

  # 3. VO2max & PRÄZISIONS-VLAMAX (Regression statt 2-Punkt-Messung)
    vo2max_est = 3.5 * v_max
    
    # Wir isolieren die Stufen ab der Schwelle für die anaerobe Steigung
    idx_anaerob = np.where(speeds >= (v_ias - 0.5))[0]
    
    if len(idx_anaerob) >= 2:
        v_ana = speeds[idx_anaerob]
        l_ana = lactates[idx_anaerob]
        # Lineare Regression für die reale Laktat-Zuwachsrate
        slope, _ = np.polyfit(v_ana, l_ana, 1)
        # Normierung: Ein Slope von ca. 4.5 mmol/kmh entspricht hoher VLaMax
        vlamax_score = np.clip(slope / 4.5, 0.25, 0.95)
    else:
        slope = 0.5
        vlamax_score = np.clip((v_max / 28), 0.4, 0.7)

    # 4. STABILITÄTS-INDEX (Ehemals Flush Rate) & Typisierung
    stab_val = round(100 - (vlamax_score * 75), 1)
    if not is_all_out: stab_val *= 0.9

    if vlamax_score < 0.48:
        m_type, color, f_factor = "DIESEL / EKONOM", "#00FF41", 0.92
    elif vlamax_score < 0.72:
        m_type, color, f_factor = "HYBRID / ALLROUNDER", "#FFD700", 0.88
    else:
        m_type, color, f_factor = "POWER / SPRINTER", "#FF003C", 0.82

    # 5. FatMax & Riegel Prognose
    v_fatmax = v_ias * f_factor
    hf_ias = int(hr_spline(v_ias))
    hf_fatmax = int(hr_spline(v_fatmax))
    riegel_exponent = 1.06 if vlamax_score < 0.48 else 1.08 if vlamax_score < 0.72 else 1.12

    # 6. LT1 (Aerobe Schwelle)
    ias_lt1 = baseline + 0.5
    v_lt1 = v_range[np.argmin(np.abs(l_range - ias_lt1))].item()
    hf_lt1 = int(hr_spline(v_lt1))

    # 7. Finaler Return (Voll kompatibel mit app_run.py)
    return {
        "v_ias": v_ias, "lt2": v_ias,
        "v_lt1": v_lt1, "lt1": v_lt1,
        "l_ias": ias_laktat, "hf_ias": hf_ias, "hf_lt2": hf_ias, "hf_lt1": hf_lt1,
        "vo2max": vo2max_est, "vlamax_val": round(vlamax_score, 2),
        "vlamax_label": m_type, "vlamax_color": color,
        "flush_rate": stab_val, 
        "re": stab_val,        
        "stab": stab_val,      
        "is_stable": vlamax_score < 0.68,
        "slope": round(slope, 2),    
        "riegel_exp": riegel_exponent,
        "v_range": v_range, "l_range": l_range,
        "v_fine": v_range, "l_fine": l_range, "h_fine": h_range,           
        "v_orig": speeds, "l_orig": lactates, "h_orig": hr,
        "fatmax": round(v_fatmax, 1), "hf_fatmax": hf_fatmax 
    }
