from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # ==================== DASHBOARD ====================
    path('', views.AdminDashboardView.as_view(), name='dashboard'),
    path('superuser-dashboard/', views.SuperuserDashboardView.as_view(), name='superuser_dashboard'),
    
    # ==================== ELECTION MANAGEMENT ====================
    # Elections
    path('elections/', views.ElectionListView.as_view(), name='election_list'),
    path('elections/create/', views.ElectionCreateView.as_view(), name='election_create'),
    path('elections/<int:pk>/', views.ElectionDetailView.as_view(), name='election_detail'),
    path('elections/<int:pk>/edit/', views.ElectionUpdateView.as_view(), name='election_edit'),
    path('elections/<int:pk>/delete/', views.ElectionDeleteView.as_view(), name='election_delete'),
    
    # All Positions LIST page (positions_manage.html)
    path('positions/', views.AllPositionsListView.as_view(), name='all_positions'),
    
    # Create Position FORM page (position_form.html) - WITH ELECTION DROPDOWN
    path('positions/create/', views.PositionCreateView.as_view(), name='position_create'),
    
    # Edit Position FORM page (position_form.html)
    path('positions/<int:pk>/edit/', views.PositionUpdateView.as_view(), name='position_edit'),
    
    # Delete Position
    path('positions/<int:pk>/delete/', views.PositionDeleteView.as_view(), name='position_delete'),
    
    # Position Candidates
    path('positions/<int:position_id>/candidates/', views.PositionCandidatesView.as_view(), name='position_candidates'),
    
    # Reorder Positions
    path('positions/reorder/', views.reorder_positions, name='reorder_positions'),
    
    # Election-specific Positions (for a specific election)
    path('elections/<int:election_id>/positions/', views.ElectionPositionsView.as_view(), name='election_positions'),
    path('elections/<int:election_id>/positions/add/', views.ElectionPositionCreateView.as_view(), name='election_position_add'),
    path('elections/<int:election_id>/positions/<int:pk>/edit/', views.PositionUpdateView.as_view(), name='election_position_edit'),
    path('elections/<int:election_id>/positions/<int:pk>/delete/', views.PositionDeleteView.as_view(), name='election_position_delete'),
    path('positions/download-template/', views.download_position_template, name='download_position_template'),
    path('positions/bulk-upload/', views.bulk_upload_positions, name='bulk_upload_positions'),
    # Election Candidates
    path('elections/<int:election_id>/positions/<int:position_id>/candidates/', views.ElectionPositionCandidatesView.as_view(), name='election_position_candidates'),
    path('elections/<int:election_id>/positions/<int:position_id>/candidates/add/', views.ElectionCandidateCreateView.as_view(), name='election_candidate_add'),
    path('elections/<int:election_id>/positions/<int:position_id>/candidates/<int:pk>/edit/', views.ElectionCandidateUpdateView.as_view(), name='election_candidate_edit'),
    path('elections/<int:election_id>/positions/<int:position_id>/candidates/<int:candidate_id>/delete/', views.election_candidate_delete, name='election_candidate_delete'),
    path('elections/<int:election_id>/positions/<int:position_id>/candidates/reorder/', views.reorder_election_candidates, name='election_candidates_reorder'),
    path('elections/<int:election_id>/positions/<int:position_id>/candidates/<int:candidate_id>/toggle-active/', views.toggle_candidate_active, name='toggle_candidate_active'),
    
    # All Candidates LIST page (candidates/list.html)
    path('candidates/', views.AllCandidatesListView.as_view(), name='candidate_list'),
    
    # Create Candidate FORM page (election/candidate_form.html) - WITH ELECTION AND POSITION DROPDOWNS
        
    # Edit Candidate FORM page (election/candidate_form.html)
        
    # Delete Candidate
        
    # All Teams LIST page (teams/list.html)
    path('teams/', views.TeamListView.as_view(), name='team_list'),
    
    # Create Team FORM page (teams/form.html)
        
    # Edit Team FORM page (teams/form.html)
        
    # Delete Team
        
    # Election Results
    path('elections/<int:election_id>/results/', views.ElectionResultsView.as_view(), name='election_results'),
    path('elections/<int:election_id>/results/download/', views.download_election_results, name='download_election_results'),
    
    # ==================== CANDIDATE APPLICATIONS ====================
    path('candidates/applications/', views.CandidateApplicationListView.as_view(), name='candidate_applications'),
    path('candidates/applications/<int:pk>/', views.CandidateApplicationDetailView.as_view(), name='candidate_application_detail'),
    path('candidates/applications/<int:pk>/approve/', views.approve_candidate_application, name='approve_candidate_application'),
    path('candidates/applications/<int:pk>/reject/', views.reject_candidate_application, name='reject_candidate_application'),
    path('candidates/applications/<int:pk>/details/', views.candidate_application_details, name='candidate_application_details'),
    
    # ==================== TEAM APPLICATIONS ====================
    path('teams/applications/', views.TeamApplicationListView.as_view(), name='team_applications'),
    path('teams/applications/<int:pk>/approve/', views.approve_team_application, name='approve_team_application'),
    path('teams/applications/<int:pk>/reject/', views.reject_team_application, name='reject_team_application'),
    path('teams/applications/<int:pk>/details/', views.team_application_details, name='team_application_details'),
    
    # ==================== VOTER MANAGEMENT ====================
    path('voters/', views.VoterManagementView.as_view(), name='voter_list'),
    path('voters/<int:voter_id>/', views.VoterDetailView.as_view(), name='voter_detail'),
    path('voters/<int:voter_id>/verify-kyc/', views.verify_voter_kyc, name='verify_voter_kyc'),
    path('voters/<int:voter_id>/verify-tsc/', views.verify_voter_tsc, name='verify_voter_tsc'),
    path('voters/<int:voter_id>/suspend/', views.suspend_voter, name='suspend_voter'),
    path('voters/<int:voter_id>/activate/', views.activate_voter, name='activate_voter'),
    path('voters/<int:voter_id>/delete/', views.delete_voter, name='delete_voter'),
    path('voters/suspended/', views.SuspendedVotersView.as_view(), name='suspended_voters'),
    path('voters/deletion-requests/', views.VoterDeletionRequestsView.as_view(), name='voter_deletion_requests'),
    path('voters/deletion-requests/<int:request_id>/approve/', views.approve_deletion_request, name='approve_deletion_request'),
    path('voters/deletion-requests/<int:request_id>/reject/', views.reject_deletion_request, name='reject_deletion_request'),
    path('voters/bulk-action/', views.bulk_voter_action, name='bulk_voter_action'),
    
    # ==================== KYC VERIFICATION ====================
    path('kyc/pending/', views.PendingKYCView.as_view(), name='pending_kyc'),
    path('kyc/<int:voter_id>/', views.KYCDetailView.as_view(), name='kyc_detail'),
    path('kyc/<int:voter_id>/verify/', views.verify_kyc, name='verify_kyc'),
    path('kyc/<int:voter_id>/reject/', views.reject_kyc, name='reject_kyc'),
    path('kyc/<int:voter_id>/documents/', views.view_kyc_documents, name='view_kyc_documents'),
    path('kyc/stats/', views.kyc_statistics, name='kyc_stats'),
    
    # ==================== TSC VERIFICATION ====================
    path('tsc/pending/', views.PendingTSCView.as_view(), name='pending_tsc'),
    path('tsc/<int:voter_id>/verify/', views.verify_tsc, name='verify_tsc'),
    path('tsc/<int:voter_id>/reject/', views.reject_tsc, name='reject_tsc'),
    path('tsc/stats/', views.tsc_statistics, name='tsc_stats'),
    
    # ==================== ADMIN MANAGEMENT (SUPERUSER ONLY) ====================
    path('admins/', views.AdminListView.as_view(), name='admin_list'),
    path('admins/pending/', views.PendingAdminApprovalsView.as_view(), name='pending_admin_approvals'),
    path('admins/<int:admin_id>/', views.AdminDetailView.as_view(), name='admin_detail'),
    path('admins/<int:admin_id>/approve/', views.approve_admin, name='approve_admin'),
    path('admins/<int:admin_id>/reject/', views.reject_admin, name='reject_admin'),
    path('admins/<int:admin_id>/suspend/', views.suspend_admin, name='suspend_admin'),
    path('admins/<int:admin_id>/activate/', views.activate_admin, name='activate_admin'),
    path('admins/<int:admin_id>/delete/', views.delete_admin, name='delete_admin'),
    path('admins/<int:admin_id>/permissions/', views.edit_admin_permissions, name='edit_admin_permissions'),
   
    # ==================== DEVICE RESET REQUESTS ====================
    path('device-resets/', views.DeviceResetRequestsView.as_view(), name='device_reset_requests'),
    path('device-resets/<int:request_id>/', views.DeviceResetDetailView.as_view(), name='device_reset_detail'),
    path('device-resets/<int:request_id>/approve/', views.approve_device_reset, name='approve_device_reset'),
    path('device-resets/<int:request_id>/reject/', views.reject_device_reset, name='reject_device_reset'),
    path('device-resets/stats/', views.device_reset_statistics, name='device_reset_stats'),
    
    # ==================== ELECTION MONITORING ====================
    path('monitoring/live/', views.LiveElectionMonitoringView.as_view(), name='live_monitoring'),
    path('monitoring/data/', views.live_monitoring_data, name='live_monitoring_data'),
    
    # ==================== REPORTS AND ANALYTICS ====================
    path('reports/voter-turnout/', views.voter_turnout_report, name='voter_turnout_report'),
    path('reports/kyc-status/', views.kyc_status_report, name='kyc_status_report'),
    path('reports/vote-counts/', views.vote_counts_report, name='vote_counts_report'),
    path('reports/activity-log/', views.activity_log_report, name='activity_log_report'),
    path('reports/export/<str:report_type>/', views.export_report, name='export_report'),
    
    # ==================== AUDIT LOGS (SUPERUSER ONLY) ====================
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('audit-logs/<int:log_id>/', views.AuditLogDetailView.as_view(), name='audit_log_detail'),
    
    # ==================== NOTIFICATIONS ====================
    path('notifications/', views.AdminNotificationListView.as_view(), name='admin_notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/unread-count/', views.unread_notifications_count, name='unread_notifications_count'),
    path('notifications/recent/', views.recent_notifications, name='recent_notifications'),
    
    # ==================== SYSTEM SETTINGS (SUPERUSER ONLY) ====================
    path('settings/general/', views.GeneralSettingsView.as_view(), name='general_settings'),
    path('settings/security/', views.SecuritySettingsView.as_view(), name='security_settings'),
    path('settings/email/', views.EmailSettingsView.as_view(), name='email_settings'),
    path('settings/backup/', views.BackupSettingsView.as_view(), name='backup_settings'),
    path('settings/maintenance/', views.MaintenanceSettingsView.as_view(), name='maintenance_mode'),
    
    # Maintenance endpoints
    path('settings/logs/', views.get_system_logs, name='system_logs'),
    path('settings/download-logs/', views.download_system_logs, name='download_logs'),
    path('settings/clear-logs/', views.clear_system_logs, name='clear_logs'),
    
    # ==================== DATA MANAGEMENT ====================
    path('data/backups/', views.BackupListView.as_view(), name='backup_list'),
    path('data/backup/create/', views.create_backup, name='create_backup'),
    path('data/backup/<str:backup_id>/delete/', views.delete_backup, name='delete_backup'),
    path('data/backup/<str:backup_id>/download/', views.download_backup, name='download_backup'),
    
    # ==================== API ENDPOINTS ====================
    path('api/realtime-stats/', views.get_realtime_stats, name='realtime_stats'),
    path('api/dashboard-stats/', views.get_dashboard_stats, name='dashboard_stats'),
    path('api/kyc-stats/', views.get_kyc_stats, name='api_kyc_stats'),
    path('api/voter-stats/', views.get_voter_stats, name='voter_stats'),
    path('api/election-stats/', views.get_election_stats, name='election_stats'),
    path('api/activity-feed/', views.get_activity_feed, name='activity_feed'),
    path('api/find-voter/', views.find_voter, name='find_voter'),
    path('api/deletion-requests/count/', views.deletion_requests_count, name='deletion_requests_count'),
    path('api/candidate-applications/count/', views.candidate_applications_count, name='candidate_applications_count'),
    path('api/team-applications/count/', views.team_applications_count, name='team_applications_count'),
    path('api/admin-pending-count/', views.admin_pending_count, name='admin_pending_count'),
    path('api/voter-status/<int:voter_id>/', views.voter_status, name='voter_status'),

    # ==================== DATA MANAGEMENT ====================
path('data/backups/', views.BackupListView.as_view(), name='backup_list'),
path('data/backup/create/', views.create_backup, name='create_backup'),
path('data/backup/<str:backup_id>/', views.backup_details, name='backup_details'),
path('data/backup/<str:backup_id>/download/', views.download_backup, name='download_backup'),
path('data/backup/<str:backup_id>/delete/', views.delete_backup, name='delete_backup'),
path('data/backup/<str:backup_id>/restore/', views.restore_backup, name='restore_backup'),
path('data/backups/delete-bulk/', views.bulk_delete_backups, name='bulk_delete_backups'),
]