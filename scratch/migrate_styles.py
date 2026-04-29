import os
import re

# Define mappings for bulk replacement
MAPPINGS = {
    r'class="sf-card\b': 'class="card radius-12 border-neutral-200',
    r'class="sf-card__body\b': 'class="card-body',
    r'class="sf-table\b': 'class="table bordered-table mb-0',
    r'class="sf-toolbar\b': 'class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24',
    r'class="sf-actions\b': 'class="d-flex flex-wrap gap-2',
    r'class="sf-toolbar__title\b': 'class="mb-0',
    r'class="sf-avatar\b': 'class="radius-8 bg-primary-50 text-primary-600 d-flex align-items-center justify-content-center',
    r'class="sf-pill\b': 'class="badge',
    r'class="student-pill\b': 'class="badge',
    r'class="sf-hero\b': 'class="card bg-primary-600 border-0 radius-12 overflow-hidden mb-4',
    r'class="sf-hero__eyebrow\b': 'class="badge bg-white text-primary-600 mb-2',
    r'class="sf-hero__title\b': 'class="text-white mb-1',
    r'class="sf-hero__meta\b': 'class="text-white opacity-75 text-sm',
    r'class="sf-th-': 'class="text-xs text-secondary-light font-bold ',
    r'class="status-pill\b': 'class="badge',
    r'class="status-pill--success\b': 'class="bg-success-50 text-success-600',
    r'class="status-pill--warning\b': 'class="bg-warning-50 text-warning-600',
    r'class="status-pill--danger\b': 'class="bg-danger-50 text-danger-600',
    r'class="sf-btn-primary\b': 'class="btn btn-primary-600 radius-8',
    r'class="sf-btn-secondary\b': 'class="btn btn-outline-secondary radius-8',
}

TEMPLATE_DIR = 'templates'

def migrate_templates():
    count = 0
    for root, dirs, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content
                for pattern, replacement in MAPPINGS.items():
                    content = re.sub(pattern, replacement, content)

                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Migrated: {file_path}")
                    count += 1

    print(f"Total files migrated: {count}")

if __name__ == '__main__':
    migrate_templates()
