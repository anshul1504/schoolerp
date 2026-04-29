import sys
import re

content = '''{% block content %}
<div class="row gy-4">
    {% include "settings/_sidebar.html" %}

    <div class="col-xxl-9 col-lg-8">
        <div class="shadow-1 radius-12 bg-base h-100 overflow-hidden">
            <div class="card-header border-bottom bg-base py-16 px-24">
                <h6 class="text-lg fw-semibold mb-0">Backend Audit Based Settings Map</h6>
                <p class="text-sm text-secondary-light mb-0 mt-4">Showing only modules that already exist in backend routes and are actionable now.</p>
            </div>

            <div class="card-body p-24">
                <div class="d-flex gap-16 mb-24">
                    <span class="badge bg-primary-50 text-primary-600 px-16 py-8 radius-pill border border-primary-100 fw-medium">Core Settings: 7</span>
                    <span class="badge bg-warning-50 text-warning-600 px-16 py-8 radius-pill border border-warning-100 fw-medium">Platform Ops: 5</span>
                    <span class="badge bg-info-50 text-info-600 px-16 py-8 radius-pill border border-info-100 fw-medium">System Ops: 5</span>
                </div>

                <div class="mb-32">
                    <h6 class="text-md fw-semibold mb-16 pb-8 border-bottom border-neutral-100">Core Settings</h6>
                    <div class="row gy-3">
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/branding/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:palette-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Branding & Base Setup</h6>
                                        <p class="text-xs text-secondary-light mb-0">Product name, logos, theme colors</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/role-matrix/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:shield-keyhole-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Role Matrix</h6>
                                        <p class="text-xs text-secondary-light mb-0">Section-level access by role</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/permissions/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:lock-password-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Permissions Matrix</h6>
                                        <p class="text-xs text-secondary-light mb-0">Feature permissions by role</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/rbac-audit/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:file-list-3-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">RBAC Audit</h6>
                                        <p class="text-xs text-secondary-light mb-0">Role/permission change history</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/rbac-grants/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:user-settings-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">RBAC User Grants</h6>
                                        <p class="text-xs text-secondary-light mb-0">User-level grants and overrides</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/2fa/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:shield-check-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">2FA Policy</h6>
                                        <p class="text-xs text-secondary-light mb-0">Role/user based authentication policy</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/settings/email-test/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-primary-600 hover-bg-primary-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-primary-100 text-primary-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:mail-send-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">SMTP Email Test</h6>
                                        <p class="text-xs text-secondary-light mb-0">Outbound email delivery checks</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                    </div>
                </div>

                <div class="mb-32">
                    <h6 class="text-md fw-semibold mb-16 pb-8 border-bottom border-neutral-100">Platform Governance</h6>
                    <div class="row gy-3">
                        <div class="col-xl-4 col-md-6">
                            <a href="/platform/security/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-warning-600 hover-bg-warning-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-warning-100 text-warning-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:shield-star-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Platform Security</h6>
                                        <p class="text-xs text-secondary-light mb-0">Global policy and security controls</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/platform/domains/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-warning-600 hover-bg-warning-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-warning-100 text-warning-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:global-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Domain Management</h6>
                                        <p class="text-xs text-secondary-light mb-0">School domain mapping and governance</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/platform/tokens/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-warning-600 hover-bg-warning-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-warning-100 text-warning-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:key-2-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Integration Tokens</h6>
                                        <p class="text-xs text-secondary-light mb-0">API token provisioning and control</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/platform/announcements/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-warning-600 hover-bg-warning-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-warning-100 text-warning-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:megaphone-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Announcements</h6>
                                        <p class="text-xs text-secondary-light mb-0">Platform-wide communication controls</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/platform/support/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-warning-600 hover-bg-warning-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-warning-100 text-warning-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:customer-service-2-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Support Desk</h6>
                                        <p class="text-xs text-secondary-light mb-0">Operational support ticketing</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                    </div>
                </div>

                <div class="">
                    <h6 class="text-md fw-semibold mb-16 pb-8 border-bottom border-neutral-100">System Operations</h6>
                    <div class="row gy-3">
                        <div class="col-xl-4 col-md-6">
                            <a href="/billing/plans/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-info-600 hover-bg-info-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-info-100 text-info-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:bill-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Billing Plans</h6>
                                        <p class="text-xs text-secondary-light mb-0">Plans, tiers, and feature packaging</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/billing/invoices/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-info-600 hover-bg-info-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-info-100 text-info-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:file-text-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Invoices</h6>
                                        <p class="text-xs text-secondary-light mb-0">Invoice records and payment status</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/reports/builder/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-info-600 hover-bg-info-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-info-100 text-info-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:layout-grid-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Report Builder</h6>
                                        <p class="text-xs text-secondary-light mb-0">Custom reporting definitions</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/reports/scheduled/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-info-600 hover-bg-info-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-info-100 text-info-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:time-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Scheduled Reports</h6>
                                        <p class="text-xs text-secondary-light mb-0">Automated report run policies</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                        <div class="col-xl-4 col-md-6">
                            <a href="/activity/" class="d-block p-16 radius-8 border border-neutral-100 hover-border-info-600 hover-bg-info-50 transition-all h-100">
                                <div class="d-flex gap-12 align-items-start">
                                    <div class="w-40-px h-40-px bg-info-100 text-info-600 rounded-circle d-flex justify-content-center align-items-center text-xl flex-shrink-0">
                                        <iconify-icon icon="ri:history-line"></iconify-icon>
                                    </div>
                                    <div>
                                        <h6 class="text-sm fw-bold mb-4">Activity Log</h6>
                                        <p class="text-xs text-secondary-light mb-0">Audit visibility for platform actions</p>
                                    </div>
                                </div>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''

with open('templates/settings/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\{\% block content \%\}[\s\S]*?(?=\{\% endblock \%\})', content, text)

with open('templates/settings/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
