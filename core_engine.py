import numpy as np

def get_high_end_curve(x, y):
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

def calc_metrics(v, l, h, height=180, weight=75, sw=False, level="Ambitioniert"):
    """ VECTR-X CORE LOGIC V12 - ELITE STABLE """
    if not v or len(v) < 3: return None
    
    v_fine, l_fine = get_high_end_curve(v, l)
    h_fine = np.interp(v_fine, v, h)
    baseline = min(l_fine)
    v_max = max(v)
    
    # --- STATION 1: FATMAX ---
    fatmax_v = v_fine[np.abs(l_fine - (baseline + 0.4)).argmin()]
    if fatmax_v < min(v): fatmax_v = min(v)
    
    # --- STATION 2: SCHWELLE / iANS (ELITE LOGIC) ---
    if level == "Elite":
        # Für Elite ignorieren wir Gradienten-Rauschen und suchen den Power-Punkt
        lt2_v = v_fine[np.abs(l_fine - (baseline + 1.85)).argmin()]
    else:
        grads = np.gradient(l_fine, v_fine)
        try:
            idx_curvature = np.where(grads > 0.60)[0]
            if len(idx_curvature) > 0:
                lt2_v = v_fine[idx_curvature[0]]
            else:
                lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]
        except:
            lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]
    
    # Sicherstellen, dass LT2 > FatMax
    if lt2_v <= fatmax_v + 0.5:
        lt2_v = v_fine[np.abs(l_fine - (baseline + 1.5)).argmin()]

    # --- STATION 3: SPEED-TAX ---
    l_at_lt2 = np.interp(lt2_v, v_fine, l_fine)
    l_at_fmax = np.interp(fatmax_v, v_fine, l_fine)
    speed_range = lt2_v - fatmax_v
    speed_tax = (l_at_lt2 - l_at_fmax) / speed_range if speed_range > 0.5 else 0.0
    
    # --- STATION 4: RESILIENZ ---
    idx_lt2 = np.searchsorted(v_fine, lt2_v)
    idx_max = len(v_fine) - 1
    if idx_lt2 < idx_max:
        d_lac_red, d_spd_red = l_fine[idx_max] - l_fine[idx_lt2], v_fine[idx_max] - v_fine[idx_lt2]
        slope_red = d_lac_red / d_spd_red if d_spd_red > 0.1 else 3.0
    else:
        slope_red = 3.0
    resilience_score = 100 / (1 + (slope_red * 1.5))
    
    # --- STATION 5: VO2MAX ---
    weight_corr = 1.0 + ((70 - weight) * 0.007) 
    rel_vo2max = ((3.125 * v_max) + 3.5) * weight_corr
    
    # --- STATION 6: RACE PROJECTION (ELITE HYBRID) ---
    # k-Faktor Korrektur
    k_factor = 1.055 if level == "Elite" else (1.13 - (resilience_score / 800))
    
    t_ref_15k = (15.0 / lt2_v) 
    hm_time = t_ref_15k * (21.0975 / 15.0)**k_factor
    m_time = hm_time * 2.11 # Elite Faktor

    # --- RETURN DICT ---
    return {
        "fatmax": fatmax_v, "lt1": fatmax_v, "lt2": lt2_v,
        "hf_fatmax": int(np.interp(fatmax_v, v_fine, h_fine)),
        "hf_lt1": int(np.interp(fatmax_v, v_fine, h_fine)),
        "hf_lt2": int(np.interp(lt2_v, v_fine, h_fine)),
        "re": round(speed_tax, 2),
        "slope": round(slope_red, 2),
        "stab": int(resilience_score),
        "is_stable": resilience_score > 60,
        "vo2max": round(rel_vo2max, 1),
        "v_vo2max": v_max,
        "hm_time": hm_time,
        "m_time": m_time,
        "v_fine": v_fine, "l_fine": l_fine, "h_fine": h_fine,
        "v_orig": np.array(v), "l_orig": np.array(l),
        "frontal_area": 0.029 * (height**0.725) * (weight**0.425) / 100
    }
