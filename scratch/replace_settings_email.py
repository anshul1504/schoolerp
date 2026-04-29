import sys
import re

content = '''{% block content %}
<div class="row gy-4">
    {% include "settings/_sidebar.html" %}

    <div class="col-xxl-9 col-lg-8">
        <form method="post" class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
            {% csrf_token %}
            <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                <h6 class="text-lg fw-semibold mb-0">SMTP Test</h6>
                <small class="text-neutral-400">Sends an HTML + text email to validate SMTP credentials.</small>
            </div>

            <div class="card-body p-24">
                <div class="row gy-4">
                    <div class="col-12">
                        <label class="form-label text-sm fw-semibold text-primary-light d-inline-block mb-8">Recipient email</label>
                        <input type="email" name="to_email" class="form-control" placeholder="name@example.com" required>
                    </div>
                </div>

                <div class="mt-24 p-16 bg-primary-50 border border-primary-100 radius-8">
                    <p class="text-sm text-primary-600 mb-0">
                        <i class="ri-information-line me-8"></i>
                        Uses <code>EMAIL_HOST</code>, <code>EMAIL_PORT</code>, <code>EMAIL_HOST_USER</code>, and <code>EMAIL_HOST_PASSWORD</code> from environment configuration.
                    </p>
                </div>
            </div>

            <div class="card-footer border-top bg-base py-16 px-24 d-flex justify-content-end gap-12">
                <button type="submit" class="btn btn-primary-600 px-24 py-12 radius-8 fw-semibold shadow-primary">
                    <i class="ri-mail-send-line me-8"></i>Send Test Email
                </button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
'''

with open('templates/settings/email_test.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\{\% block content \%\}[\s\S]*?(?=\{\% endblock \%\})', content, text)

# fix duplicate endblock
text = re.sub(r'\{\%\s*endblock\s*\%\}\s*\{\%\s*endblock\s*\%\}', r'{% endblock %}', text)

with open('templates/settings/email_test.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
