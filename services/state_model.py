"""
Coupled State Model - Physiology-Terrain Coupling Algorithm
Based on the business plan's "Physical-Terrain" coupling model.

State variables:
- M: Muscle state (0-150, 100=rested)
- C: Cardiovascular state (0-100, 50=rested)
- G: Glycogen reserve (grams, ~400g full)

Key equations:
- dM/dt = -alpha * grade * k_surface * (150-M)/150 - eta * (M-50)
- dC/dt = beta * (HR - LTHR) * (1 + alt/5000) + lambda * effective_grade
- dG/dt = -gamma * P/efficiency * H(t>3600)
"""
import math
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class PhysioState:
    """Physiological state at a point in time."""
    M: float      # Muscle state (0-150, 100=rested, <50=fatigued)
    C: float      # Cardiovascular state (0-100, 50=rested, >75=stress)
    G: float      # Glycogen (grams, 400=full, <100=low)
    
    def __post_init__(self):
        self.M = max(0, min(150, self.M))
        self.C = max(0, min(100, self.C))
        self.G = max(0, self.G)


class CoupledStateModel:
    """Physiology-Terrain coupled state evolution model."""
    
    # Calibrated parameters for realistic trail running
    ALPHA = 0.008      # Terrain fatigue coefficient (increased for stronger effect)
    BETA = 0.006       # Cardiovascular stress coefficient
    GAMMA = 0.008      # Glycogen consumption coefficient
    ETA = 0.003        # Fatigue accumulation coefficient
    LAMBDA = 0.006     # Bidirectional coupling coefficient
    
    def __init__(self, 
                 vo2max: float = 50,
                 max_hr: int = 185,
                 weight_kg: float = 68,
                 age: int = 25):
        self.vo2max = vo2max
        self.max_hr = max_hr
        self.weight_kg = weight_kg
        self.age = age
        self.lthr = int(max_hr * 0.87)  # Lactate threshold HR
        
    def simulate(self, points: List[Dict], segments: List[Any]) -> List[Dict]:
        """Simulate physiological state evolution along the route."""
        state = PhysioState(M=100, C=50, G=400)
        predictions = []
        
        for seg in segments:
            pace_min_per_km = self._estimate_pace(seg.avg_grade, state)
            duration_min = seg.length_km * pace_min_per_km
            hr = self._estimate_hr(seg.avg_grade, state)
            power = self._estimate_power(seg.avg_grade, pace_min_per_km)
            
            state = self._evolve_state(state, seg.avg_grade, hr, power, 
                                       duration_min * 60, seg.elevation_gain)
            
            warning = self._generate_warning(state, seg)
            
            predictions.append({
                'segment': f"{seg.start_km:.1f}-{seg.end_km:.1f}km",
                'predicted_M': round(state.M, 1),
                'predicted_C': round(state.C, 1),
                'predicted_G': round(state.G, 1),
                'estimated_hr': round(hr),
                'estimated_pace': self._pace_to_string(pace_min_per_km),
                'warning': warning,
                'confidence': round(self._calculate_confidence(state), 2)
            })
        
        return predictions
    
    def _evolve_state(self, state: PhysioState, grade: float, hr: float, 
                      power: float, dt_sec: float, ele_gain: float) -> PhysioState:
        """Evolve physiological state using coupled differential equations."""
        M, C, G = state.M, state.C, state.G
        
        steps = max(1, int(dt_sec / 60))
        dt = dt_sec / steps
        
        for _ in range(steps):
            dM, dC, dG = self._derivatives(M, C, G, grade, hr, power, dt_sec)
            M = max(0, min(150, M + dM * dt))
            C = max(0, min(100, C + dC * dt))
            G = max(0, G + dG * dt)
        
        return PhysioState(M=M, C=C, G=G)
    
    def _derivatives(self, M: float, C: float, G: float, grade: float, 
                     hr: float, power: float, total_dt: float) -> tuple:
        """Calculate state derivatives at given state."""
        effective_grade = self._effective_grade(grade, M)
        k_surface = 1.0
        
        # Heaviside: glycogen depletion kicks in after 1 hour
        H = 1.0 if total_dt > 3600 else 0.3
        
        # Efficiency
        m_factor = M / 150
        c_factor = 1 - (C / 100)
        efficiency = max(0.5, 0.7 + 0.3 * m_factor * (1 - 0.5 * c_factor))
        
        # dM/dt - muscle fatigue (can recover when M < 50 on easy terrain)
        terrain_stress = self.ALPHA * abs(effective_grade) * k_surface * ((150 - M) / 150)
        recovery = self.ETA * (50 - M)  # Positive when M < 50 (recovery)
        dM_dt = -terrain_stress + recovery
        
        # dC/dt - cardiovascular stress (with recovery on easy terrain)
        hr_stress = max(0, hr - self.lthr)
        altitude_factor = 1.0
        stress = (self.BETA * hr_stress * altitude_factor
                  + self.LAMBDA * abs(effective_grade))
        c_recovery = self.ETA * (50 - C)  # Recovery when C < 50
        dC_dt = stress + c_recovery  # c_recovery is negative when C > 50
        
        # dG/dt - glycogen consumption
        dG_dt = -self.GAMMA * (power / efficiency) * H / 3600
        
        return dM_dt, dC_dt, dG_dt
    
    def _effective_grade(self, grade: float, M: float) -> float:
        """Terrain-aware dynamic correction: effective_grade = grade * (1.5 - M/200)."""
        return grade * (1.5 - M / 200)
    
    def _estimate_pace(self, grade: float, state: PhysioState) -> float:
        """Estimate running pace (min/km) based on grade and state."""
        base_pace = 5.0

        # Grade effect: steeper = slower
        if grade > 0:
            base_pace += grade * 0.25
        else:
            base_pace += grade * 0.10

        # Fatigue effects (more aggressive)
        if state.M < 30:
            base_pace += 1.0
        elif state.M < 50:
            base_pace += 0.5
        elif state.M < 70:
            base_pace += 0.2

        if state.C > 85:
            base_pace += 0.8
        elif state.C > 75:
            base_pace += 0.4
        elif state.C > 65:
            base_pace += 0.2

        if state.G < 80:
            base_pace += 0.8
        elif state.G < 150:
            base_pace += 0.4
        elif state.G < 250:
            base_pace += 0.2

        return max(2.5, min(15.0, base_pace))
    
    def _estimate_hr(self, grade: float, state: PhysioState) -> float:
        """Estimate heart rate based on grade and state."""
        base_hr = 140
        
        if grade > 10:
            base_hr += 25
        elif grade > 5:
            base_hr += 15
        elif grade > 2:
            base_hr += 5
        elif grade < -10:
            base_hr -= 5
        
        base_hr += (state.C - 50) * 0.3
        
        return max(100, min(self.max_hr, base_hr))
    
    def _estimate_power(self, grade: float, pace_min_per_km: float) -> float:
        """Estimate running power in watts."""
        base_power = 200
        grade_power = grade * 10
        pace_factor = (5.0 / pace_min_per_km) ** 2 if pace_min_per_km > 0 else 1
        return max(100, (base_power + grade_power) * pace_factor)
    
    def _generate_warning(self, state: PhysioState, seg) -> str:
        """Generate warning message if state is critical.

        Distinguishes between:
        - Runnable descents (moderate downhill = chance to gain time)
        - Technical climbs (very steep = need to scramble/hike)
        """
        warnings = []
        grade = seg.avg_grade

        # Muscle fatigue warnings - differentiate by terrain
        if state.M < 20:
            if grade < -5:
                warnings.append("肌肉严重疲劳，下坡需控制步频保护膝盖")
            else:
                warnings.append("肌肉严重疲劳，建议步行恢复")
        elif state.M < 40:
            if grade < -5:
                warnings.append("肌肉疲劳，下坡适当减速")
            else:
                warnings.append("肌肉疲劳积累，注意降速")

        # Cardiovascular stress
        if state.C > 85:
            warnings.append("心肺压力过高，建议降低强度")
        elif state.C > 75:
            warnings.append("心肺负荷较大")

        # Glycogen
        if state.G < 50:
            warnings.append("糖原储备严重不足，立即补给")
        elif state.G < 150:
            warnings.append("糖原储备偏低，建议补充能量")

        # Terrain-specific warnings
        if grade > 20:
            warnings.append(f"极陡爬升{grade:.0f}%，需手脚并用攀爬")
        elif grade > 15:
            warnings.append(f"陡坡爬升{grade:.0f}%，建议步行通过")
        elif grade < -20:
            warnings.append(f"极陡下降{abs(grade):.0f}%，需技术下降")
        elif grade < -15:
            warnings.append(f"陡坡下降{abs(grade):.0f}%，控制速度")

        return " | ".join(warnings) if warnings else ""
    
    def _calculate_confidence(self, state: PhysioState) -> float:
        """Calculate prediction confidence (0.85-0.95)."""
        confidence = 0.95 - (100 - state.M) / 1000 - state.C / 1000
        return max(0.85, min(0.95, confidence))
    
    def _pace_to_string(self, pace: float) -> str:
        """Convert pace (min/km) to mm:ss string."""
        minutes = int(pace)
        seconds = int((pace - minutes) * 60)
        return f"{minutes}:{seconds:02d}"


def generate_strategy(segments, predictions):
    """Generate pace strategy based on state predictions."""
    strategy = []
    for i, seg in enumerate(segments):
        pred = predictions[i] if i < len(predictions) else None
        base_pace = 5.0
        
        grade = seg.avg_grade
        if grade > 0:
            base_pace += grade * 0.18
        else:
            base_pace += grade * 0.08
        
        if pred:
            if pred['predicted_M'] < 40:
                base_pace += 0.5
            if pred['predicted_C'] > 80:
                base_pace += 0.3
            if pred['predicted_G'] < 100:
                base_pace += 0.3
        
        minutes = int(base_pace)
        seconds = int((base_pace - minutes) * 60)
        pace_str = f"{minutes}:{seconds:02d}"
        
        type_desc = {
            'flat': '平路',
            'rolling': '起伏',
            'climb': '上坡',
            'steep_climb': '陡坡爬升',
            'descent': '下坡',
            'steep_descent': '陡坡下降'
        }.get(seg.terrain_type, seg.terrain_type)
        
        strategy.append({
            'segment': f"{seg.start_km:.1f}-{seg.end_km:.1f}km",
            'pace': pace_str,
            'grade': seg.avg_grade,
            'type': type_desc,
            'length': seg.length_km,
            'state_warning': pred['warning'] if pred else '',
            'risk_level': seg.risk_level
        })
    
    return strategy
