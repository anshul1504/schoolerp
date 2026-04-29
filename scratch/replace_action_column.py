import sys
import re

with open('templates/users/list.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace Management heading
text = text.replace(
    '<th class="py-16 px-24 text-neutral-600 fw-bold text-xs uppercase text-end">Management</th>',
    '<th class="py-16 px-24 text-neutral-600 fw-bold text-xs uppercase text-center">Action</th>'
)

# Replace the dropdown block with inline buttons
old_block = '''<td class="py-16 px-24 text-end">
                                    <div class="dropdown">
                                        <button class="btn btn-sm btn-neutral-100 text-neutral-600 radius-circle p-0 w-32-px h-32-px d-inline-flex justify-content-center align-items-center" type="button" data-bs-toggle="dropdown">
                                            <iconify-icon icon="ri:more-2-fill"></iconify-icon>
                                        </button>
                                        <ul class="dropdown-menu dropdown-menu-end border shadow-sm p-8">
                                            <li><a href="/users/{{ user.id }}/edit/" class="dropdown-item radius-4 py-8 text-xs fw-medium"><iconify-icon icon="ri:edit-line" class="me-8"></iconify-icon> Edit Profile</a></li>
                                            {% if user.id != request.user.id %}
                                                <li>
                                                    <form method="post" action="/users/{{ user.id }}/impersonate/" onsubmit="return confirm('Start impersonation session?');">
                                                        {% csrf_token %}
                                                        <button type="submit" class="dropdown-item radius-4 py-8 text-xs fw-medium text-info-600"><iconify-icon icon="ri:user-shared-2-line" class="me-8"></iconify-icon> Impersonate</button>
                                                    </form>
                                                </li>
                                            {% endif %}
                                            <li><a href="javascript:void(0)" class="dropdown-item radius-4 py-8 text-xs fw-medium text-warning-600" data-bs-toggle="modal" data-bs-target="#resetPasswordModal" data-user-id="{{ user.id }}" data-username="{{ user.username }}" data-reset-url="/users/{{ user.id }}/reset-password/"><iconify-icon icon="ri:key-2-line" class="me-8"></iconify-icon> Reset Password</a></li>
                                            {% if user.is_active and user.id != request.user.id %}
                                                <li><hr class="dropdown-divider"></li>
                                                <li><a href="javascript:void(0)" class="dropdown-item radius-4 py-8 text-xs fw-medium text-danger-600" data-bs-toggle="modal" data-bs-target="#deactivateUserModal" data-user-id="{{ user.id }}" data-username="{{ user.username }}" data-deactivate-url="/users/{{ user.id }}/deactivate/"><iconify-icon icon="ri:user-unfollow-line" class="me-8"></iconify-icon> Deactivate</a></li>
                                            {% endif %}
                                        </ul>
                                    </div>
                                </td>'''

new_block = '''<td class="py-16 px-24 text-center">
                                    <div class="d-flex align-items-center gap-10 justify-content-center">
                                        <!-- View -->
                                        <a href="/users/{{ user.id }}/edit/" class="bg-info-focus bg-hover-info-200 text-info-600 fw-medium w-32-px h-32-px d-flex justify-content-center align-items-center rounded-circle" title="View/Edit">
                                            <iconify-icon icon="majesticons:eye-line" class="icon text-lg"></iconify-icon>
                                        </a>

                                        <!-- Edit -->
                                        <a href="/users/{{ user.id }}/edit/" class="bg-success-focus bg-hover-success-200 text-success-600 fw-medium w-32-px h-32-px d-flex justify-content-center align-items-center rounded-circle" title="Edit">
                                            <iconify-icon icon="lucide:edit" class="icon text-lg"></iconify-icon>
                                        </a>

                                        <!-- Login As -->
                                        {% if user.id != request.user.id %}
                                            <form method="post" action="/users/{{ user.id }}/impersonate/" onsubmit="return confirm('Start impersonation session?');" class="d-inline mb-0">
                                                {% csrf_token %}
                                                <button type="submit" class="border-0 bg-primary-focus bg-hover-primary-200 text-primary-600 fw-medium w-32-px h-32-px d-flex justify-content-center align-items-center rounded-circle" title="Login As">
                                                    <iconify-icon icon="ri:user-shared-2-line" class="icon text-lg"></iconify-icon>
                                                </button>
                                            </form>
                                        {% endif %}

                                        <!-- More Actions -->
                                        <div class="dropdown">
                                            <button class="border-0 bg-neutral-100 bg-hover-neutral-200 text-neutral-600 fw-medium w-32-px h-32-px d-flex justify-content-center align-items-center rounded-circle" type="button" data-bs-toggle="dropdown" title="More">
                                                <iconify-icon icon="ri:more-2-fill" class="icon text-lg"></iconify-icon>
                                            </button>
                                            <ul class="dropdown-menu dropdown-menu-end border shadow-sm p-8">
                                                <li><a href="javascript:void(0)" class="dropdown-item radius-4 py-8 text-xs fw-medium text-warning-600" data-bs-toggle="modal" data-bs-target="#resetPasswordModal" data-user-id="{{ user.id }}" data-username="{{ user.username }}" data-reset-url="/users/{{ user.id }}/reset-password/"><iconify-icon icon="ri:key-2-line" class="me-8"></iconify-icon> Reset Password</a></li>
                                                {% if user.is_active and user.id != request.user.id %}
                                                    <li><hr class="dropdown-divider"></li>
                                                    <li><a href="javascript:void(0)" class="dropdown-item radius-4 py-8 text-xs fw-medium text-danger-600" data-bs-toggle="modal" data-bs-target="#deactivateUserModal" data-user-id="{{ user.id }}" data-username="{{ user.username }}" data-deactivate-url="/users/{{ user.id }}/deactivate/"><iconify-icon icon="ri:user-unfollow-line" class="me-8"></iconify-icon> Deactivate</a></li>
                                                {% endif %}
                                            </ul>
                                        </div>
                                    </div>
                                </td>'''

text = text.replace(old_block, new_block)

with open('templates/users/list.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
