
# apps/admin_panel/tests.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.voting.models import Position, Team, Candidate, ElectionSettings
from apps.accounts.models import User

User = get_user_model()

class AdminPanelTestCase(TestCase):
    """Test cases for admin panel"""
    
    def setUp(self):
        # Create admin user
        self.admin = User.objects.create_user(
            tsc_number='admin123',
            password='adminpass123',
            id_number='admin123',
            full_name='Admin User',
            school='Admin HQ',
            county='Nairobi',
            user_type='ADMIN',
            is_staff=True
        )
        
        # Create test data
        self.position = Position.objects.create(
            order=1,
            name='Test Position'
        )
        
        self.team = Team.objects.create(
            name='Test Team',
            color_code='#FF0000'
        )
        
        self.client = Client()
        self.client.login(tsc_number='admin123', password='adminpass123')
    
    def test_admin_dashboard_access(self):
        """Test admin dashboard access"""
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_panel/dashboard.html')
    
    def test_candidate_list_view(self):
        """Test candidate list view"""
        response = self.client.get(reverse('admin_panel:candidate_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_candidate_creation(self):
        """Test candidate creation"""
        data = {
            'position': self.position.pk,
            'team': self.team.pk,
            'full_name': 'New Candidate',
            'bio': 'Test bio',
            'order': 1,
            'is_active': True
        }
        response = self.client.post(reverse('admin_panel:candidate_add'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(Candidate.objects.filter(full_name='New Candidate').exists())
    
    def test_voter_list_view(self):
        """Test voter list view"""
        response = self.client.get(reverse('admin_panel:voter_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_election_settings_view(self):
        """Test election settings view"""
        response = self.client.get(reverse('admin_panel:election_settings'))
        self.assertEqual(response.status_code, 200)
    
    def test_unauthorized_access(self):
        """Test unauthorized access is blocked"""
        self.client.logout()
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login