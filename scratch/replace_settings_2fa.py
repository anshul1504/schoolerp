import sys
import re

content = '''{% block content %}
<div class="row gy-4">
    {% include "settings/_sidebar.html" %}

    <div class="col-xxl-9 col-lg-8">
        <form method="post" class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
            {% csrf_token %}
            <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                <h6 class="text-lg fw-semibold mb-0">2FA Enforcement Policy</h6>
                <small class="text-neutral-400">SUPER_ADMIN always requires OTP. Global env flag can still force OTP for all users.</small>
            </div>

            <div class="card-body p-24">
                <div class="row gy-4">
                    <div class="col-12">
                        <label class="form-label text-sm fw-semibold text-primary-light d-inline-block mb-8">Require OTP for roles</label>
                        {% for group_label, options in grouped_role_choices %}
                            <div class="mb-24">
                                <h6 class="text-md fw-semibold mb-16">{{ group_label }}</h6>
                                <div class="row gy-3">
                                    {% for value,label in options %}
                                        {% if value != "SUPER_ADMIN" %}
                                            <div class="col-md-4 col-sm-6">
                                                <div class="form-check d-flex align-items-center gap-2">
                                                    <input class="form-check-input w-20-px h-20-px cursor-pointer" type="checkbox" name="roles" id="role_{{ value }}" value="{{ value }}" {% if value in policy.require_for_roles %}checked{% endif %}>
                                                    <label class="form-check-label text-neutral-600 fw-medium cursor-pointer" for="role_{{ value }}">{{ label }}</label>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>
                        {% endfor %}
                        <p class="text-xs text-neutral-400 mt-8"><i class="ri-information-line me-4"></i>Tip: Start with high-risk operational roles first.</p>
                    </div>

                    <div class="col-12">
                        <label class="form-label text-sm fw-semibold text-primary-light d-inline-block mb-8">Require OTP for user IDs</label>
                        <input type="text" name="user_ids" class="form-control" value="{{ policy.require_for_user_ids|join:', ' }}" placeholder="e.g. 12, 45, 78">
                        <p class="text-xs text-neutral-400 mt-8"><i class="ri-information-line me-4"></i>Use this for exceptions without changing full role policies.</p>
                    </div>
                </div>
            </div>

            <div class="card-footer border-top bg-base py-16 px-24 d-flex justify-content-end gap-12">
                <a href="/settings/2fa/" class="btn btn-outline-secondary px-24 py-12 radius-8 fw-semibold">Reset</a>
                <button type="submit" class="btn btn-primary-600 px-24 py-12 radius-8 fw-semibold shadow-primary">Save Policy</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
'''

with open('templates/settings/two_factor_policy.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\{\% block content \%\}[\s\S]*?(?=\{\% endblock \%\})', content, text)

# fix the duplicate endblock
text = re.sub(r'\{\%\s*endblock\s*\%\}\s*\{\%\s*endblock\s*\%\}', r'{% endblock %}', text)

with open('templates/settings/two_factor_policy.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
