import numpy as np
from scipy.interpolate import UnivariateSpline
import math

# ==========================================
# MODUL 1: BASIS-DIAGNOSTIK (Spline Run)
# ==========================================
def calculate_metrics(speeds, lactates, hr, v_max, weight=75.0, height=180.0, shoulder_width=45.0, app_type="hybrid", is_all_out=True):
    # 1. Input-Sicherung & Längen-Check
    if not speeds or len(speeds) < 4:
        return {"status": "error", "message": "Mindestens 4 Stufen für Spline-Mathematik erforderlich."}
        
    speeds = np.array(speeds, dtype=float)
    lactates = np.array(lactates, dtype=float)
    hr = np.array(hr, dtype=float)
    
    # Sortierung für mathematische Sicherheit
    sort_idx = np.argsort(speeds)
    speeds = speeds[sort_idx]
    lactates = lactates[sort_idx]
    hr = hr[sort_idx]
    
    # 2. Splines & Range
    spline = UnivariateSpline(speeds, lactates, s=0.5)
    hr_spline = UnivariateSpline(speeds, hr, s=0.5)
    v_range = np.linspace(speeds[0], speeds[-1], 100)
    l_range = np.clip(spline(v_range), a_min=0.5, a_max=None)
    
    # 3. LT1 Berechnung (Aerobic Base) - Minimum + 0.5 mmol
    baseline = np.min(l_range)
    ias_lt1_laktat = baseline + 0.5
    idx_lt1 = np.argmin(np.abs(l_range - ias_lt1_laktat))
    v_lt1 = float(v_range[idx_lt1])
    
    # 4. Dmax Berechnung (IAS / Red Line)
    p1 = np.array([v_range[0], l_range[0]])
    p2 = np.array([v_range[-1], l_range[-1]])
    line_vec = p2 - p1
    
    # Verhindert Division durch Null bei flacher Kurve
    if np.linalg.norm(line_vec) == 0:
        return {"status": "error", "message": "Datenpunkte bilden keine auswertbare Kurve."}
        
    line_unit_vec = line_vec / np.linalg.norm(line_vec)
    points = np.vstack((v_range, l_range)).T
    vec_to_points = points - p1
    dist_to_line = np.linalg.norm(vec_to_points - np.outer(np.dot(vec_to_points, line_unit_vec), line_unit_vec), axis=1)
    
    idx_ias = np.argmax(dist_to_line)
    v_ias = float(v_range[idx_ias])
    ias_laktat = float(l_range[idx_ias])
    
    # 5. VO2max Schätzung (Aerodynamik)
    A = (shoulder_width / 100.0) * (height / 100.0) * 0.8
    v_ms = v_ias / 3.6
    cr = 1.0 # Rollwiderstand
    vo2_ml_kg = (0.5 * 1.225 * (v_ms**3) * 1.15 * A + cr * weight * v_ms) / (weight * 0.20)
    
    # 6. VLaMax Proxy (Glyco Power - Steigung der Kurve nach der Schwelle)
    # Simpelster mathematischer Beweis für Explosivität in diesem Modell
    vlamax_proxy = (l_range[-1] - ias_laktat) / (speeds[-1] - v_ias) if speeds[-1] > v_ias else 0.5
    
    return {
        "status": "success",
        "lt1_kmh": round(v_lt1, 2),
        "lt1_pace": round(60 / v_lt1, 2) if v_lt1 > 0 else 0, # min/km dezimal
        "ias_kmh": round(v_ias, 2),
        "ias_pace": round(60 / v_ias, 2) if v_ias > 0 else 0, # min/km dezimal
        "vo2max_est": round(vo2_ml_kg, 1),
        "vlamax_proxy": round(vlamax_proxy, 2)
    }

# ==========================================
# MODUL 2: HYROX ACID BATH
# ==========================================
def calculate_acid_bath(weight_kg, bike_watt_avg, lactate_baseline, lactate_peak, lactate_recovery, base_pace_mps):
    
    # Sicherheits-Divisionen
    power_index = bike_watt_avg / (weight_kg ** 0.67) if weight_kg > 0 else 0.0
    glyco_index = (lactate_peak - lactate_baseline) / power_index if power_index > 0 else 0.0
    flush_rate = ((lactate_peak - lactate_recovery) / lactate_peak) * 100 if lactate_peak > 0 else 0.0
    
    # Adaptive Rox-Pace mit "God-Mode" Cap
    adjustment = 1.0 - (glyco_index * 0.12) + (flush_rate * 0.004)
    rox_pace_mps = base_pace_mps * adjustment
    
    # CAP: Rox-Pace darf niemals schneller sein als die frische Schwelle!
    rox_pace_mps = min(rox_pace_mps, base_pace_mps)
    
    # Chart Data
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
# DER API ROUTER (Bulletproof Type Casting)
# ==========================================
def vectrx_api_handler(payload):
    protocol = payload.get('protocol')
    
    if protocol == 'step_test':
        return calculate_base_diagnostics(
            speeds=payload.get('speeds', []),
            lactates=payload.get('lactates', []),
            hr=payload.get('hr', []),
            v_max=float(payload.get('v_max', 0.0)),
            weight=float(payload.get('weight', 75.0)),
            height=float(payload.get('height', 180.0)),
            shoulder_width=float(payload.get('shoulder_width', 45.0))
        )
    elif protocol == 'acid_bath':
        return calculate_acid_bath(
            weight_kg=float(payload.get('weight_kg', 0.0)),
            bike_watt_avg=float(payload.get('bike_watt_avg', 0.0)),
            lactate_baseline=float(payload.get('lactate_baseline', 0.0)),
            lactate_peak=float(payload.get('lactate_peak', 0.0)),
            lactate_recovery=float(payload.get('lactate_recovery', 0.0)),
            base_pace_mps=float(payload.get('base_pace_mps', 0.0))
        )
    else:
        return {"status": "error", "message": "Unknown protocol. Use 'step_test' or 'acid_bath'."}
