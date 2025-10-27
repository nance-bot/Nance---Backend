from django.urls import path
from . import views  # assuming views.py has the functions
from rest_framework_simplejwt.views import TokenRefreshView
urlpatterns = [
    #for otp
    path("auth/request-otp/", views.request_otp),
    path("auth/verify-otp/", views.verify_otp),

    # 🔁 Refresh token
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    #for AA
    path("consent/create/", views.create_consent, name="create_consent"),
    path("consent/<str:consent_id>/status/", views.poll_consent_status, name="poll_consent_status"),
    path("session/create/", views.create_session, name="create_session"),
    path("session/<str:session_id>/transactions/", views.fetch_transactions, name="fetch_transactions"),

    #for SMS
    path("receive-sms/", views.receive_sms_transaction, name="receive_sms"),
    path("receive-sms-message/", views.receive_sms_message, name="receive_sms_message"),

    #call ml model
    path("ml-model/",views.call_ml_model, name="call_ml_model"),

    #Gmail Integration
    path('authorize/', views.authorize, name='authorize'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),

    # Email extraction endpoints
    path('extract-emails/', views.extract_credit_card_emails, name='extract_credit_card_emails'),
    path('check-new-emails/', views.check_new_credit_card_emails, name='check_new_credit_card_emails'),

]
