from django.urls import path
from . import views
from . import results_views  # Import the new views

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.VoterDashboardView.as_view(), name='dashboard'),
    
    # Voting
    path('vote/', views.VotingAreaView.as_view(), name='voting_area'),
    
    # Results - Using the new dedicated results view
    path('results/', results_views.LiveResultsView.as_view(), name='results'),
    path('elections/<int:pk>/results/', results_views.ElectionResultsView.as_view(), name='election_results'),
    
    
    
    # Candidate Applications
    path('apply-candidate/', views.ApplyCandidateView.as_view(), name='apply_candidate'),
    path('create-team/', views.CreateTeamView.as_view(), name='create_team'),
    path('application-status/', views.ApplicationStatusView.as_view(), name='application_status'),
    
    # Elections
    path('elections/', views.ElectionsView.as_view(), name='elections'),
    path('elections/<int:pk>/positions/', views.ElectionPositionsView.as_view(), name='election_positions'),
    
    # Static Pages
    path('about/', views.AboutView.as_view(), name='about'),
    path('mission/', views.MissionView.as_view(), name='mission'),
    path('how-it-works/', views.HowItWorksView.as_view(), name='how_it_works'),
    path('security/', views.SecurityView.as_view(), name='security'),
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('privacy-policy/', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms-of-service/', views.TermsOfServiceView.as_view(), name='terms_of_service'),
    path('cookie-policy/', views.CookiePolicyView.as_view(), name='cookie_policy'),
    path('data-protection/', views.DataProtectionView.as_view(), name='data_protection'),
]