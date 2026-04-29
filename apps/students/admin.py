from django.contrib import admin

from .models import (
    AdmissionWorkflowEvent,
    Student,
    StudentClassChangeHistory,
    StudentCommunicationLog,
    StudentComplianceReminder,
    StudentDisciplineIncident,
    StudentDocument,
    StudentHealthRecord,
    StudentProfileEditHistory,
    StudentPromotion,
    TransferCertificate,
    TransferCertificateRequest,
)

admin.site.register(Student)
admin.site.register(StudentDocument)
admin.site.register(StudentPromotion)
admin.site.register(TransferCertificate)
admin.site.register(AdmissionWorkflowEvent)
admin.site.register(StudentProfileEditHistory)
admin.site.register(StudentClassChangeHistory)
admin.site.register(TransferCertificateRequest)
admin.site.register(StudentDisciplineIncident)
admin.site.register(StudentHealthRecord)
admin.site.register(StudentComplianceReminder)
admin.site.register(StudentCommunicationLog)
