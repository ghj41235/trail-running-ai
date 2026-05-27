"""
GPX Service - Handles GPX file parsing using gpxpy (open source library)
https://github.com/tkrajina/gpxpy
"""
import gpxpy
import math
from typing import List, Tuple, Dict, Any


class GPXService:
    """GPX file parsing and metrics calculation service."""

    def parse(self, filepath: str) -> Tuple[List[Dict], Dict]:
        """Parse a GPX file and return points and metrics.
        
        Args:
            filepath: Path to the GPX file
            
        Returns:
            Tuple of (points list, metrics dict)
            points: [{'lat': float, 'lon': float, 'ele': float}, ...]
            metrics: {'total_distance_km', 'total_ascent_m', 'total_descent_m', 
                     'max_elevation_m', 'min_elevation_m', 'avg_gradient'}
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)

        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append({
                        'lat': point.latitude,
                        'lon': point.longitude,
                        'ele': point.elevation or 0
                    })

        if len(points) < 2:
            raise ValueError("GPX文件中没有足够的轨迹点（至少需要2个）")

        metrics = self._calc_metrics(points)
        return points, metrics

    def parse_from_text(self, xml_text: str) -> Tuple[List[Dict], Dict]:
        """Parse GPX from XML string."""
        gpx = gpxpy.parse(xml_text)

        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append({
                        'lat': point.latitude,
                        'lon': point.longitude,
                        'ele': point.elevation or 0
                    })

        if len(points) < 2:
            raise ValueError("GPX数据中没有足够的轨迹点（至少需要2个）")

        metrics = self._calc_metrics(points)
        return points, metrics

    def _calc_metrics(self, points: List[Dict]) -> Dict:
        """Calculate route metrics from points."""
        total_dist = 0.0
        total_ascent = 0.0
        total_descent = 0.0
        max_ele = points[0]['ele'] if points else 0
        min_ele = points[0]['ele'] if points else 0

        for i in range(1, len(points)):
            lat1, lon1, ele1 = points[i-1]['lat'], points[i-1]['lon'], points[i-1]['ele']
            lat2, lon2, ele2 = points[i]['lat'], points[i]['lon'], points[i]['ele']

            dist = self._haversine(lat1, lon1, lat2, lon2)
            total_dist += dist

            ele_diff = ele2 - ele1
            if ele_diff > 0:
                total_ascent += ele_diff
            else:
                total_descent += abs(ele_diff)

            max_ele = max(max_ele, ele2)
            min_ele = min(min_ele, ele2)

        avg_gradient = (total_ascent / (total_dist * 1000)) * 100 if total_dist > 0 else 0

        return {
            'total_distance_km': round(total_dist, 2),
            'total_ascent_m': round(total_ascent),
            'total_descent_m': round(total_descent),
            'max_elevation_m': round(max_ele),
            'min_elevation_m': round(min_ele),
            'avg_gradient': round(avg_gradient, 1)
        }

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371.0  # Earth radius in km
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def calculate_grades(self, points: List[Dict], window_size: int = 10) -> List[float]:
        """Calculate grade (slope) at each point using a rolling window.
        
        Args:
            points: List of points with lat, lon, ele
            window_size: Number of points to use for grade calculation
            
        Returns:
            List of grade percentages for each point
        """
        grades = []
        for i in range(len(points)):
            start = max(0, i - window_size // 2)
            end = min(len(points), i + window_size // 2 + 1)
            
            if end - start < 2:
                grades.append(0.0)
                continue
                
            ele_diff = points[end-1]['ele'] - points[start]['ele']
            dist = 0.0
            for j in range(start + 1, end):
                dist += self._haversine(
                    points[j-1]['lat'], points[j-1]['lon'],
                    points[j]['lat'], points[j]['lon']
                )
            
            if dist > 0:
                grade = (ele_diff / (dist * 1000)) * 100
                grades.append(round(grade, 1))
            else:
                grades.append(0.0)
        
        return grades

    def generate_sample_route(self) -> Tuple[List[Dict], Dict]:
        """Generate a sample route with varied terrain for demonstration."""
        # Create a route with flat sections, climbs, and descents
        base_lat, base_lon = 39.9042, 116.4074  # Beijing area
        
        # Generate ~200 points over ~15km with realistic terrain profile
        points = []
        num_points = 200
        
        for i in range(num_points):
            # Progress along route (0 to 1)
            t = i / (num_points - 1)
            
            # Create a winding path
            lat = base_lat + 0.05 * t + 0.01 * math.sin(t * 8 * math.pi)
            lon = base_lon + 0.08 * t + 0.005 * math.cos(t * 6 * math.pi)
            
            # Create elevation profile with varied terrain:
            # 0-15%: flat warmup (ele ~50m)
            # 15-30%: gradual climb (50m -> 200m)
            # 30-40%: steep climb (200m -> 450m) - HARD
            # 40-55%: rolling hills (450m -> 400m)
            # 55-70%: steep descent (400m -> 150m) - RISK
            # 70-85%: gradual climb (150m -> 350m)
            # 85-100%: flat finish (350m -> 300m)
            
            if t < 0.15:
                ele = 50 + 20 * math.sin(t * 40 * math.pi)
            elif t < 0.30:
                ele = 50 + (t - 0.15) / 0.15 * 150 + 30 * math.sin(t * 20 * math.pi)
            elif t < 0.40:
                ele = 200 + (t - 0.30) / 0.10 * 250 + 50 * math.sin(t * 15 * math.pi)
            elif t < 0.55:
                ele = 450 - (t - 0.40) / 0.15 * 50 + 40 * math.sin(t * 25 * math.pi)
            elif t < 0.70:
                ele = 400 - (t - 0.55) / 0.15 * 250 + 30 * math.sin(t * 18 * math.pi)
            elif t < 0.85:
                ele = 150 + (t - 0.70) / 0.15 * 200 + 25 * math.sin(t * 22 * math.pi)
            else:
                ele = 350 - (t - 0.85) / 0.15 * 50 + 15 * math.sin(t * 30 * math.pi)
            
            points.append({
                'lat': round(lat, 6),
                'lon': round(lon, 6),
                'ele': round(ele, 1)
            })
        
        metrics = self._calc_metrics(points)
        return points, metrics

    def generate_gpx_xml(self, points: List[Dict], name: str = "示例路线") -> str:
        """Generate a GPX XML string from points."""
        from datetime import datetime, timedelta
        
        gpx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="TrailRunningAI" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>{name}</name>
    <trkseg>"""
        
        base_time = datetime(2025, 4, 9, 8, 0, 0)
        for i, p in enumerate(points):
            time = base_time + timedelta(minutes=i * 2)
            gpx_content += f"""
      <trkpt lat="{p['lat']}" lon="{p['lon']}">
        <ele>{p['ele']}</ele>
        <time>{time.isoformat()}Z</time>
      </trkpt>"""
        
        gpx_content += """
    </trkseg>
  </trk>
</gpx>"""
        return gpx_content
