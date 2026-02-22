import numpy as np
from scipy.interpolate import UnivariateSpline
import math

# ==========================================
# MODUL 1: BASIS-DIAGNOSTIK (Dein Original-Code)
# ==========================================
def calculate_base_diagnostics(speeds, lactates, hr, v_max, weight=75.0, height=180.0, shoulder_width=45.0, app_type="hybrid", is_all_out=True):
    """
    Klassischer Stufentest mit Spline-Interpolation und Dmax-Modell.
    Optimiert für Marathonis und Basis-Pacing.
    """
    speeds = np.array(speeds)
    lactates = np.array(lactates)
    hr = np.array(hr)
    
    # Sortierung für mathematische Sicherheit
    sort_idx = np.argsort(speeds)
    speeds = speeds[sort_idx]
    lactates = lactates[sort_idx]
    hr = hr[sort_idx]
    
    # Splines & Range
    spline = UnivariateSpline(speeds, lactates, s=0.5)
    hr_spline = UnivariateSpline(speeds, hr, s=0.5)
    v_range = np.linspace(speeds[0], speeds[-1], 100)
    l_range = np.clip(spline(v_range), a_min=0.5, a_max=None)
    
    # Dmax Berechnung (vereinfacht für diesen Block)
    p1 = np.array([v_range[0], l_range[0]])
    p2 = np.array([v_range[-1], l_range[-1]])
    line_vec = p2 - p1
    line_unit_vec = line_vec / np.linalg.norm(line_vec)
    
    points = np.vstack((v_range, l_range)).T
    vec_to_points = points - p1
    dist_to_line = np.linalg.norm(vec_to_points - np.outer(np.dot(vec_to_points, line_unit_vec), line_unit_vec), axis=1)
    
    idx_ias = np.argmax(dist_to_line)
    v_ias = float(v_range[idx_ias])
    ias_laktat = float(l_range[idx_ias])
    hf_ias = int(np.clip(hr_spline(v_ias), 40, 250))
    
    # VO2max Schätzung (Srdan-Spezial: Aerodynamik)
    # Fläche A in m^2
    A = (shoulder_width / 100.0) * (height / 100.0) * 0.8
    v_ms = v_ias / 3.6
    cr = 1.0 # Rollwiderstand-Äquivalent Laufen
    # VO2 = (Luftwiderstand + Rollwiderstand) / Wirkungsgrad
    vo2_ml_kg = (0.5 * 1.225 * v_ms**3 * 1.15 * A + cr * weight * v_ms) / (weight * 0.20)
    
    return {
        "status": "success",
        "v_ias": round(v_ias, 2),
        "hf_ias": hf_ias,
        "l_ias": round(ias_laktat, 1),
        "vo2max_est": round(vo2_ml_kg, 1),
        "zones": {
            "recovery": round(v_ias * 0.70, 2),
            "base": round(v_ias * 0.85, 2),
            "threshold": round(v_ias, 2)
        }
    }

# ==========================================
# MODUL 2: HYROX ACID BATH (Neue Logik)
# ==========================================
def calculate_acid_bath(weight_kg, bike_watt_avg, lactate_baseline, lactate_peak, lactate_recovery, base_pace_mps):
    """
    Berechnet Allometrie, Flush Rate und Rox-Pace.
    Generiert Chart-Daten für das Frontend (Balken & Kurven).
    """
    # 1. Kraft & Stoffwechsel
    power_index = bike_watt_avg / (weight_kg ** 0.67) if weight_kg > 0 else 0
    glyco_index = (lactate_peak - lactate_baseline) / power_index if power_index > 0 else 0
    flush_rate = ((lactate_peak - lactate_recovery) / lactate_peak) * 100 if lactate_peak > 0 else 0
    
    # 2. Adaptive Rox-Pace (Penalty/Bonus System)
    # Ein hoher Glyco-Index (Säure-Monster) bekommt Abzug, hohe Flush Rate gibt Bonus
    adjustment = 1.0 - (glyco_index * 0.12) + (flush_rate * 0.004)
    rox_pace_mps = base_pace_mps * adjustment
    
    # 3. UI Chart Data (Dein Balken-Modell)
    # x=Zeit/Phase, y=Laktat
    chart_data = [
        {"x": "Warmup", "y": lactate_baseline, "type": "point", "label": "Baseline"},
        {"x": "Acid Bath", "y": lactate_peak, "type": "bar", "label": f"{int(bike_watt_avg)}W", "rel_power": round(power_index,1)},
        {"x": "Recovery", "y": lactate_recovery, "type": "point", "label": "Flush Phase"}
    ]
    
    return {
        "status": "success",
        "power_index": round(power_index, 2),
        "flush_rate": round(flush_rate, 1),
        "rox_pace_mps": round(rox_pace_mps, 3),
        "rox_pace_min_km": round(16.666 / rox_pace_mps, 2) if rox_pace_mps > 0 else 0,
        "chart_data": chart_data
    }

# ==========================================
# DER API ROUTER (Björns Anlaufstelle)
# ==========================================
def vectrx_api_handler(payload):
    protocol = payload.get('protocol')
    
    if protocol == 'step_test':
        return calculate_base_diagnostics(
            speeds=payload.get('speeds'),
            lactates=payload.get('lactates'),
            hr=payload.get('hr'),
            v_max=payload.get('v_max'),
            weight=payload.get('weight', 75.0),
            height=payload.get('height', 180.0),
            shoulder_width=payload.get('shoulder_width', 45.0)
        )
    elif protocol == 'acid_bath':
        return calculate_acid_bath(
            weight_kg=payload.get('weight_kg'),
            bike_watt_avg=payload.get('bike_watt_avg'),
            lactate_baseline=payload.get('lactate_baseline'),
            lactate_peak=payload.get('lactate_peak'),
            lactate_recovery=payload.get('lactate_recovery'),
            base_pace_mps=payload.get('base_pace_mps')
        )
    else:
        return {"status": "error", "message": "Unknown protocol"}
