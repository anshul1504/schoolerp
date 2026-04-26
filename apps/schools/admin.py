from django.contrib import admin

from .models import PlanFeature, School, SchoolSubscription, SubscriptionInvoice, SubscriptionPayment, SubscriptionPlan

admin.site.register(School)
admin.site.register(SubscriptionPlan)
admin.site.register(SchoolSubscription)
admin.site.register(SubscriptionInvoice)
admin.site.register(SubscriptionPayment)
admin.site.register(PlanFeature)
