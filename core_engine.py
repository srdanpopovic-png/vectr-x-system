import numpy as np
from scipy.interpolate import UnivariateSpline
import math

# ==========================================
# MODUL 1: BASIS-DIAGNOSTIK (Dein Original-Code für Streamlit)
# ==========================================
def calculate_metrics(speeds, lactates, hr, v_max, weight=75.0, height=180.0, shoulder_width=45.0, app_type="hybrid", is_all_out=True):
    # FIX: Umwandlung in NumPy-Arrays
    speeds = np.array(speeds)
    lactates = np.array(lactates)
    hr = np.array(hr)
    
    # UPGRADE 1: Idiotensicherung (Zwangssortierung)
    sort_idx = np.argsort(speeds)
    speeds = speeds[sort_idx]
    lactates = lactates[sort_idx]
    hr = hr[sort_idx]
    
    # 1. Splines für Laktat & Herzfrequenz
    spline = UnivariateSpline(speeds, lactates, s=0.5)
    hr_spline = UnivariateSpline(speeds, hr, s=0.5)
    
    v_range = np.linspace(speeds[0], speeds[-1], 100)
    
    # UPGRADE 3: Physikalisches Clipping
    l_range = np.clip(spline(v_range), a_min=0.5, a_max=None)
    h_range = np.clip(hr_spline(v_range), a_min=40.0, a_max=250.0) 

    # 2. Schwellenberechnung (Die "Srdan-Weiche": Dmax vs. Dickhuth)
    min_idx = np.argmin(l_range)
    v_min = v_range[min_idx]
    baseline = l_range[min_idx] 
    
    ias_laktat_dickhuth = baseline + 1.5
    ias_spline = UnivariateSpline(speeds, lactates - ias_laktat_dickhuth, s=0.5)
    ias_roots = ias_spline.roots()
    valid_ias_roots = [r for r in ias_roots if v_min <= r <= speeds[-1]]
    
    if valid_ias_roots:
        v_ias_dickhuth = float(valid_ias_roots[0])
    else:
        v_ias_dickhuth = v_range[np.argmin(np.abs(l_range - ias_laktat_dickhuth))].item()

    v_max_point = speeds[-1]
    l_max_point = l_range[-1]
    
    m = (l_max_point - baseline) / (v_max_point - v_min) if v_max_point != v_min else 0
    b = baseline - m * v_min
    
    valid_indices = np.where(v_range >= v_min)[0]
    v_valid = v_range[valid_indices]
    l_valid = l_range[valid_indices]
    
    dmax_distances = (m * v_valid + b) - l_valid
    best_idx_sub = np.argmax(dmax_distances)
    v_ias_dmax = v_valid[best_idx_sub].item()

    if is_all_out:
        v_ias = round(v_ias_dmax, 2)
        calc_method = "DMAX"
    else:
        v_ias = round(v_ias_dickhuth, 2)
        calc_method = "DICKHUTH (+1.5)"

    ias_laktat = round(spline(v_ias).item(), 2)
    
    # 3. VO2max SCHÄTZUNG 
    v_m_min = v_max * 16.667 
    vo2_base = (0.2 * v_m_min) + 3.5 
    
    height_m = height / 100.0
    shoulder_m = shoulder_width / 100.0
    A = height_m * shoulder_m * 0.75 
    v_ms = v_max / 3.6
    p_aero_watt = 0.5 * 1.2 * 0.9 * A * (v_ms ** 3)
    vo2_aero_total = p_aero_watt * 12.0
    vo2_aero_rel = vo2_aero_total / weight
    vo2max_est = round(vo2_base + vo2_aero_rel, 1)
    
    # --- RADIKALE VLAMAX-ANALYSE ---
    last_slope = 0.0 
    
    if len(speeds) >= 2:
        last_delta_l = lactates[-1] - lactates[-2]
        last_delta_v = speeds[-1] - speeds[-2]
        if last_delta_v != 0:
            last_slope = last_delta_l / last_delta_v
        else:
            last_slope = 0.0
        vlamax_score = np.clip(last_slope / 4.0, 0.3, 1.0)
    else:
        vlamax_score = 0.5
        last_slope = 0.0

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
            
    if app_type == "run":
        riegel_exponent = 1.05 if vlamax_score < 0.35 else 1.07 if vlamax_score < 0.52 else 1.10
    else:
        riegel_exponent = 1.06 if vlamax_score < 0.40 else 1.08 if vlamax_score < 0.58 else 1.12

    v_fatmax = v_ias * f_factor
    hf_ias = int(np.clip(hr_spline(v_ias), 40, 250))
    hf_fatmax = int(np.clip(hr_spline(v_fatmax), 40, 250))

    # 6. LT1 
    ias_lt1 = baseline + 0.5
    lt1_spline = UnivariateSpline(speeds, lactates - ias_lt1, s=0.5)
    lt1_roots = lt1_spline.roots()
    valid_lt1_roots = [r for r in lt1_roots if v_min <= r <= speeds[-1]]
    
    if valid_lt1_roots:
        v_lt1 = float(valid_lt1_roots[0])
    else:
        v_lt1 = v_range[np.argmin(np.abs(l_range - ias_lt1))].item()
        
    hf_lt1 = int(np.clip(hr_spline(v_lt1), 40, 250))
    
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

# ==========================================
# MODUL 2: HYROX ACID BATH (Für Björns API)
# ==========================================
def calculate_acid_bath(weight_kg, bike_watt_avg, lactate_baseline, lactate_peak, lactate_recovery, base_pace_mps):
    power_index = bike_watt_avg / (weight_kg ** 0.67) if weight_kg > 0 else 0.0
    glyco_index = (lactate_peak - lactate_baseline) / power_index if power_index > 0 else 0.0
    flush_rate = ((lactate_peak - lactate_recovery) / lactate_peak) * 100 if lactate_peak > 0 else 0.0
    
    adjustment = 1.0 - (glyco_index * 0.12) + (flush_rate * 0.004)
    rox_pace_mps = min(base_pace_mps * adjustment, base_pace_mps)
    
    chart_data = [
        {"x": "Warmup", "y": lactate_baseline, "type": "point", "label": "Baseline"},
        {"x": "Acid Bath", "y": lactate_peak, "type": "bar", "label": f"{int(bike_watt_avg)}W", "rel_power": round(power_index,1)},
        {"x": "Recovery", "y": lactate_recovery, "type": "point", "label": "Flush Phase"}
    ]
    
    return {
        "status": "success",
        "power_index": round(power_index, 2),
        "glyco_index": round(glyco_index, 3),
        "flush_rate": round(flush_rate, 1),
        "rox_pace_mps": round(rox_pace_mps, 3),
        "rox_pace_min_km": round(16.666 / rox_pace_mps, 2) if rox_pace_mps > 0 else 0.0,
        "chart_data": chart_data
    }

# ==========================================
# DER API ROUTER (Für Björns Vercel App)
# ==========================================
def vectrx_api_handler(payload):
    protocol = payload.get('protocol')
    
    if protocol == 'step_test':
        # Hier bedient sich Björn für den Run-Test
        return calculate_metrics(
            speeds=payload.get('speeds', []),
            lactates=payload.get('lactates', []),
            hr=payload.get('hr', []),
            v_max=float(payload.get('v_max', 0.0)),
            weight=float(payload.get('weight', 75.0)),
            height=float(payload.get('height', 180.0)),
            shoulder_width=float(payload.get('shoulder_width', 45.0)),
            app_type=payload.get('app_type', 'hybrid'),
            is_all_out=payload.get('is_all_out', True)
        )
    elif protocol == 'acid_bath':
        # Hier bedient sich Björn für den Hyrox-Test
        return calculate_acid_bath(
            weight_kg=float(payload.get('weight_kg', 0.0)),
            bike_watt_avg=float(payload.get('bike_watt_avg', 0.0)),
            lactate_baseline=float(payload.get('lactate_baseline', 0.0)),
            lactate_peak=float(payload.get('lactate_peak', 0.0)),
            lactate_recovery=float(payload.get('lactate_recovery', 0.0)),
            base_pace_mps=float(payload.get('base_pace_mps', 0.0))
        )
    else:
        return {"status": "error", "message": "Unknown protocol."}
