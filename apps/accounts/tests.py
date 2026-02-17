
# apps/accounts/tests.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from .models import User, AdminProfile
import tempfile
from PIL import Image

User = get_user_model()

class AccountsTestCase(TestCase):
    """Test cases for accounts app"""
    
    def setUp(self):
        self.client = Client()
        # Create a test image
        self.image = self.create_test_image()
        
    def create_test_image(self):
        """Create a test image file"""
        image = Image.new('RGB', (100, 100), color='red')
        tmp_file = tempfile.NamedTemporaryFile(suffix='.jpg')
        image.save(tmp_file, format='JPEG')
        tmp_file.seek(0)
        return SimpleUploadedFile(
            'test.jpg', 
            tmp_file.read(), 
            content_type='image/jpeg'
        )
    
    def test_user_creation(self):
        """Test user creation"""
        user = User.objects.create_user(
            tsc_number='12345678',
            password='testpass123',
            id_number='87654321',
            full_name='Test User',
            school='Test School',
            county='Nairobi',
            user_type='VOTER'
        )
        self.assertEqual(user.tsc_number, '12345678')
        self.assertEqual(user.user_type, 'VOTER')
        self.assertTrue(user.check_password('testpass123'))
    
    def test_duplicate_tsc_number(self):
        """Test duplicate TSC number prevention"""
        User.objects.create_user(
            tsc_number='12345678',
            password='testpass123',
            id_number='87654321',
            full_name='Test User',
            school='Test School',
            county='Nairobi'
        )
        with self.assertRaises(Exception):
            User.objects.create_user(
                tsc_number='12345678',  # Duplicate
                password='testpass456',
                id_number='99999999',
                full_name='Another User',
                school='Another School',
                county='Mombasa'
            )
    
    def test_kyc_status_default(self):
        """Test default KYC status"""
        user = User.objects.create_user(
            tsc_number='12345678',
            password='testpass123',
            id_number='87654321',
            full_name='Test User',
            school='Test School',
            county='Nairobi'
        )
        self.assertEqual(user.kyc_status, 'PENDING')
    
    def test_vote_token_generation(self):
        """Test vote token is generated"""
        user = User.objects.create_user(
            tsc_number='12345678',
            password='testpass123',
            id_number='87654321',
            full_name='Test User',
            school='Test School',
            county='Nairobi'
        )
        self.assertIsNotNone(user.vote_token)
        self.assertEqual(len(str(user.vote_token)), 36)  # UUID length
    
    def test_registration_view_get(self):
        """Test registration page loads"""
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')
    
    def test_login_view_get(self):
        """Test login page loads"""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
    
    def tearDown(self):
        # Clean up any created files
        import shutil
        try:
            shutil.rmtree('media/test')
        except:
            pass