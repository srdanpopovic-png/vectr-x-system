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

    # 3. VO2max & VLaMax Logik
    vo2max_est = 3.5 * v_max
    
    # JETZT FUNKTIONIERT ES: Filterung auf Basis des NumPy-Arrays
    post_ias_v = speeds[speeds >= v_ias]
    post_ias_l = lactates[speeds >= v_ias]
    
    if len(post_ias_v) > 1:
        slope = (post_ias_l[-1] - post_ias_l[0]) / (post_ias_v[-1] - post_ias_v[0])
    else:
        # Fallback, falls die Schwelle ganz am Ende der Kurve liegt
        slope = 0.5 
    
    vlamax_score = np.clip((slope * 5) / (v_max / 10), 0.2, 1.0)
    
    # ... Rest der Funktion wie gehabt ...

    # 4. FLUSH RATE™ & Typisierung
    flush_rate = 100 - (vlamax_score * 50)
    if not is_all_out: flush_rate *= 0.9 

    if vlamax_score < 0.45:
        m_type, color, f_factor = "DIESEL / ENDURANCE", "#00F2FF", 0.92
    elif vlamax_score < 0.75:
        m_type, color, f_factor = "HYBRID / ALLROUNDER", "#FFD700", 0.88
    else:
        m_type, color, f_factor = "POWER / SPRINTER", "#FF003C", 0.82

    # 5. FatMax & Riegel Prognose
    v_fatmax = v_ias * f_factor
    hf_ias = int(hr_spline(v_ias))
    hf_fatmax = int(hr_spline(v_fatmax))
    riegel_exponent = 1.06 if vlamax_score < 0.45 else 1.08 if vlamax_score < 0.75 else 1.11

# 6. NEU: LT1 (Aerobe Schwelle) für app_run.py Zeile 310
    ias_lt1 = baseline + 0.5
    v_lt1 = v_range[np.argmin(np.abs(l_range - ias_lt1))]
    hf_lt1 = int(hr_spline(v_lt1))

    # 7. Finaler Return mit allen Brücken (Aliases) für dein Frontend
    return {
        # Core Metrics
        "v_ias": v_ias, "lt2": v_ias,
        "v_lt1": v_lt1, "lt1": v_lt1,
        "l_ias": ias_laktat, "hf_ias": hf_ias, "hf_lt2": hf_ias, "hf_lt1": hf_lt1,
        "vo2max": vo2max_est, "vlamax_val": round(vlamax_score, 2),
        "vlamax_label": m_type, "vlamax_color": color,
        "flush_rate": round(flush_rate, 1), 
        "re": round(flush_rate, 1),        
        "stab": round(flush_rate, 1),      
        "is_stable": flush_rate >= 70,     # <--- FIX für Zeile 369
        "slope": round(slope, 2),    
        "riegel_exp": riegel_exponent,
        
        # Grafik-Daten
        "v_range": v_range, "l_range": l_range,
        "v_fine": v_range, "l_fine": l_range, "h_fine": h_range,          
        "v_orig": speeds, "l_orig": lactates, "h_orig": hr,
        
        # Zonen
        "fatmax": round(v_fatmax, 1), "hf_fatmax": hf_fatmax 
    }
