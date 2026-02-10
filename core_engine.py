import numpy as np

def get_high_end_curve(x, y):
    """ VECTR-X SPLINE ENGINE (Monotone Kubische Spline-Interpolation) """
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

def calc_metrics(v, l, h, height=180, weight=75):
    """ VECTR-X CORE LOGIC V9 - Physiologisch kalibriert """
    if not v or len(v) < 3: return None
    
    v_fine, l_fine = get_high_end_curve(v, l)
    h_fine = np.interp(v_fine, v, h)
    baseline = min(l_fine)
    v_max_test = max(v)
    
    # --- 1. FATMAX (BASE) ---
    fatmax_v = v_fine[np.abs(l_fine - (baseline + 0.4)).argmin()]
    
    # --- 2. SCHWELLE / iANS (THRESHOLD) ---
    # Dynamischer Gradient: Profis puffern Laktat besser, die Kurve knickt später
    # Wir passen den Schwellen-Trigger an die vMax an
    grad_trigger = 0.65 if v_max_test < 16 else 0.85
    grads = np.gradient(l_fine, v_fine)
    
    try:
        idx_curvature = np.where(grads > grad_trigger)[0]
        if len(idx_curvature) > 0:
            lt2_v = v_fine[idx_curvature[0]]
        else:
            lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]
    except:
        lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]
    
    # --- 3. SPEED-TAX (ECONOMY) ---
    l_at_lt2 = np.interp(lt2_v, v_fine, l_fine)
    l_at_fmax = np.interp(fatmax_v, v_fine, l_fine)
    speed_range = lt2_v - fatmax_v
    speed_tax = (l_at_lt2 - l_at_fmax) / max(0.5, speed_range)
    
    # --- 4. METABOLISCHE RESILIENZ (STABILITY) ---
    idx_lt2 = np.searchsorted(v_fine, lt2_v)
    idx_max = len(v_fine) - 1
    if idx_lt2 < idx_max:
        slope_red = (l_fine[idx_max] - l_fine[idx_lt2]) / (v_fine[idx_max] - v_fine[idx_lt2])
    else:
        slope_red = 2.5
    resilience_score = 100 / (1 + (slope_red * 1.5))
    
    # --- 5. VO2MAX PRO (Leger & Mercier + Weight Factor) ---
    # Grund-VO2max nach Speed
    base_vo2 = (3.125 * v_max_test) + 3.5
    # Gewichts-Effizienz: Leichtere Läufer haben oft einen mechanischen Vorteil
    # Referenzgewicht 70kg. Pro 5kg drunter/drüber +/- 1.5% Effizienz
    weight_corr = 1.0 + ((70 - weight) * 0.003)
    rel_vo2max = base_vo2 * weight_corr
    
    # --- 6. PROGNOSEN (Riegel-Logik) ---
    def riegel_predict(v_ref, dist_target, score):
        # k-Faktor (Ausdauer-Exponent) basierend auf Resilience
        # Elite (Score 90+) k=1.05 | Amateur (Score 40) k=1.12
        k = 1.15 - (score / 1000)
        t_ref = 15.0 / v_ref # Zeit für 15km an der Schwelle
        t_target = t_ref * (dist_target / 15.0)**k
        return t_target

    t_hm = riegel_predict(lt2_v, 21.0975, resilience_score)
    t_m = riegel_predict(lt2_v, 42.195, resilience_score)

    return {
        "fatmax": fatmax_v,
        "lt2": lt2_v,
        "vo2max": round(rel_vo2max, 1),
        "re": round(speed_tax, 2),
        "stab": int(resilience_score),
        "is_stable": resilience_score > 60,
        "hm_time": t_hm, # In Dezimalstunden für die Formatierungsfunktion
        "m_time": t_m,
        "v_fine": v_fine, "l_fine": l_fine, "h_fine": h_fine
    }

def format_time(decimal_hours):
    """ Wandelt Dezimalstunden in HH:MM:SS um """
    hours = int(decimal_hours)
    minutes = int((decimal_hours - hours) * 60)
    seconds = int(((decimal_hours - hours) * 60 - minutes) * 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
