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

   # 3. VO2max & VLaMax Logik (VECTR-X PRECISON UPDATE)
    vo2max_est = 3.5 * v_max
    
    # Filterung der Belastungsstufen oberhalb der Schwelle (v_ias)
    # Wir nehmen einen Puffer von 0.5 km/h vor der Schwelle mit rein
    idx_anaerob = np.where(speeds >= (v_ias - 0.5))[0]
    
    if len(idx_anaerob) >= 2:
        v_ana = speeds[idx_anaerob]
        l_ana = lactates[idx_anaerob]
        # Lineare Regression: Berechnet die reale Steigungsrate des Laktats
        slope, _ = np.polyfit(v_ana, l_ana, 1)
        # VLaMax Score Normalisierung (Zielebereich 0.3 - 0.9)
        # Wir setzen die Steigung ins Verhältnis zur maximal erreichten Speed
        vlamax_score = np.clip(slope / 4.5, 0.25, 0.95)
    else:
        # Fallback auf v_max Relation, falls der Test zu früh abgebrochen wurde
        vlamax_score = np.clip((v_max / 28), 0.4, 0.7)

    # 4. STABILITÄTS-INDEX & METABOLISCHE TYPISIERUNG
    # Hohe VLaMax = hohe Glykolyse = geringere metabolische Stabilität
    stab = round(100 - (vlamax_score * 75), 1)
    is_stable = vlamax_score < 0.68  # Wichtiger Flag für die App-Anzeige

    if vlamax_score < 0.48:
        m_type, color, f_factor = "DIESEL / EKONOM", "#00FF41", 0.92
    elif vlamax_score < 0.72:
        m_type, color, f_factor = "ALLROUNDER / HYBRID", "#FFD700", 0.88
    else:
        m_type, color, f_factor = "POWER / SPRINTER", "#FF003C", 0.82

 # 5. VERFEINERTE PROGNOSE (HYROX vs. RUN)
    # Ermüdungs-Exponent: Diesel (niedrig) bis Sprinter (hoch)
    base_exponent = 1.06 if vlamax_score < 0.48 else 1.08 if vlamax_score < 0.72 else 1.12
    
    # Hyrox-Spezifischer Malus (Zusatz-Ermüdung durch Kraft-Interferenz)
    hyrox_malus = 0.04 
    
    # Hilfsfunktion für die Riegel-Berechnung
    # v2 = v1 * (d2 / d1)^(1 - exponent)
    v_hyrox_8k = v_ias * (8 / 10)**(1 - (base_exponent + hyrox_malus))
    v_run_10k = v_ias * (10 / 10)**(1 - base_exponent) # Entspricht v_ias bei d=10

    # 6. LT1 (Aerobe Schwelle) & FatMax
    ias_lt1 = baseline + 0.5
    v_lt1 = v_range[np.argmin(np.abs(l_range - ias_lt1))].item()
    hf_lt1 = int(hr_spline(v_lt1))
    v_fatmax = v_ias * f_factor
    hf_fatmax = int(hr_spline(v_fatmax))

    # 7. Finaler Return (Alle Brücken für app_run.py)
    return {
        "v_ias": v_ias, "lt2": v_ias,
        "v_lt1": v_lt1, "lt1": v_lt1,
        "l_ias": ias_laktat, "hf_ias": hf_ias, "hf_lt2": hf_ias, "hf_lt1": hf_lt1,
        "vo2max": vo2max_est, "v_max": v_max,
        "vlamax_val": vlamax_score,
        "stab": stab,
        "flush_rate": stab, # Kompatibilität mit altem Frontend
        "is_stable": is_stable,
        "m_type": m_type,
        "color": color,
        "v_fatmax": v_fatmax,
        "hf_fatmax": hf_fatmax,
        "v_hyrox_8k": v_hyrox_8k, 
        "v_run_10k": v_run_10k,
        "riegel_exponent": base_exponent
    }
