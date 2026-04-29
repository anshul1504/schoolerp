import sys
import re

content = '''{% block content %}
<div class="row gy-4">
    {% include "settings/_sidebar.html" %}

    <div class="col-xxl-9 col-lg-8">
        <div class="row gy-4">
            <div class="col-12">
                <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
                    <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                        <h6 class="text-lg fw-semibold mb-0">Search Grants</h6>
                        <small class="text-neutral-400">Filter by user ID, actor, or change payload text.</small>
                    </div>
                    <div class="card-body p-24">
                        <form method="get" class="row gy-3 align-items-end">
                            <div class="col-md-8">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Search</label>
                                <input type="text" name="q" class="form-control" value="{{ filters.q }}" placeholder="user id or text">
                            </div>
                            <div class="col-md-4 d-flex gap-12 justify-content-end">
                                <a href="/settings/" class="btn btn-neutral-100 text-neutral-600 px-24 py-10 radius-8 fw-semibold">Back</a>
                                <a href="/settings/rbac-grants/" class="btn btn-outline-secondary px-24 py-10 radius-8 fw-semibold">Reset</a>
                                <button type="submit" class="btn btn-primary-600 px-24 py-10 radius-8 fw-semibold shadow-primary">Search</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-12">
                <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
                    <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                        <h6 class="text-lg fw-semibold mb-0">Grant Events</h6>
                        <span class="badge bg-primary-50 text-primary-600 border border-primary-100 px-12 py-4 radius-pill fw-medium">Latest updates</span>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table align-middle table-hover mb-0">
                                <thead class="bg-neutral-50 text-neutral-500 text-xs fw-semibold">
                                    <tr>
                                        <th class="px-24 py-12">When</th>
                                        <th class="px-24 py-12">Actor</th>
                                        <th class="px-24 py-12">User ID</th>
                                        <th class="px-24 py-12">Changes</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for e in logs %}
                                        <tr>
                                            <td class="px-24 py-16 text-muted text-sm">{{ e.created_at }}</td>
                                            <td class="px-24 py-16 text-primary-light fw-medium">{% if e.actor %}{{ e.actor.username }}{% else %}-{% endif %}</td>
                                            <td class="px-24 py-16">
                                                <code class="bg-neutral-50 border border-neutral-100 radius-4 px-8 py-4 text-xs text-neutral-600 d-inline-block">{{ e.object_id }}</code>
                                            </td>
                                            <td class="px-24 py-16">
                                                <code class="bg-neutral-50 border border-neutral-100 radius-4 px-8 py-4 text-xs text-neutral-600 d-inline-block text-truncate" style="max-width:300px;">{{ e.changes }}</code>
                                            </td>
                                        </tr>
                                    {% empty %}
                                        <tr>
                                            <td colspan="4" class="p-48 text-center text-muted">
                                                <iconify-icon icon="ri:inbox-2-line" class="text-4xl mb-12 d-block"></iconify-icon>
                                                No grant events yet.
                                            </td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''

with open('templates/settings/rbac_user_grants.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\{\% block content \%\}[\s\S]*?(?=\{\% endblock \%\})', content, text)

# fix the duplicate endblock again
text = re.sub(r'\{\%\s*endblock\s*\%\}\s*\{\%\s*endblock\s*\%\}', r'{% endblock %}', text)

with open('templates/settings/rbac_user_grants.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
