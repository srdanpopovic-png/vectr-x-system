import numpy as np
from scipy.interpolate import UnivariateSpline
import math

# ==========================================
# TEIL A: DIE RUNNER-ENGINE (Dmax & Aerodynamik)
# ==========================================
def run_protocol_engine(payload):
    """
    Standard-Lauf-Diagnostik für >= 4 Stufen.
    Nutzt Dmax für die Schwelle und Aerodynamik für VO2max.
    """
    speeds = np.array(payload.get('speeds_kmh', []))
    lactates = np.array(payload.get('lactates_mmol', []))
    heart_rates = np.array(payload.get('heart_rates_bpm', []))
    
    weight = float(payload.get('weight_kg', 75.0))
    height = float(payload.get('height_cm', 180.0))
    shoulder_width = float(payload.get('shoulder_width_cm', 45.0))
    v_max_reached = float(payload.get('v_max_all_out', speeds[-1] if len(speeds) > 0 else 0))

    if len(speeds) < 4:
        return {"status": "error", "message": "Der Lauf-Modus benötigt mindestens 4 Stufen."}

    # Sortierung und Spline-Glättung
    idx = np.argsort(speeds)
    speeds, lactates, heart_rates = speeds[idx], lactates[idx], heart_rates[idx]
    
    l_spline = UnivariateSpline(speeds, lactates, s=0.5)
    hr_spline = UnivariateSpline(speeds, heart_rates, s=0.5)
    
    v_fine = np.linspace(speeds[0], speeds[-1], 100)
    l_fine = np.clip(l_spline(v_fine), 0.5, None)

    # Dmax Berechnung (Geometrische Schwelle)
    v_min, l_min = v_fine[0], l_fine[0]
    v_end, l_end = v_fine[-1], l_fine[-1]
    
    m = (l_end - l_min) / (v_end - v_min) if v_end != v_min else 0
    b = l_min - m * v_min
    distances = (m * v_fine + b) - l_fine
    
    lt2_kmh = round(v_fine[np.argmax(distances)], 2)
    lt2_hr = int(hr_spline(lt2_kmh))

    # VO2max Schätzung (inkl. der "16 km/h Regel" für die Relevanz der Schulterbreite)
    # Frontalfläche A in m^2
    area = (height / 100.0) * (shoulder_width / 100.0) * 0.75 
    p_aero = 0.5 * 1.225 * 0.9 * area * ((v_max_reached / 3.6) ** 3)
    vo2max_est = round(((0.2 * (v_max_reached * 16.667)) + 3.5) + ((p_aero * 12.0) / weight), 1)

    return _generate_output("PURE RUNNER", lt2_kmh, lt2_kmh, lt2_hr, vo2max=vo2max_est)


# ==========================================
# TEIL B: DIE HYBRID-ENGINE (Mader-Sandwich)
# ==========================================
def hyrox_protocol_engine(payload):
    """
    Mader-Heck-Modell für 3 Stufen + Acid Bath (Assault Bike) + Flush.
    """
    weight = float(payload.get('weight_kg', 0))
    speeds = payload.get('speeds_kmh', [])
    lactates = payload.get('lactates_mmol', [])
    heart_rates = payload.get('heart_rates_bpm', [])
    
    if len(speeds) != 3:
        return {"status": "error", "message": "Hyrox-Modus benötigt exakt 3 Stufen."}
    
    # Klartext-Mapping
    s1_v, s2_v, s3_v = speeds[0], speeds[1], speeds[2]
    s1_l, s2_l, s3_l = lactates[0], lactates[1], lactates[2]
    s1_h, s2_h, s3_h = heart_rates[0], heart_rates[1], heart_rates[2]
    
    bike_watt = float(payload.get('bike_watt_avg', 0))
    peak_l = float(payload.get('lactate_peak', 0))
    flush_l = float(payload.get('lactate_flush_recovery', 0))

    # Allometrie & VLaMax Proxy
    allometric_index = bike_watt / (weight ** 0.67) if weight > 0 else 0
    vlamax_proxy = peak_l / allometric_index if allometric_index > 0 else 0.5

    # Algebraische Parabel (3 Punkte Lösung)
    denom = (s1_v - s2_v) * (s1_v - s3_v) * (s2_v - s3_v)
    if denom == 0: return {"status": "error", "message": "Paces ungültig."}
    
    a = (s3_v * (s2_l - s1_l) + s2_v * (s1_l - s3_l) + s1_v * (s3_l - s2_l)) / denom
    b = ((s3_v**2) * (s1_l - s2_l) + (s2_v**2) * (s3_l - s1_l) + (s1_v**2) * (s2_l - s3_l)) / denom
    c = (s2_v * s3_v * (s2_v - s3_v) * s1_l + s3_v * s1_v * (s3_v - s1_v) * s2_l + s1_v * s2_v * (s1_v - s2_v) * s3_l) / denom

    # Mader-Schwelle (+1.5 mmol über Baseline)
    target_l = s1_l + 1.5
    disc = (b**2) - (4 * a * (c - target_l))
    raw_lt2_kmh = (-b + math.sqrt(disc)) / (2 * a) if disc >= 0 else s2_v

    # VLaMax Shift & Flush Validierung
    final_kmh = raw_lt2_kmh * (1.0 - (vlamax_proxy * 0.1))
    final_kmh *= 1.02 if (peak_l - flush_l) > 0 else 0.95

    # Puls Interpolation
    hr_slope = (s3_h - s2_h) / (s3_v - s2_v)
    lt2_hr = int(s2_h + hr_slope * (final_kmh - s2_v))

    m_type = "TURBO / POWER" if vlamax_proxy > 0.4 else "DIESEL / ENDURANCE"
    return _generate_output(m_type, raw_lt2_kmh, final_kmh, lt2_hr)


# ==========================================
# HILFSFUNKTIONEN
# ==========================================
def _generate_output(m_type, raw_lt2, final_v, lt2_hr, vo2max=None):
    def fmt_p(v):
        s = int((60/v)*60) if v > 0 else 0
        return f"{s // 60}:{s % 60:02d}"
    
    res = {
        "metabolic_type": m_type,
        "raw_lt2_kmh": round(raw_lt2, 2),
        "final_pace_kmh": round(final_v, 2),
        "target_pace_min_km": fmt_p(final_v),
        "lt2_heart_rate": lt2_hr,
        "zones": [
            {"name": "ZONE-1 | RECOVERY",  "pace": fmt_p(final_v * 0.75), "hr": f"<{int(lt2_hr * 0.80)}"},
            {"name": "ZONE-2 | ENDURANCE", "pace": fmt_p(final_v * 0.85), "hr": f"{int(lt2_hr * 0.80)}-{int(lt2_hr * 0.89)}"},
            {"name": "ZONE-3 | TEMPO",     "pace": fmt_p(final_v * 0.93), "hr": f"{int(lt2_hr * 0.90)}-{int(lt2_hr * 0.94)}"},
            {"name": "ZONE-4 | THRESHOLD", "pace": fmt_p(final_v),        "hr": f"{int(lt2_hr * 0.95)}-{int(lt2_hr * 1.00)}"},
            {"name": "ZONE-5 | MAX",       "pace": fmt_p(final_v * 1.05), "hr": f">{int(lt2_hr * 1.00)}"}
        ]
    }
    if vo2max: res["vo2max_estimate"] = vo2max
    return res

def vectrx_api_handler(payload):
    protocol = payload.get('protocol', 'hyrox')
    if protocol == 'run':
        return run_protocol_engine(payload)
    return hyrox_protocol_engine(payload)
