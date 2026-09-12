import os
import re

files_to_process = [
    'backend/static/report.html',
    'backend/static/interview.html',
    'backend/static/index.html'
]

for filepath in files_to_process:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # update css cache buster
        content = re.sub(r'style\.css(\?v=[0-9\.]+)?', 'style.css?v=4.0.0', content)
        # update js cache buster
        content = re.sub(r'report\.js(\?v=[0-9\.]+)?', 'report.js?v=4.0.0', content)
        content = re.sub(r'interview\.js(\?v=[0-9\.]+)?', 'interview.js?v=4.0.0', content)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
