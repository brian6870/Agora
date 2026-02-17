
# apps/core/tests.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from apps.voting.models import ElectionSettings, Position, Team, Candidate
from apps.core.middleware import DeviceFingerprintMiddleware
import json

User = get_user_model()

class CoreTestCase(TestCase):
    """Test cases for core functionality"""
    
    def setUp(self):
        self.client = Client()
        
        # Create voter
        self.voter = User.objects.create_user(
            tsc_number='voter123',
            password='voterpass123',
            id_number='voter123',
            full_name='Test Voter',
            school='Test School',
            county='Nairobi',
            user_type='VOTER',
            kyc_status='VERIFIED'
        )
        
        # Create election settings
        self.election = ElectionSettings.objects.create(
            election_name='Test Election',
            voting_date=timezone.now().date(),
            voting_start_time=timezone.now().time(),
            voting_end_time=(timezone.now() + timezone.timedelta(hours=8)).time(),
            allow_voting=True,
            status='ACTIVE'
        )
        
        # Create test candidate
        position = Position.objects.create(order=1, name='Test Position')
        team = Team.objects.create(name='Test Team')
        self.candidate = Candidate.objects.create(
            position=position,
            team=team,
            full_name='Test Candidate'
        )
    
    def test_dashboard_view_authenticated(self):
        """Test dashboard access for authenticated user"""
        self.client.login(tsc_number='voter123', password='voterpass123')
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'voter/dashboard.html')
    
    def test_dashboard_view_unauthenticated(self):
        """Test dashboard access for unauthenticated user"""
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_voting_area_access_before_vote(self):
        """Test voting area access"""
        self.client.login(tsc_number='voter123', password='voterpass123')
        response = self.client.get(reverse('core:voting_area'))
        self.assertEqual(response.status_code, 200)
    
    def test_results_view(self):
        """Test results page"""
        response = self.client.get(reverse('core:results'))
        self.assertEqual(response.status_code, 200)
    
    def test_live_results_api(self):
        """Test live results API"""
        response = self.client.get(
            reverse('core:live_results'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('stats', data)
    
    def test_middleware_fingerprint_generation(self):
        """Test device fingerprint generation"""
        middleware = DeviceFingerprintMiddleware(lambda x: None)
        request = self.client.request().wsgi_request
        fingerprint = middleware.get_device_fingerprint(request)
        self.assertIsNotNone(fingerprint)
        self.assertEqual(len(fingerprint), 64)  # SHA256 hash length