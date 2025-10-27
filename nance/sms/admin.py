from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from sms.models import * 
# Register your models here.

admin.site.register(CustomUser, UserAdmin)
admin.site.register(OTPRequest) 
admin.site.register(AAConsent)
admin.site.register(AADataSession)
admin.site.register(RawAATransaction)
admin.site.register(RawSMSTransaction)
admin.site.register(GmailEmail)
admin.site.register(SMSMessage)