from django.urls import path
from . import views

urlpatterns = [
    # Diagnostic endpoint
    path('check-setup/', views.check_setup, name='check_setup'),
    
    # Gmail OAuth endpoints
    path('authorize/', views.authorize, name='gmail_authorize'),
    path('oauth2callback/', views.oauth2callback, name='gmail_oauth2callback'),
    
    # Email extraction endpoints
    path('extract-emails/', views.extract_credit_card_emails, name='extract_credit_card_emails'),
    path('check-new-emails/', views.check_new_credit_card_emails, name='check_new_credit_card_emails'),
]


