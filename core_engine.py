import numpy as np

def get_high_end_curve(x, y):
    """ 
    VECTR-X SPLINE ENGINE
    Monotone Kubische Spline-Interpolation.
    Verhindert das 'Oszillieren' der Kurve zwischen Messpunkten.
    """
    x, y = np.array(x, dtype=float), np.array(y, dtype=float)
    n = len(x)
    dx, dy = np.diff(x), np.diff(y)
    m = dy / dx
    d = np.zeros(n)
    for i in range(1, n-1):
        if m[i-1]*m[i] <= 0: d[i] = 0
        else:
            w1, w2 = 2*dx[i] + dx[i-1], dx[i] + 2*dx[i-1]
            d[i] = (w1 + w2) / (w1/m[i-1] + w2/m[i])
    d[0], d[-1] = m[0], m[-1]
    
    # 500 Punkte für maximale "Smoothness" in der Grafik
    x_fine = np.linspace(x[0], x[-1], 500)
    y_fine = []
    for xi in x_fine:
        if xi == x[-1]: y_fine.append(y[-1]); continue
        idx = np.searchsorted(x, xi) - 1
        h = x[idx+1] - x[idx]
        t_val = (xi - x[idx]) / h
        val = (y[idx]*(1+2*t_val)*(1-t_val)**2 + h*d[idx]*t_val*(1-t_val)**2 + 
               y[idx+1]*t_val**2*(3-2*t_val) + h*d[idx+1]*t_val**2*(t_val-1))
        y_fine.append(val)
    return x_fine, np.array(y_fine)

def calc_metrics(v, l, h, height=180, weight=75, sw=False):
    """
    VECTR-X CORE LOGIC
    Berechnet: FatMax, iANS, Speed-Tax und Metabolische Resilienz
    """
    if not v or len(v) < 3: return None
    
    # 1. Kurvenfitting
    v_fine, l_fine = get_high_end_curve(v, l)
    h_fine = np.interp(v_fine, v, h)
    
    # Basis-Laktat (Minimum der Kurve)
    baseline = min(l_fine)
    
    # --- STATION 1: FATMAX (BASE) ---
    # Definition: Erster Anstieg um +0.3 bis +0.5 mmol über Baseline
    # Wir nehmen +0.4 als robusten Mittelwert für "Base Core"
    fatmax_v = v_fine[np.abs(l_fine - (baseline + 0.4)).argmin()]
    if fatmax_v < min(v): fatmax_v = min(v)
    
    # --- STATION 2: SCHWELLE / iANS (THRESHOLD) ---
    # Wir suchen den Punkt, wo die Kurve "bricht" (Gradient wird steil).
    grads = np.gradient(l_fine, v_fine)
    try:
        # Suche nach dem Punkt, wo der Anstieg signifikant wird (> 0.6 mmol/l pro km/h)
        # und weit genug vom Start entfernt ist.
        idx_curvature = np.where(grads > 0.60)[0]
        
        if len(idx_curvature) > 0:
            # Nimm den ersten Punkt, der diese Steilheit erreicht
            lt2_v = v_fine[idx_curvature[0]]
        else:
            raise ValueError("Kein klarer Anstieg gefunden")
            
        # Sicherheits-Check: Schwelle muss signifikant über FatMax liegen
        if lt2_v <= fatmax_v + 1.0:
            # Fallback auf klassisches Modell: Baseline + 1.5 mmol
            lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]
            
    except:
        # Fallback bei unsauberen Daten: Baseline + 1.5 mmol (Dickhuth-Proxy)
        lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]
    
    # --- STATION 3: SPEED-TAX (EFFICIENCY) ---
    # Kostenberechnung: (Laktat an Schwelle - Laktat an Base) / (Speed an Schwelle - Speed an Base)
    l_at_lt2 = np.interp(lt2_v, v_fine, l_fine)
    l_at_fmax = np.interp(fatmax_v, v_fine, l_fine)
    
    speed_range = lt2_v - fatmax_v
    if speed_range > 0.5: # Division durch Null verhindern
        speed_tax = (l_at_lt2 - l_at_fmax) / speed_range
    else:
        speed_tax = 0.0 # Sollte physiologisch nicht passieren
    
    # --- STATION 4: METABOLISCHE RESILIENZ (REALITY CHECK) ---
    # Wie verhält sich das System NACH der Schwelle?
    # Wir messen den Gradienten zwischen Schwelle und Abbruch.
    idx_lt2 = np.searchsorted(v_fine, lt2_v)
    idx_max = len(v_fine) - 1
    
    if idx_lt2 < idx_max:
        d_lac_red = l_fine[idx_max] - l_fine[idx_lt2]
        d_spd_red = v_fine[idx_max] - v_fine[idx_lt2]
        if d_spd_red > 0.1:
            slope_red = d_lac_red / d_spd_red
        else:
            slope_red = 3.0 # Penalty für sofortigen Abbruch
    else:
        slope_red = 3.0 # Penalty
        
    # DIE NEUE FORMEL (Hyperbolischer Zerfall)
    # Score = 100 / (1 + (k * slope))
    # k = 1.5 (Härtefaktor)
    # Slope 0.2 -> Score 77 (Elite)
    # Slope 1.0 -> Score 40 (Amateur)
    resilience_score = 100 / (1 + (slope_red * 1.5))
    
    # --- STATION 5: VO2MAX (ENGINE ESTIMATE) ---
    # ACSM Formel für Laufen: VO2 = 3.5 + (0.2 * Speed_m_min) + Grade...
    # Vereinfacht für Flachland: ca. 3.5 * Speed_kmh
    # Wir machen es etwas präziser für Läufer:
    v_max = max(v)
    rel_vo2max = (v_max * 3.5) # Klassische Approximation
    
    # --- RETURN DICT ---
    return {
        "fatmax": fatmax_v, 
        "lt1": fatmax_v, # Legacy Support
        "lt2": lt2_v,
        
        "hf_fatmax": int(np.interp(fatmax_v, v_fine, h_fine)),
        "hf_lt1": int(np.interp(fatmax_v, v_fine, h_fine)),
        "hf_lt2": int(np.interp(lt2_v, v_fine, h_fine)),
        
        # Die neuen VECTR-X Metriken
        "re": round(speed_tax, 2), # SPEED-TAX
        "slope": round(slope_red, 2), # Der reine Gradient (für Debugging)
        "stab": int(resilience_score), # Der Score (0-100)
        "is_stable": resilience_score > 60, # Grenzwert für "Gelb" (war vorher 70, jetzt härter -> 60 ist ok)
        
        "vo2max": rel_vo2max,
        "v_vo2max": v_max,
        
        # Grafik-Daten
        "v_fine": v_fine, "l_fine": l_fine, "h_fine": h_fine,
        "v_orig": np.array(v), "l_orig": np.array(l),
        
        # Biometrie
        "frontal_area": 0.029 * (height**0.725) * (weight**0.425) / 100
    }