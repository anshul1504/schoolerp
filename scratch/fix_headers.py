import re
import os

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

    # Find where the custom header starts and ends
    # It usually starts right after {% block content %}

    # We will extract the buttons from inside the header if possible, but it's safer to just define the replacements.

    # Let's just do targeted regex.
    if filename == 'list.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</div>\s*</div>\s*<div class="row gy-4">',
            r'{% block heading_actions %}\n<div class="d-flex align-items-center gap-12">\n    <a href="/users/invite/" class="btn btn-outline-primary d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:mail-send-line"></iconify-icon>\n        Invite User\n    </a>\n    <a href="/users/create/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:user-add-line"></iconify-icon>\n        Create User\n    </a>\n</div>\n{% endblock %}\n\n<div class="row gy-4">',
            text,
            flags=re.DOTALL
        )

        # Remove the 4th stats card and change columns to 4
        text = re.sub(r'col-xxl-3 col-xl-3 col-md-6', 'col-xxl-4 col-xl-4 col-md-4', text)
        text = re.sub(
            r'<div class="col-xxl-4 col-xl-4 col-md-4">\s*<div class="shadow-1 radius-12 bg-info-50 p-24 h-100 d-flex flex-column justify-content-center">.*?</div>\s*</div>\s*</div>\s*</div>\s*<!-- Main Content Area -->',
            r'</div>\n    </div>\n\n    <!-- Main Content Area -->',
            text,
            flags=re.DOTALL
        )

    elif filename == 'create.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</a>\s*</div>\s*<form method="post"',
            r'{% block heading_actions %}\n<a href="/users/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n    <iconify-icon icon="ri:arrow-left-line"></iconify-icon>\n    Back to Directory\n</a>\n{% endblock %}\n\n<form method="post"',
            text,
            flags=re.DOTALL
        )

    elif filename == 'edit.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</div>\s*</div>\s*<form method="post"',
            r'{% block heading_actions %}\n<div class="d-flex align-items-center gap-12">\n    {% if user_obj.id != request.user.id %}\n        <form method="post" action="/users/{{ user_obj.id }}/impersonate/" onsubmit="return confirm(\'Start impersonation session?\');" class="mb-0">\n            {% csrf_token %}\n            <button type="submit" class="btn btn-outline-primary d-flex align-items-center gap-6">\n                <iconify-icon icon="ri:user-shared-2-line"></iconify-icon>\n                Login As\n            </button>\n        </form>\n    {% endif %}\n    <a href="/users/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:arrow-left-line"></iconify-icon>\n        Back to Directory\n    </a>\n</div>\n{% endblock %}\n\n<form method="post"',
            text,
            flags=re.DOTALL
        )

    elif filename == 'import.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</div>\s*</div>\s*<div class="row gy-4">',
            r'{% block heading_actions %}\n<div class="d-flex align-items-center gap-6">\n    <a href="/users/import/sample/csv/" class="btn btn-outline-primary d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:download-line"></iconify-icon>\n        Download Sample CSV\n    </a>\n    <a href="/users/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:arrow-left-line"></iconify-icon>\n        Back to Directory\n    </a>\n</div>\n{% endblock %}\n\n<div class="row gy-4">',
            text,
            flags=re.DOTALL
        )

    elif filename == 'import_preview.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</div>\s*</div>\s*<div class="row gy-4">',
            r'{% block heading_actions %}\n<div class="d-flex align-items-center gap-6">\n    <a href="/users/import/" class="btn btn-outline-primary d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:upload-cloud-line"></iconify-icon>\n        Upload New File\n    </a>\n    <a href="/users/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:arrow-left-line"></iconify-icon>\n        Back to Directory\n    </a>\n</div>\n{% endblock %}\n\n<div class="row gy-4">',
            text,
            flags=re.DOTALL
        )

    elif filename == 'invitations.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</div>\s*</div>\s*<div class="row gy-4">',
            r'{% block heading_actions %}\n<div class="d-flex align-items-center gap-6">\n    <a href="/users/" class="btn btn-outline-primary d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:arrow-left-line"></iconify-icon>\n        Back to Directory\n    </a>\n    <a href="/users/invite/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n        <iconify-icon icon="ri:mail-send-line"></iconify-icon>\n        Invite User\n    </a>\n</div>\n{% endblock %}\n\n<div class="row gy-4">',
            text,
            flags=re.DOTALL
        )

    elif filename == 'invite.html':
        text = re.sub(
            r'<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">.*?</a>\s*</div>\s*<form method="post"',
            r'{% block heading_actions %}\n<a href="/users/" class="btn btn-primary-600 d-flex align-items-center gap-6">\n    <iconify-icon icon="ri:arrow-left-line"></iconify-icon>\n    Back to Directory\n</a>\n{% endblock %}\n\n<form method="post"',
            text,
            flags=re.DOTALL
        )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

for f in files:
    try:
        fix_file(f)
        print(f"Fixed {f}")
    except Exception as e:
        print(f"Error in {f}: {e}")

