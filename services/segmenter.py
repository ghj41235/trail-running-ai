"""
Smart Segmenter - Dynamic route segmentation
Flat/safe sections -> merged into 3-5km chunks
Dangerous sections -> split into 200-500m fine segments

FIXED for high-density GPX data:
- Pre-process: downsample points that are too close together
- Smooth grades with a larger window to reduce noise
- Merge aggressively based on terrain type + distance
"""
import math
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum


class TerrainType(Enum):
    FLAT = "flat"
    CLIMB = "climb"
    STEEP_CLIMB = "steep_climb"
    DESCENT = "descent"
    STEEP_DESCENT = "steep_descent"
    ROLLING = "rolling"


@dataclass
class Segment:
    """A route segment with terrain classification."""
    start_idx: int      # Start point index
    end_idx: int        # End point index
    start_km: float     # Start distance in km
    end_km: float       # End distance in km
    length_km: float    # Segment length
    avg_grade: float    # Average grade (%)
    max_grade: float    # Maximum grade (%)
    min_grade: float    # Minimum grade (%)
    terrain_type: str   # Terrain classification
    elevation_gain: float  # Elevation gain in meters
    elevation_loss: float  # Elevation loss in meters
    risk_level: str     # 'low', 'medium', 'high'


class SmartSegmenter:
    """Smart dynamic route segmentation.

    Strategy:
    - Flat/gentle sections (|grade| < 3%): merge into 3-5km chunks
    - Moderate climbs/descents (3% <= |grade| < 8%): 1-3km chunks
    - Steep sections (|grade| >= 8%): 200-500m fine segments
    - Extreme sections (|grade| >= 15%): 100-200m micro segments
    """

    # Grade thresholds (%)
    FLAT_THRESHOLD = 3.0
    MODERATE_THRESHOLD = 8.0
    STEEP_THRESHOLD = 15.0

    # Segment length targets (km)
    FLAT_TARGET = 4.0      # 3-5km for flat
    MODERATE_TARGET = 2.0   # 1-3km for moderate
    STEEP_TARGET = 0.35     # 200-500m for steep
    EXTREME_TARGET = 0.15   # 100-200m for extreme

    def __init__(self, gpx_service):
        self.gpx = gpx_service

    def segment(self, points: List[Dict]) -> List[Segment]:
        """Perform smart dynamic segmentation on route points."""
        if len(points) < 2:
            return []

        # Step 1: Downsample if points are too dense (target ~50m spacing)
        points = self._downsample(points, target_spacing_m=50)

        # Step 2: Calculate cumulative distances and smooth grades
        cumdist = self._calc_cumdist(points)
        grades = self._calculate_smooth_grades(points, cumdist, window_m=100)

        # Step 3: Create segments by terrain type with minimum length enforcement
        segments = self._segment_by_terrain(points, cumdist, grades)

        # Step 4: Aggressive merge of similar adjacent segments
        segments = self._aggressive_merge(segments)

        return segments

    def _downsample(self, points: List[Dict], target_spacing_m: float = 50) -> List[Dict]:
        """Downsample points to target spacing to reduce noise."""
        if len(points) < 10:
            return points

        result = [points[0]]
        dist_since_last = 0.0

        for i in range(1, len(points)):
            dist = self.gpx._haversine(
                result[-1]['lat'], result[-1]['lon'],
                points[i]['lat'], points[i]['lon']
            )
            dist_since_last += dist

            if dist_since_last >= target_spacing_m / 1000:
                result.append(points[i])
                dist_since_last = 0.0

        # Always keep last point
        if result[-1] != points[-1]:
            result.append(points[-1])

        return result

    def _calculate_smooth_grades(self, points: List[Dict], cumdist: List[float], window_m: float = 100) -> List[float]:
        """Calculate grades with distance-based smoothing window."""
        grades = []
        n = len(points)

        for i in range(n):
            # Find points within window
            left = i
            right = i
            window_km = window_m / 1000

            while left > 0 and cumdist[i] - cumdist[left] < window_km:
                left -= 1
            while right < n - 1 and cumdist[right] - cumdist[i] < window_km:
                right += 1

            if right <= left:
                grades.append(0.0)
                continue

            ele_diff = points[right]['ele'] - points[left]['ele']
            dist = cumdist[right] - cumdist[left]

            if dist > 0:
                grade = (ele_diff / (dist * 1000)) * 100
                grades.append(round(grade, 1))
            else:
                grades.append(0.0)

        return grades

    def _segment_by_terrain(self, points, cumdist, grades) -> List[Segment]:
        """Create segments with minimum length enforcement."""
        segments = []
        n = len(points)
        i = 0

        while i < n - 1:
            start_idx = i
            start_type = self._classify_terrain(grades[i])

            # Determine minimum length for this terrain type
            min_len = self._min_length_for_type(start_type)
            j = i + 1

            while j < n:
                current_type = self._classify_terrain(grades[j])
                seg_length = cumdist[j] - cumdist[start_idx]

                # Must reach minimum length before allowing split
                if seg_length < min_len:
                    j += 1
                    continue

                # Terrain type change forces a boundary
                if current_type != start_type:
                    break

                # Also enforce max length
                max_len = self._max_length_for_type(start_type)
                if seg_length >= max_len:
                    break

                j += 1

            end_idx = min(j, n - 1)
            # Ensure we make progress
            if end_idx <= start_idx:
                end_idx = min(start_idx + 1, n - 1)

            seg = self._create_segment(points, cumdist, grades, start_idx, end_idx)
            segments.append(seg)
            i = end_idx

        return segments

    def _min_length_for_type(self, terrain_type: TerrainType) -> float:
        """Minimum segment length in km."""
        mapping = {
            TerrainType.FLAT: 2.0,
            TerrainType.ROLLING: 1.0,
            TerrainType.CLIMB: 0.5,
            TerrainType.DESCENT: 0.5,
            TerrainType.STEEP_CLIMB: 0.1,
            TerrainType.STEEP_DESCENT: 0.1,
        }
        return mapping.get(terrain_type, 0.5)

    def _max_length_for_type(self, terrain_type: TerrainType) -> float:
        """Maximum segment length in km."""
        mapping = {
            TerrainType.FLAT: 5.0,
            TerrainType.ROLLING: 3.0,
            TerrainType.CLIMB: 2.0,
            TerrainType.DESCENT: 2.0,
            TerrainType.STEEP_CLIMB: 0.5,
            TerrainType.STEEP_DESCENT: 0.5,
        }
        return mapping.get(terrain_type, 2.0)

    def _aggressive_merge(self, segments: List[Segment]) -> List[Segment]:
        """Aggressively merge adjacent segments."""
        if len(segments) <= 1:
            return segments

        # Pass 1: Merge same terrain type
        merged = self._merge_same_type(segments)

        # Pass 2: Merge flat/rolling into larger chunks
        merged = self._merge_flat_rolling(merged)

        # Pass 3: Merge short segments into neighbors
        merged = self._merge_short_segments(merged)

        return merged

    def _merge_same_type(self, segments: List[Segment]) -> List[Segment]:
        """Merge adjacent segments with same terrain type."""
        merged = []
        current = segments[0]

        for seg in segments[1:]:
            if (seg.terrain_type == current.terrain_type and
                current.length_km + seg.length_km <= self._max_length_for_type(
                    self._classify_terrain_name(current.terrain_type))):
                current = self._combine_segments(current, seg)
            else:
                merged.append(current)
                current = seg

        merged.append(current)
        return merged

    def _merge_flat_rolling(self, segments: List[Segment]) -> List[Segment]:
        """Merge adjacent flat/rolling segments."""
        merged = []
        current = None

        for seg in segments:
            if seg.terrain_type in ('flat', 'rolling'):
                if current is None:
                    current = seg
                elif current.terrain_type in ('flat', 'rolling'):
                    if current.length_km + seg.length_km <= 5.0:
                        current = self._combine_segments(current, seg)
                    else:
                        merged.append(current)
                        current = seg
                else:
                    merged.append(current)
                    current = seg
            else:
                if current is not None:
                    merged.append(current)
                    current = None
                merged.append(seg)

        if current is not None:
            merged.append(current)

        return merged

    def _merge_short_segments(self, segments: List[Segment]) -> List[Segment]:
        """Merge very short segments (<200m) into neighbors."""
        if len(segments) <= 1:
            return segments

        result = []
        i = 0
        while i < len(segments):
            seg = segments[i]

            if seg.length_km < 0.2 and len(result) > 0:
                # Merge into previous
                result[-1] = self._combine_segments(result[-1], seg)
            elif seg.length_km < 0.2 and i < len(segments) - 1:
                # Merge into next
                segments[i + 1] = self._combine_segments(seg, segments[i + 1])
                i += 1
                continue
            else:
                result.append(seg)

            i += 1

        return result

    def _classify_terrain_name(self, name: str) -> TerrainType:
        """Convert terrain type string to enum."""
        mapping = {
            'flat': TerrainType.FLAT,
            'rolling': TerrainType.ROLLING,
            'climb': TerrainType.CLIMB,
            'descent': TerrainType.DESCENT,
            'steep_climb': TerrainType.STEEP_CLIMB,
            'steep_descent': TerrainType.STEEP_DESCENT,
        }
        return mapping.get(name, TerrainType.FLAT)

    def _combine_segments(self, a: Segment, b: Segment) -> Segment:
        """Combine two adjacent segments."""
        total_len = a.length_km + b.length_km
        avg_grade = round((a.avg_grade * a.length_km + b.avg_grade * b.length_km) / total_len, 1)
        max_grade = max(a.max_grade, b.max_grade)
        min_grade = min(a.min_grade, b.min_grade)

        # Reclassify terrain based on combined grade
        terrain_type = self._terrain_type_string(avg_grade, max_grade, min_grade)
        ele_gain = a.elevation_gain + b.elevation_gain
        ele_loss = a.elevation_loss + b.elevation_loss

        return Segment(
            start_idx=a.start_idx,
            end_idx=b.end_idx,
            start_km=a.start_km,
            end_km=b.end_km,
            length_km=round(total_len, 2),
            avg_grade=avg_grade,
            max_grade=max_grade,
            min_grade=min_grade,
            terrain_type=terrain_type,
            elevation_gain=round(ele_gain, 1),
            elevation_loss=round(ele_loss, 1),
            risk_level=self._assess_risk(avg_grade, max_grade, ele_gain, ele_loss, total_len)
        )

    def _calc_cumdist(self, points: List[Dict]) -> List[float]:
        """Calculate cumulative distance for each point."""
        cumdist = [0.0]
        for i in range(1, len(points)):
            dist = self.gpx._haversine(
                points[i-1]['lat'], points[i-1]['lon'],
                points[i]['lat'], points[i]['lon']
            )
            cumdist.append(cumdist[-1] + dist)
        return cumdist

    def _classify_terrain(self, grade: float) -> TerrainType:
        """Classify terrain based on grade."""
        if grade >= self.STEEP_THRESHOLD:
            return TerrainType.STEEP_CLIMB
        elif grade >= self.MODERATE_THRESHOLD:
            return TerrainType.CLIMB
        elif grade >= self.FLAT_THRESHOLD:
            return TerrainType.ROLLING if grade > 0 else TerrainType.DESCENT
        elif grade <= -self.STEEP_THRESHOLD:
            return TerrainType.STEEP_DESCENT
        elif grade <= -self.MODERATE_THRESHOLD:
            return TerrainType.DESCENT
        elif grade <= -self.FLAT_THRESHOLD:
            return TerrainType.ROLLING
        else:
            return TerrainType.FLAT

    def _create_segment(self, points, cumdist, grades, start_idx, end_idx) -> Segment:
        """Create a Segment object from point indices."""
        seg_grades = grades[start_idx:end_idx+1]
        avg_grade = sum(seg_grades) / len(seg_grades) if seg_grades else 0
        max_grade = max(seg_grades) if seg_grades else 0
        min_grade = min(seg_grades) if seg_grades else 0

        ele_gain = 0
        ele_loss = 0
        for i in range(start_idx + 1, end_idx + 1):
            diff = points[i]['ele'] - points[i-1]['ele']
            if diff > 0:
                ele_gain += diff
            else:
                ele_loss += abs(diff)

        terrain_type = self._terrain_type_string(avg_grade, max_grade, min_grade)
        length_km = round(cumdist[end_idx] - cumdist[start_idx], 2)
        risk_level = self._assess_risk(avg_grade, max_grade, ele_gain, ele_loss, length_km)

        return Segment(
            start_idx=start_idx,
            end_idx=end_idx,
            start_km=round(cumdist[start_idx], 2),
            end_km=round(cumdist[end_idx], 2),
            length_km=length_km,
            avg_grade=round(avg_grade, 1),
            max_grade=round(max_grade, 1),
            min_grade=round(min_grade, 1),
            terrain_type=terrain_type,
            elevation_gain=round(ele_gain, 1),
            elevation_loss=round(ele_loss, 1),
            risk_level=risk_level
        )

    def _terrain_type_string(self, avg_grade, max_grade, min_grade) -> str:
        """Convert grade to terrain type string."""
        if avg_grade >= self.STEEP_THRESHOLD:
            return 'steep_climb'
        elif avg_grade >= self.MODERATE_THRESHOLD:
            return 'climb'
        elif avg_grade <= -self.STEEP_THRESHOLD:
            return 'steep_descent'
        elif avg_grade <= -self.MODERATE_THRESHOLD:
            return 'descent'
        elif abs(avg_grade) < self.FLAT_THRESHOLD:
            return 'flat'
        else:
            return 'rolling'

    def _assess_risk(self, avg_grade, max_grade, ele_gain, ele_loss, length_km: float = 1.0) -> str:
        """Assess segment risk level.

        Uses avg_grade as primary criterion, with elevation change
        normalized by segment length to avoid long flat sections
        being flagged as medium due to cumulative elevation.
        """
        abs_avg = abs(avg_grade)

        # Normalize elevation change per km
        ele_gain_per_km = ele_gain / length_km if length_km > 0 else 0
        ele_loss_per_km = ele_loss / length_km if length_km > 0 else 0

        # High risk: very steep sustained grades
        if abs_avg >= 15:
            return 'high'
        # Medium risk: moderately steep or significant elevation density
        elif abs_avg >= 8:
            return 'medium'
        elif abs_avg >= 5 and (ele_gain_per_km > 80 or ele_loss_per_km > 80):
            return 'medium'
        # Low risk: gentle grades
        elif abs_avg >= 3:
            return 'low'
        else:
            return 'low'
