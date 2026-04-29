import os
import re

base_dir = r'c:\Users\PC\Desktop\sCHOOL\school_erp\templates\settings'

for filename in ['index.html', 'branding.html', 'role_matrix.html', 'permissions_matrix.html']:
    path = os.path.join(base_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Replace double endblock at the end
    text = re.sub(r'\{\%\s*endblock\s*\%\}\s*\{\%\s*endblock\s*\%\}', r'{% endblock %}', text)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

print("done")
