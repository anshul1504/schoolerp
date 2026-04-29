import os
import re

files = [
    'create.html',
    'edit.html',
    'import.html',
    'import_preview.html',
    'invitations.html',
    'invite.html',
    'list.html'
]

base_dir = r'c:\Users\PC\Desktop\sCHOOL\school_erp\templates\users'

def fix_file(filename):
    path = os.path.join(base_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # We need to find:
    # {% block content %}
    # {% block heading_actions %} ... {% endblock %}
    # and move heading_actions BEFORE content.

    match = re.search(r'\{\%\s*block\s+content\s*\%\}\s*(\{\%\s*block\s+heading_actions\s*\%\}.*?\{\%\s*endblock\s*\%\})', text, flags=re.DOTALL)
    if match:
        heading_block = match.group(1)
        # Remove it from inside content
        text = text.replace(match.group(0), '{% block content %}')
        # Place it before content
        text = text.replace('{% block content %}', heading_block + '\n\n{% block content %}')

        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Fixed {filename}")
    else:
        print(f"No match in {filename}")

for f in files:
    fix_file(f)

