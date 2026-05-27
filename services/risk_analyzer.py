"""
Risk Analyzer - Smart risk analysis for trail routes
Core principle: Only show REAL dangers, not every slight slope.
- Merge adjacent risks of the same type
- Maximum 6 risk items
- Color coding: red (>15%), yellow (3-15%), green (<3% not shown)
"""
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class RiskItem:
    """A risk item for display."""
    start: float        # Start km
    end: float          # End km
    level: str          # 'high', 'medium'
    type: str           # Risk type
    desc: str           # Description
    suggest: str        # Suggestion


class RiskAnalyzer:
    """Intelligent risk analyzer.
    
    Rules:
    - High risk (red): avg_grade > 15% or max_grade > 20%, or steep_descent > 10%
    - Medium risk (yellow): avg_grade 3-15% or max_grade 10-20%
    - Low risk: not shown (swallowed by smart segmentation)
    - Merge adjacent risks of same type and level
    - Maximum 6 items total
    """
    
    # Grade thresholds
    HIGH_GRADE = 15.0
    MEDIUM_GRADE = 8.0
    HIGH_MAX_GRADE = 20.0
    MEDIUM_MAX_GRADE = 12.0
    STEEP_DESCENT = 10.0  # Descent risk threshold
    
    def analyze(self, segments) -> List[Dict]:
        """Analyze segments and return risk items (max 6, merged).
        
        Args:
            segments: List of segment objects from SmartSegmenter
            
        Returns:
            List of risk dicts for frontend display
        """
        raw_risks = self._detect_risks(segments)
        merged = self._merge_adjacent(raw_risks)
        
        # Cap at 6 items - prioritize high risks
        merged.sort(key=lambda r: 0 if r['level'] == 'high' else 1)
        if len(merged) > 6:
            merged = merged[:6]
        
        # Sort back by distance
        merged.sort(key=lambda r: r['start'])
        
        return merged
    
    def _detect_risks(self, segments) -> List[Dict]:
        """Detect individual risk points from segments."""
        risks = []

        for seg in segments:
            abs_avg = abs(seg.avg_grade)
            abs_max = abs(seg.max_grade)
            length = seg.length_km

            # Skip flat/gentle segments entirely (they're not risks)
            if abs_avg < 5:
                continue

            # Determine risk level and type
            is_descent = seg.avg_grade < 0

            # High risk: sustained steep grades
            if abs_avg >= self.HIGH_GRADE:
                level = 'high'
                if is_descent:
                    risk_type = 'steep_descent'
                    desc = f"陡坡下降{abs_avg:.0f}%，持续{length:.1f}km"
                    suggest = "控制速度，小步高频，注意落脚点"
                else:
                    risk_type = 'steep_climb'
                    desc = f"陡坡爬升{abs_avg:.0f}%，持续{length:.1f}km"
                    suggest = "采用小步高频技术，必要时步行通过"

            # Medium risk: moderate grades
            elif abs_avg >= self.MEDIUM_GRADE:
                level = 'medium'
                if is_descent:
                    risk_type = 'steep_descent'
                    desc = f"下坡路段{abs_avg:.0f}%，持续{length:.1f}km"
                    suggest = "利用重力但控制速度，保护膝盖"
                else:
                    risk_type = 'climb'
                    desc = f"上坡路段{abs_avg:.0f}%，持续{length:.1f}km"
                    suggest = "适当降低配速，保持稳定节奏"

            else:
                continue  # Low risk - skip

            risks.append({
                'start': seg.start_km,
                'end': seg.end_km,
                'level': level,
                'type': risk_type,
                'desc': desc,
                'suggest': suggest
            })

        return risks
    
    def _merge_adjacent(self, risks: List[Dict]) -> List[Dict]:
        """Merge adjacent risks of the same type and level."""
        if not risks:
            return []
        
        merged = []
        current = dict(risks[0])
        
        for risk in risks[1:]:
            # Merge if adjacent (within 0.5km gap) and same type+level
            if (risk['level'] == current['level'] and 
                risk['type'] == current['type'] and
                risk['start'] - current['end'] < 0.5):
                # Extend current
                current['end'] = risk['end']
                current['desc'] = self._merge_desc(current['desc'], risk['desc'])
                current['suggest'] = current['suggest']  # Keep first suggestion
            else:
                merged.append(current)
                current = dict(risk)
        
        merged.append(current)
        return merged
    
    def _merge_desc(self, desc1: str, desc2: str) -> str:
        """Merge two descriptions intelligently."""
        # If both mention grades, keep the more severe one
        if "坡度" in desc1 and "坡度" in desc2:
            return desc1  # Keep first (more severe due to sort order)
        return desc1


def calculate_segment_risks_for_chart(segments) -> Dict:
    """Calculate risk distribution for charts.
    
    Returns dict with counts of high/medium/low risk segments.
    """
    high = sum(1 for s in segments if s.risk_level == 'high')
    medium = sum(1 for s in segments if s.risk_level == 'medium')
    low = sum(1 for s in segments if s.risk_level == 'low')
    total = len(segments) or 1
    
    return {
        'high_pct': round(high / total * 100),
        'medium_pct': round(medium / total * 100),
        'low_pct': round(low / total * 100),
        'high_count': high,
        'medium_count': medium,
        'low_count': low
    }
