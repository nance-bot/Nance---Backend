from django.contrib import admin
from .models import GmailEmail, GmailToken

admin.site.register(GmailEmail)
admin.site.register(GmailToken)


