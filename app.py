"""
Trail Running AI Assistant - Flask Backend
Main application with API routes for GPX analysis, AI services, and training plans.
"""
import os
import sys
import json
import traceback
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config
from services.gpx_service import GPXService
from services.segmenter import SmartSegmenter
from services.state_model import CoupledStateModel, generate_strategy
from services.risk_analyzer import RiskAnalyzer, calculate_segment_risks_for_chart
from services.ai_service import AIService

app = Flask(__name__)
app.config.from_object(config)
CORS(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize services
gpx_service = GPXService()
segmenter = SmartSegmenter(gpx_service)
risk_analyzer = RiskAnalyzer()
ai_service = AIService(
    api_key=config.KIMI_API_KEY,
    endpoint=config.KIMI_API_ENDPOINT,
    model=config.KIMI_MODEL
)

# In-memory history storage
history_records = []


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


def handle_error(f):
    """Decorator to handle exceptions consistently."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            app.logger.error(traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 500
    return wrapper


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
@handle_error
def analyze_route():
    """Analyze a GPX file and return full analysis.
    
    Returns:
        JSON with points, metrics, segments, risks, state_predictions, strategy
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '只支持.gpx文件'}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        # Parse GPX
        points, metrics = gpx_service.parse(filepath)
        
        # Smart segmentation
        segments = segmenter.segment(points)
        
        # State model simulation
        state_model = CoupledStateModel()
        predictions = state_model.simulate(points, segments)
        
        # Risk analysis
        risks = risk_analyzer.analyze(segments)
        
        # Strategy generation
        strategy = generate_strategy(segments, predictions)
        
        # Risk distribution for charts
        risk_dist = calculate_segment_risks_for_chart(segments)

        # Generate route summary: danger points, speed-up points, scramble sections
        route_summary = _generate_route_summary(segments, predictions, risks)

        # Add to history
        record = {
            'id': len(history_records) + 1,
            'type': 'route',
            'name': file.filename.replace('.gpx', ''),
            'date': datetime.now().isoformat(),
            'distance': metrics['total_distance_km'],
            'ascent': metrics['total_ascent_m'],
            'segments': len(segments)
        }
        history_records.insert(0, record)
        
        # Serialize segments for JSON
        segments_data = []
        for s in segments:
            segments_data.append({
                'start': s.start_km,
                'end': s.end_km,
                'length': s.length_km,
                'avg_grade': s.avg_grade,
                'max_grade': s.max_grade,
                'min_grade': s.min_grade,
                'terrain_type': s.terrain_type,
                'elevation_gain': s.elevation_gain,
                'elevation_loss': s.elevation_loss,
                'risk_level': s.risk_level
            })
        
        return jsonify({
            'success': True,
            'points': points,
            'metrics': metrics,
            'segments': segments_data,
            'risks': risks,
            'state_predictions': predictions,
            'strategy': strategy,
            'risk_distribution': risk_dist,
            'route_summary': route_summary
        })
        
    finally:
        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass


@app.route('/api/demo-route', methods=['GET'])
@handle_error
def demo_route():
    """Generate and return a demo route for testing."""
    points, metrics = gpx_service.generate_sample_route()
    
    # Smart segmentation
    segments = segmenter.segment(points)
    
    # State model
    state_model = CoupledStateModel()
    predictions = state_model.simulate(points, segments)
    
    # Risk analysis
    risks = risk_analyzer.analyze(segments)
    
    # Strategy
    strategy = generate_strategy(segments, predictions)
    
    # Risk distribution
    risk_dist = calculate_segment_risks_for_chart(segments)

    # Route summary
    route_summary = _generate_route_summary(segments, predictions, risks)

    # Add to history
    record = {
        'id': len(history_records) + 1,
        'type': 'route',
        'name': '示例路线（演示用）',
        'date': datetime.now().isoformat(),
        'distance': metrics['total_distance_km'],
        'ascent': metrics['total_ascent_m'],
        'segments': len(segments)
    }
    history_records.insert(0, record)

    segments_data = []
    for s in segments:
        segments_data.append({
            'start': s.start_km,
            'end': s.end_km,
            'length': s.length_km,
            'avg_grade': s.avg_grade,
            'max_grade': s.max_grade,
            'min_grade': s.min_grade,
            'terrain_type': s.terrain_type,
            'elevation_gain': s.elevation_gain,
            'elevation_loss': s.elevation_loss,
            'risk_level': s.risk_level
        })

    return jsonify({
        'success': True,
        'points': points,
        'metrics': metrics,
        'segments': segments_data,
        'risks': risks,
        'state_predictions': predictions,
        'strategy': strategy,
        'risk_distribution': risk_dist,
        'route_summary': route_summary
    })


@app.route('/api/ai/plan', methods=['POST'])
@handle_error
def ai_training_plan():
    """Generate training plan via AI with local fallback.
    
    Returns:
        JSON with plan and source indicator
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '无数据'}), 400
    
    try:
        plan = ai_service.generate_plan(data)
        return jsonify({
            'success': True,
            'source': 'ai',
            'plan': plan
        })
    except Exception as e:
        # AI failed, return local fallback with 503
        fallback = ai_service.local_plan(data)
        return jsonify({
            'success': True,  # Still return success since we have fallback
            'source': 'local',
            'error': str(e),
            'plan': fallback
        })


@app.route('/api/ai/chat', methods=['POST'])
@handle_error
def ai_chat():
    """AI coach chat endpoint.
    
    Returns:
        JSON with AI reply
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '无数据'}), 400
    
    msg = data.get('message', '')
    context = data.get('context', {})
    
    try:
        reply = ai_service.chat(msg, context)
        return jsonify({'success': True, 'reply': reply})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'reply': 'AI服务暂时不可用，请稍后再试。您可以使用本地训练计划功能。'
        }), 503


@app.route('/api/ai/equipment', methods=['POST'])
@handle_error
def ai_equipment():
    """Get equipment recommendations based on route data."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '无数据'}), 400
    
    try:
        advice = ai_service.generate_equipment_advice(data)
        return jsonify({'success': True, 'advice': advice})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'advice': ai_service._default_equipment(data)
        })


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get activity history."""
    return jsonify({'success': True, 'records': history_records[:50]})


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """Clear all history records."""
    history_records.clear()
    return jsonify({'success': True})


def _generate_route_summary(segments, predictions, risks):
        """Generate concise route summary for key decision points."""
        # Danger points: high risk segments + very steep sections
        danger_points = []
        for seg in segments:
            if seg.risk_level == 'high' or abs(seg.avg_grade) >= 15:
                danger_points.append({
                    'start': seg.start_km,
                    'end': seg.end_km,
                    'grade': seg.avg_grade,
                    'type': '陡坡' if seg.avg_grade > 0 else '陡降',
                    'reason': f"{'爬升' if seg.avg_grade > 0 else '下降'}{abs(seg.avg_grade):.0f}%"
                })

        # Scramble sections: extremely steep climbs requiring hands
        scramble_sections = []
        for seg in segments:
            if seg.avg_grade > 20:
                scramble_sections.append({
                    'start': seg.start_km,
                    'end': seg.end_km,
                    'grade': seg.avg_grade,
                    'length': seg.length_km
                })

        # Speed-up points: runnable descents (-5% to -15%) and flat/rolling sections
        speedup_points = []
        for seg in segments:
            # Runnable descent: not too steep, not too technical
            if -15 <= seg.avg_grade < -3 and seg.length_km >= 0.3:
                speedup_points.append({
                    'start': seg.start_km,
                    'end': seg.end_km,
                    'grade': seg.avg_grade,
                    'type': '可跑下坡',
                    'length': seg.length_km
                })
            # Flat/rolling where you can maintain pace
            elif abs(seg.avg_grade) <= 3 and seg.length_km >= 1.0:
                # Check if state is good enough to push
                speedup_points.append({
                    'start': seg.start_km,
                    'end': seg.end_km,
                    'grade': seg.avg_grade,
                    'type': '平缓路段',
                    'length': seg.length_km
                })

        return {
            'danger_count': len(danger_points),
            'danger_points': danger_points,
            'scramble_count': len(scramble_sections),
            'scramble_sections': scramble_sections,
            'speedup_count': len(speedup_points),
            'speedup_points': speedup_points
        }

@app.route('/api/green-eco', methods=['GET'])
def get_green_eco():
    """Get green eco data (mock data for demo)."""
    return jsonify({
        'success': True,
        'data': {
            'total_runs': 12,
            'total_distance': 156.8,
            'carbon_saved': 23.5,
            'green_points': 785,
            'level': '环保达人',
            'level_progress': 78.5,
            'monthly_data': [
                {'month': '1月', 'carbon': 18.5},
                {'month': '2月', 'carbon': 22.3},
                {'month': '3月', 'carbon': 19.8},
                {'month': '4月', 'carbon': 25.6},
                {'month': '5月', 'carbon': 21.4},
                {'month': '6月', 'carbon': 23.5}
            ]
        }
    })


if __name__ == '__main__':
    print(f"Starting Trail Running AI Assistant...")
    print(f"API Key configured: {'Yes' if config.KIMI_API_KEY else 'No (AI features will use local fallback)'}")
    app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT)
