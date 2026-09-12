import os
import re

files_to_process = [
    'backend/static/css/style.css',
    'backend/static/report.html',
    'backend/static/interview.html',
    'backend/static/index.html'
]

replacements = [
    # General CSS adjustments for light mode
    (r'rgba\(255,\s*255,\s*255,\s*0\.\d+\)', 'var(--border)'),
    (r'background:\s*linear-gradient\(135deg,\s*#ffffff\s*0%,\s*#a5b4fc\s*100%\);', 'color: var(--text);'),
    (r'-webkit-background-clip:\s*text;', ''),
    (r'-webkit-text-fill-color:\s*transparent;', ''),
    (r'color:\s*#ffffff;', 'color: var(--surface);'),
    
    # Report.html specific pastels (success/green)
    (r'rgba\(76,\s*175,\s*80,\s*0\.08\)', '#f0fdf4'),
    (r'rgba\(76,\s*175,\s*80,\s*0\.2\)', '#bbf7d0'),
    (r'rgba\(76,\s*175,\s*80,\s*0\.03\)', '#f0fdf4'),
    (r'rgba\(76,\s*175,\s*130,\s*0\.2\)', '#f0fdf4'),
    (r'#4caf50', '#166534'),
    
    # Report.html specific pastels (danger/red)
    (r'rgba\(224,\s*92,\s*92,\s*0\.03\)', '#fff1f2'),
    (r'rgba\(224,\s*92,\s*92,\s*0\.1\)', '#fecdd3'),
    (r'rgba\(224,\s*92,\s*92,\s*0\.05\)', '#fff1f2'),
    (r'rgba\(224,\s*92,\s*92,\s*0\.2\)', '#fff1f2'),
    (r'rgba\(224,\s*92,\s*92,\s*0\.15\)', '#fff1f2'),
    (r'rgba\(224,\s*92,\s*92,\s*0\.12\)', '#fff1f2'),
    (r'rgba\(224,\s*92,\s*92,\s*0\.3\)', '#fecdd3'),
    
    # Badges / Accents (purple/blue)
    (r'rgba\(108,\s*99,\s*255,\s*0\.06\)', '#eff6ff'),
    (r'rgba\(108,\s*99,\s*255,\s*0\.15\)', '#bfdbfe'),
    (r'rgba\(108,\s*99,\s*255,\s*0\.1\)', '#eff6ff'),
    (r'rgba\(108,\s*99,\s*255,\s*0\.12\)', '#eff6ff'),
    (r'rgba\(108,\s*99,\s*255,\s*0\.25\)', '#bfdbfe'),
    
    # Warning (yellow/orange)
    (r'rgba\(245,\s*166,\s*35,\s*0\.2\)', '#fefce8'),
    (r'rgba\(245,\s*166,\s*35,\s*0\.3\)', '#fef08a'),
    
    # Accent2 (teal)
    (r'rgba\(78,\s*205,\s*196,\s*0\.08\)', '#f0fdfa'),
]

for filepath in files_to_process:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
print('Refactoring complete.')
