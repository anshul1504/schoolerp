import sys
import re

content = '''{% block content %}
<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">
    <div class="">
        <h1 class="fw-semibold mb-4 h6 text-primary-light">User Management</h1>
        <div class="">
            <a href="/" class="text-secondary-light hover-text-primary hover-underline">Dashboard</a>
            <span class="text-secondary-light">/ User Directory</span>
        </div>
    </div>
</div>

<div class="row gy-4">
    <!-- User Stats Summary -->
    <div class="col-12">
        <div class="row gy-3">
            <div class="col-xxl-3 col-xl-3 col-md-6">
                <div class="shadow-1 radius-12 bg-primary-50 p-24 h-100">
                    <div class="d-flex align-items-center justify-content-between mb-12">
                        <span class="text-primary-600 fw-bold text-xs uppercase letter-spacing-1">Total Directory</span>
                        <iconify-icon icon="ri:group-line" class="text-2xl text-primary-600"></iconify-icon>
                    </div>
                    <h3 class="mb-4">{{ stats.total_users }}</h3>
                    <p class="text-xs text-primary-light mb-0">Total registered platform users</p>
                </div>
            </div>
            <div class="col-xxl-3 col-xl-3 col-md-6">
                <div class="shadow-1 radius-12 bg-success-50 p-24 h-100">
                    <div class="d-flex align-items-center justify-content-between mb-12">
                        <span class="text-success-600 fw-bold text-xs uppercase letter-spacing-1">Active Accounts</span>
                        <iconify-icon icon="ri:user-follow-line" class="text-2xl text-success-600"></iconify-icon>
                    </div>
                    <h3 class="mb-4">{{ stats.active_users }}</h3>
                    <p class="text-xs text-success-light mb-0">Users with platform access</p>
                </div>
            </div>
            <div class="col-xxl-3 col-xl-3 col-md-6">
                <div class="shadow-1 radius-12 bg-warning-50 p-24 h-100">
                    <div class="d-flex align-items-center justify-content-between mb-12">
                        <span class="text-warning-600 fw-bold text-xs uppercase letter-spacing-1">Inactive</span>
                        <iconify-icon icon="ri:user-forbid-line" class="text-2xl text-warning-600"></iconify-icon>
                    </div>
                    <h3 class="mb-4">{{ stats.inactive_users }}</h3>
                    <p class="text-xs text-warning-light mb-0">Access currently restricted</p>
                </div>
            </div>
            <div class="col-xxl-3 col-xl-3 col-md-6">
                <div class="shadow-1 radius-12 bg-info-50 p-24 h-100 d-flex flex-column justify-content-center">
                    <div class="d-flex gap-2">
                        <a href="/users/invite/" class="btn btn-primary-600 w-100 radius-8 py-10 fw-semibold"><i class="ri-mail-send-line me-2"></i>Invite</a>
                        <a href="/users/create/" class="btn btn-outline-primary w-100 radius-8 py-10 fw-semibold"><i class="ri-user-add-line me-2"></i>Create</a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Main Content Area -->
    <div class="col-12">
        <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
            <div class="card-header bg-base border-bottom py-16 px-24">
                <form method="get" class="row gy-3 align-items-end">
                    <input type="hidden" name="status" value="{{ filters.status }}">
                    <div class="col-lg-3 col-md-6">
                        <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Search Users</label>
                        <div class="input-group">
                            <span class="input-group-text bg-neutral-50 border-neutral-200 text-neutral-400"><iconify-icon icon="ri:search-line"></iconify-icon></span>
                            <input type="text" name="q" class="form-control" value="{{ filters.q }}" placeholder="Search name, email...">
                        </div>
                    </div>
                    <div class="col-lg-2 col-md-6">
                        <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Role Filter</label>
                        <select name="role" class="form-control form-select">
                            <option value="">All Roles</option>
                            {% for group_label, options in grouped_role_choices %}
                                <optgroup label="{{ group_label }}">
                                    {% for value,label in options %}
                                        <option value="{{ value }}" {% if filters.role == value %}selected{% endif %}>{{ label }}</option>
                                    {% endfor %}
                                </optgroup>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-lg-2 col-md-6">
                        <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Institution Filter</label>
                        <select name="school_id" class="form-control form-select">
                            <option value="">All Institutions</option>
                            {% for school in schools %}
                                <option value="{{ school.id }}" {% if filters.school_id|stringformat:"s" == school.id|stringformat:"s" %}selected{% endif %}>{{ school.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-lg-3 col-md-6 d-flex gap-8">
                        <button type="submit" class="btn btn-primary-600 px-16 fw-semibold d-flex align-items-center gap-2"><iconify-icon icon="ri:filter-3-line"></iconify-icon> Apply Filter</button>
                        <a href="/users/" class="btn btn-neutral-100 text-neutral-600 px-16 fw-semibold">Reset</a>
                    </div>
                    <div class="col-lg-2 col-md-12 text-end">
                        <div class="dropdown">
                            <button class="btn btn-outline-neutral-200 dropdown-toggle text-sm fw-semibold px-16" type="button" data-bs-toggle="dropdown">
                                Export Data
                            </button>
                            <ul class="dropdown-menu dropdown-menu-end border shadow-sm">
                                <li><a class="dropdown-item text-sm" href="javascript:void(0)" id="exportSelectedCsvBtn">Export CSV</a></li>
                                <li><a class="dropdown-item text-sm" href="javascript:void(0)" id="exportSelectedExcelBtn">Export Excel</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item text-sm" href="/users/import/">Import from File</a></li>
                            </ul>
                        </div>
                    </div>
                </form>
            </div>

            <div class="card-body p-0">'''

with open('templates/users/list.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\{\% block content \%\}[\s\S]*?<div class=\"card-body p-0\">', content, text)

with open('templates/users/list.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
