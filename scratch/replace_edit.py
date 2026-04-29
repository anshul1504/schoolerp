import sys
import re

content = '''{% block content %}
<div class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-24">
    <div class="">
        <h1 class="fw-semibold mb-4 h6 text-primary-light">Modifying: {{ user_obj.username }}</h1>
        <div class="d-flex align-items-center gap-12">
            <a href="/" class="text-secondary-light hover-text-primary hover-underline">Dashboard</a>
            <a href="/users/" class="text-secondary-light hover-text-primary hover-underline"> / User Directory</a>
            <span class="text-secondary-light">/ Edit Account</span>
            {% if user_obj.is_active %}
                <span class="badge bg-success-50 text-success-600 border border-success-100 text-xs radius-pill px-12 py-4 ms-2">Active Account</span>
            {% else %}
                <span class="badge bg-neutral-50 text-neutral-400 border border-neutral-100 text-xs radius-pill px-12 py-4 ms-2">Restricted</span>
            {% endif %}
        </div>
    </div>
    <a href="/users/" class="btn btn-primary-600 d-flex align-items-center gap-6">
        <iconify-icon icon="ri:arrow-left-line"></iconify-icon>
        Back to Directory
    </a>
</div>

<form method="post" class="mt-24" id="userEditForm">
    {% csrf_token %}
    <div class="row gy-4">
        <!-- Section 1: Basic Identity -->
        <div class="col-lg-12">
            <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
                <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                    <h6 class="text-lg fw-semibold mb-0">1. Identity & Contact</h6>
                </div>
                <div class="card-body p-20">
                    <div class="row gy-3">
                        <div class="col-xxl-3 col-xl-4 col-sm-6">
                            <div class="">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">System Username <span class="text-danger-600">*</span></label>
                                <input type="text" name="username" class="form-control bg-neutral-50" value="{{ user_obj.username }}" required>
                            </div>
                        </div>
                        <div class="col-xxl-3 col-xl-4 col-sm-6">
                            <div class="">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Email Address</label>
                                <input type="email" name="email" class="form-control" value="{{ user_obj.email|default:'' }}" placeholder="e.g. john@example.com">
                            </div>
                        </div>
                        <div class="col-xxl-3 col-xl-4 col-sm-6">
                            <div class="">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">First Name</label>
                                <input type="text" name="first_name" class="form-control" value="{{ user_obj.first_name|default:'' }}" placeholder="Enter first name">
                            </div>
                        </div>
                        <div class="col-xxl-3 col-xl-4 col-sm-6">
                            <div class="">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Last Name</label>
                                <input type="text" name="last_name" class="form-control" value="{{ user_obj.last_name|default:'' }}" placeholder="Enter last name">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Section 2: Permissions & Scope -->
        <div class="col-lg-12">
            <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
                <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                    <h6 class="text-lg fw-semibold mb-0">2. Permissions & Scope</h6>
                </div>
                <div class="card-body p-20">
                    <div class="row gy-3">
                        <div class="col-xxl-6 col-xl-6 col-sm-6">
                            <div class="">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">System Role <span class="text-danger-600">*</span></label>
                                <select name="role" class="form-control form-select" required>
                                    {% for group_label, options in grouped_role_choices %}
                                        <optgroup label="{{ group_label }}">
                                            {% for value,label in options %}
                                                <option value="{{ value }}" {% if user_obj.role == value %}selected{% endif %}>{{ label }}</option>
                                            {% endfor %}
                                        </optgroup>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                        <div class="col-xxl-6 col-xl-6 col-sm-6">
                            <div class="">
                                <label class="text-sm fw-semibold text-primary-light d-inline-block mb-8">Institutional Scope</label>
                                <select name="school_id" class="form-control form-select" id="userSchoolSelect">
                                    <option value="" {% if not user_obj.school_id %}selected{% endif %}>Global Platform Access</option>
                                    {% for school in schools %}
                                        <option value="{{ school.id }}" {% if user_obj.school_id == school.id %}selected{% endif %}>{{ school.name }}</option>
                                    {% endfor %}
                                </select>
                                <small class="text-neutral-400 mt-8 d-block" id="schoolHint">Required for non-Super Admin users.</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Section 3: Status & Account Control -->
        <div class="col-lg-12">
            <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
                <div class="card-header border-bottom bg-base py-16 px-24 d-flex align-items-center justify-content-between">
                    <h6 class="text-lg fw-semibold mb-0">3. Account Control</h6>
                </div>
                <div class="card-body p-20">
                    <div class="row gy-3 align-items-center">
                        <div class="col-xxl-6 col-xl-6 col-sm-6">
                            <div class="form-check form-switch p-0 d-flex align-items-center gap-12 ms-4">
                                <input class="form-check-input ms-0" type="checkbox" name="is_active" id="is_active" {% if user_obj.is_active %}checked{% endif %} role="switch">
                                <label class="form-check-label text-sm fw-semibold text-secondary-light mb-0" for="is_active">Account Activation Status</label>
                            </div>
                        </div>
                        <div class="col-xxl-6 col-xl-6 col-sm-6 text-end">
                            <button type="button" class="btn btn-outline-warning fw-semibold px-16 radius-8" data-bs-toggle="modal" data-bs-target="#resetPasswordModal">
                                <iconify-icon icon="ri:key-2-line" class="me-4"></iconify-icon> Force Password Reset
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="col-lg-12 d-flex gap-16 justify-content-end mb-24">
            <a href="/users/" class="btn btn-neutral-100 text-neutral-600 px-32 py-12 radius-8 fw-semibold">Discard Changes</a>
            <button type="submit" class="btn btn-primary-600 px-32 py-12 radius-8 fw-semibold shadow-primary">Save Profile Updates</button>
        </div>
    </div>
</form>
'''

with open('templates/users/edit.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\{\% block content \%\}[\s\S]*?(?=<!-- Password Reset Modal)', content, text)

with open('templates/users/edit.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
