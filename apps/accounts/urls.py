from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'accounts'

urlpatterns = [
    # ==================== REGISTRATION AND LOGIN ====================
    path('register/', views.VoterRegistrationView.as_view(), name='register'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('get-otp-status/', views.get_otp_status, name='get_otp_status'),
    path('save-step1/', views.save_step1_data, name='save_step1'),
    path('get-step1/', views.get_step1_data, name='get_step1'),
    path('login/', views.VoterLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ==================== PASSWORD RESET ====================
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/verify/', views.PasswordResetVerifyView.as_view(), name='password_reset_verify'),
    
    # ==================== COMPLETION PAGES ====================
    path('registration-complete/', TemplateView.as_view(
        template_name='accounts/registration_complete.html'
    ), name='registration_complete'),
    
    # ==================== DEVICE RESET ====================
    path('device-reset/', views.DeviceResetRequestView.as_view(), name='device_reset'),
    path('reset-request-complete/', TemplateView.as_view(
        template_name='accounts/reset_request_complete.html'
    ), name='reset_request_complete'),
    
    # ==================== TERMS ====================
    path('terms/', TemplateView.as_view(
        template_name='accounts/terms.html'
    ), name='terms'),
    
    # ==================== AJAX ENDPOINTS ====================
    path('check-tsc/', views.check_tsc_availability, name='check_tsc'),
    path('check-id/', views.check_id_availability, name='check_id'),
    path('check-email/', views.check_email_availability, name='check_email'),
    
    # ==================== ACCOUNT MANAGEMENT ====================
    # Account deletion
    path('delete-account/', views.DeleteAccountRequestView.as_view(), name='delete_account'),
    path('cancel-deletion/', views.CancelDeletionRequestView.as_view(), name='cancel_deletion'),
    
    # Profile management
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.MarkNotificationReadView.as_view(), name='mark_notification_read'),
    path('notifications/read-all/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_notifications_read'),
    
    # ==================== ADMIN URLS ====================
    # Admin authentication
    path('admin-login/', views.AdminLoginView.as_view(), name='admin_login'),
    path('admin-register/', views.AdminRegistrationView.as_view(), name='admin_register'),
    path('admin-password-reset/', views.AdminPasswordResetRequestView.as_view(), name='admin_password_reset_request'),
    path('admin-password-reset/verify/', views.AdminPasswordResetVerifyView.as_view(), name='admin_password_reset_verify'),
    path('admin-device-reset/', views.AdminDeviceResetRequestView.as_view(), name='admin_device_reset'),
    path('admin-reset-request-complete/', TemplateView.as_view(
        template_name='admin_panel/admin_reset_request_complete.html'
    ), name='admin_reset_request_complete'),
    path('get-otp-status/', views.get_otp_status, name='get_otp_status'),
    
    # Admin approval (for superusers)
    path('admin/pending/', views.PendingAdminApprovalsView.as_view(), name='pending_admin_approvals'),
    path('admin/<int:admin_id>/approve/', views.approve_admin, name='approve_admin'),
    path('admin/<int:admin_id>/reject/', views.reject_admin, name='reject_admin'),
    path('admin/<int:admin_id>/assign-id/', views.assign_admin_id, name='assign_admin_id'),
    
    # Admin management
    path('admin/list/', views.AdminListView.as_view(), name='admin_list'),
    path('admin/<int:admin_id>/', views.AdminDetailView.as_view(), name='admin_detail'),
    path('admin/<int:admin_id>/suspend/', views.suspend_admin, name='suspend_admin'),
    path('admin/<int:admin_id>/activate/', views.activate_admin, name='activate_admin'),
    path('admin/<int:admin_id>/delete/', views.delete_admin, name='delete_admin'),
    
    # ==================== VOTER MANAGEMENT (ADMIN) ====================
    path('voters/suspended/', views.SuspendedVotersView.as_view(), name='suspended_voters'),
    path('voters/deletion-requests/', views.DeletionRequestsView.as_view(), name='deletion_requests'),
    path('voters/<int:voter_id>/suspend/', views.suspend_voter, name='suspend_voter'),
    path('voters/<int:voter_id>/activate/', views.activate_voter, name='activate_voter'),
    path('voters/<int:voter_id>/delete/', views.delete_voter, name='delete_voter'),
    path('voters/<int:voter_id>/approve-deletion/', views.approve_deletion, name='approve_deletion'),
    path('voters/<int:voter_id>/reject-deletion/', views.reject_deletion, name='reject_deletion'),
    
    # ==================== KYC VERIFICATION (ADMIN) ====================
    path('kyc/pending/', views.PendingKYCView.as_view(), name='pending_kyc'),
    path('kyc/<int:voter_id>/verify/', views.verify_kyc, name='verify_kyc'),
    path('kyc/<int:voter_id>/reject/', views.reject_kyc, name='reject_kyc'),
    path('kyc/<int:voter_id>/documents/', views.view_kyc_documents, name='view_kyc_documents'),
    
    # ==================== TSC VERIFICATION (ADMIN) ====================
    path('tsc/pending/', views.PendingTSCView.as_view(), name='pending_tsc'),
    path('tsc/<int:voter_id>/verify/', views.verify_tsc, name='verify_tsc'),
    path('tsc/<int:voter_id>/reject/', views.reject_tsc, name='reject_tsc'),
    
    # ==================== AUDIT LOGS (SUPERUSER ONLY) ====================
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('audit-logs/<int:log_id>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    path('audit-logs/export/', views.export_audit_logs, name='export_audit_logs'),
    path('audit-logs/user/<int:user_id>/', views.UserAuditLogsView.as_view(), name='user_audit_logs'),
    path('audit-logs/action/<str:action>/', views.ActionAuditLogsView.as_view(), name='action_audit_logs'),
    
    # ==================== STATISTICS API ENDPOINTS ====================
    path('api/kyc-stats/', views.kyc_statistics, name='kyc_stats'),
    path('api/tsc-stats/', views.tsc_statistics, name='tsc_stats'),
]

# ==================== API ENDPOINTS (AJAX) ====================
# These are additional API endpoints that return JSON responses
api_patterns = [
    path('api/check-tsc/', views.check_tsc_availability, name='api_check_tsc'),
    path('api/check-id/', views.check_id_availability, name='api_check_id'),
    path('api/check-email/', views.check_email_availability, name='api_check_email'),
    path('api/send-otp/', views.send_otp, name='api_send_otp'),
    path('api/verify-otp/', views.verify_otp, name='api_verify_otp'),
    path('api/otp-status/', views.get_otp_status, name='api_otp_status'),
]

# Add API patterns to urlpatterns
urlpatterns += api_patterns