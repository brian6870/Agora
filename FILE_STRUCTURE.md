agora_voting/

├── agora.db.backup
├── am1.py
├── FILE_STRUCTURE.md
├── fix.py
├── fix2.py
├── manage.py
├── PROJECT_STRUCTURE.md
├── requirements.txt
├── setup_windows.bat
├── tailwind.config.js

├── agora_backend/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── __pycache__/

├── apps/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── accounts/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── signals.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   ├── utils.py
│   │   ├── views.py
│   │   ├── __pycache__/
│   │   └── migrations/
│   ├── admin_panel/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── __pycache__/
│   │   └── migrations/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── context_processors.py
│   │   ├── middleware.py
│   │   ├── models.py
│   │   ├── security.py
│   │   ├── signals.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   ├── views.py
│   │   ├── __pycache__/
│   │   └── migrations/
│   └── voting/
│       ├── __init__.py
│       ├── admin.py
│       ├── apps.py
│       ├── models.py
│       ├── tests.py
│       ├── views.py
│       ├── __pycache__/
│       └── migrations/

├── backups/

├── deployment/
│   ├── deploy.sh
│   ├── gunicorn.conf.py
│   ├── nginx.conf
│   └── supervisor.conf

├── logs/
│   ├── gunicorn/
│   └── nginx/

├── media/
│   ├── admin/
│   │   ├── faces/
│   │   └── ids/
│   ├── candidates/
│   │   └── 2026-02-14_at_18.58.41.jpeg
│   ├── kyc/
│   │   ├── faces/
│   │   └── ids/
│   └── teams/
│       ├── download.png
│       └── download_aOwRYKb.png

├── scripts/
│   ├── backup_db.sh
│   ├── reset_election.py
│   └── verify_kyc.py

├── static/
│   ├── css/
│   │   ├── admin.css
│   │   ├── style.css
│   │   └── voting.css
│   ├── images/
│   │   ├── default-avatar.png
│   │   ├── favicon.ico
│   │   ├── logo-dark.png
│   │   ├── logo-light.png
│   │   └── logo.png
│   ├── js/
│   │   ├── camera.js
│   │   ├── counties.js
│   │   ├── fingerprint.js
│   │   ├── loading.js
│   │   ├── main.js
│   │   ├── ocr.js
│   │   ├── registration.js
│   │   ├── theme.js
│   │   ├── timer.js
│   │   └── voting.js
│   └── vendor/
│       ├── bootstrap/
│       └── fontawesome/

├── staticfiles/

├── templates/
│   ├── base.html
│   ├── accounts/
│   │   ├── delete_account.html
│   │   ├── device_reset.html
│   │   ├── landing.html
│   │   ├── login.html
│   │   ├── password_reset_request.html
│   │   ├── password_reset_verify.html
│   │   ├── register.html
│   │   ├── registration_complete.html
│   │   ├── reset_request_complete.html
│   │   └── terms.html
│   ├── admin_panel/
│   │   ├── admin_device_reset.html
│   │   ├── admin_login.html
│   │   ├── admin_password_reset_request.html
│   │   ├── admin_password_reset_verify.html
│   │   ├── admin_register.html
│   │   ├── admin_reset_request_complete.html
│   │   ├── base_admin.html
│   │   ├── dashboard.html
│   │   ├── superuser_dashboard.html
│   │   ├── admins/
│   │   │   ├── confirm_delete_admin.html
│   │   │   ├── create.html
│   │   │   ├── detail.html
│   │   │   ├── edit_permissions.html
│   │   │   ├── list.html
│   │   │   └── pending.html
│   │   ├── audit/
│   │   │   ├── action_logs.html
│   │   │   ├── detail.html
│   │   │   ├── logs.html
│   │   │   └── user_logs.html
│   │   ├── candidates/
│   │   │   ├── applications.html
│   │   │   └── list.html
│   │   ├── data/
│   │   │   └── backups.html
│   │   ├── device_resets/
│   │   │   ├── detail.html
│   │   │   └── list.html
│   │   ├── election/
│   │   │   ├── candidate_form.html
│   │   │   ├── date.html
│   │   │   ├── form.html
│   │   │   ├── list.html
│   │   │   ├── positions.html
│   │   │   ├── positions_manage.html
│   │   │   ├── position_candidates.html
│   │   │   └── position_form.html
│   │   ├── kyc/
│   │   │   ├── detail.html
│   │   │   ├── documents.html
│   │   │   └── pending.html
│   │   ├── monitoring/
│   │   │   └── live.html
│   │   ├── notifications/
│   │   │   └── list.html
│   │   ├── reports/
│   │   │   ├── activity_log.html
│   │   │   ├── kyc_status.html
│   │   │   ├── voter_turnout.html
│   │   │   └── vote_counts.html
│   │   ├── settings/
│   │   │   ├── backup.html
│   │   │   ├── email.html
│   │   │   ├── general.html
│   │   │   ├── maintenance.html
│   │   │   └── security.html
│   │   ├── teams/
│   │   │   ├── applications.html
│   │   │   └── list.html
│   │   ├── tsc/
│   │   │   └── pending.html
│   │   └── voters/
│   │       ├── confirm_delete_voter.html
│   │       ├── deletion_requests.html
│   │       ├── detail.html
│   │       ├── list.html
│   │       └── suspended.html
│   ├── core/
│   │   ├── about.html
│   │   ├── base_page.html
│   │   ├── cookie_policy.html
│   │   ├── data_protection.html
│   │   ├── faq.html
│   │   ├── how_it_works.html
│   │   ├── mission.html
│   │   ├── privacy_policy.html
│   │   ├── security.html
│   │   └── terms_of_service.html
│   ├── emails/
│   │   ├── admin_approval_request.html
│   │   ├── candidate_application_approved.html
│   │   ├── candidate_application_received.html
│   │   ├── candidate_application_rejected.html
│   │   ├── request_approved.html
│   │   ├── request_received.html
│   │   ├── request_rejected.html
│   │   └── team_application_approved.html
│   ├── errors/
│   │   ├── 404.html
│   │   ├── 500.html
│   │   └── custom_50x.html
│   ├── includes/
│   │   ├── footer.html
│   │   ├── header.html
│   │   ├── messages.html
│   │   ├── navigation.html
│   │   └── terms_modal.html
│   └── voter/
│       ├── application_status.html
│       ├── apply_candidate.html
│       ├── create_team.html
│       ├── dashboard.html
│       ├── election_positions.html
│       ├── election_results.html
│       ├── elections.html
│       ├── results.html
│       └── voting_area.html

├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_security.py
│   └── test_voting.py

└── venv/
	├── .gitignore
	├── Include/
	├── Lib/
	├── Scripts/
	└── pyvenv.cfg