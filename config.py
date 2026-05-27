import os

# API Configuration - Read from environment variable, fallback to hardcoded key
KIMI_API_KEY = os.environ.get('KIMI_API_KEY', 'sk-lGKauq2Fz2H222ps5kYM04R75jTFlbwk6eLb48Uk4ALcmG3Y')
KIMI_API_ENDPOINT = 'https://api.moonshot.cn/v1/chat/completions'
KIMI_MODEL = 'moonshot-v1-8k'

# File Upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'gpx'}

# App
DEBUG = False
HOST = '0.0.0.0'
PORT = 5001
