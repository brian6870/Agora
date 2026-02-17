#!/usr/bin/env python
"""
Production database seeding script for Agora Voting System
This script ONLY creates user accounts:
- Super admin account
- Verified admin account
- Sample voter account
- Verified voters from Tharaka Nithi

No elections, teams, candidates, or votes are created.
"""

import os
import sys
import django
from django.contrib.auth.hashers import make_password
from django.db import transaction

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings')
django.setup()

from apps.accounts.models import User

# ==================== CONFIGURATION ====================

# Credentials (will be printed at the end)
SUPER_ADMIN_EMAIL = "superadmin@agora.ke"
SUPER_ADMIN_PASSWORD = "SuperAdmin@2026"
SUPER_ADMIN_TSC = "SUPER001"
SUPER_ADMIN_ID = "30000001"

ADMIN_EMAIL = "admin@agora.ke"
ADMIN_PASSWORD = "Admin@2026"
ADMIN_TSC = "ADMIN001"
ADMIN_ID = "30000002"

VOTER_EMAIL = "voter@agora.ke" 
VOTER_PASSWORD = "Voter@2026"
VOTER_TSC = "VOTER001"
VOTER_ID = "40000001"

# Tharaka Nithi voters
THARAKA_NITHI_VOTERS = [
    {"full_name": "John Muthomi", "tsc_number": "TN001", "id_number": "10000001"},
    {"full_name": "Mary Kathure", "tsc_number": "TN002", "id_number": "10000002"},
    {"full_name": "Peter Gitonga", "tsc_number": "TN003", "id_number": "10000003"},
    {"full_name": "Jane Nkirote", "tsc_number": "TN004", "id_number": "10000004"},
    {"full_name": "Samuel Mugambi", "tsc_number": "TN005", "id_number": "10000005"},
    {"full_name": "Grace Makena", "tsc_number": "TN006", "id_number": "10000006"},
    {"full_name": "David Kimathi", "tsc_number": "TN007", "id_number": "10000007"},
    {"full_name": "Esther Kajuju", "tsc_number": "TN008", "id_number": "10000008"},
    {"full_name": "Joseph Muriuki", "tsc_number": "TN009", "id_number": "10000009"},
    {"full_name": "Ruth Kaari", "tsc_number": "TN010", "id_number": "10000010"},
    {"full_name": "Francis Mwenda", "tsc_number": "TN011", "id_number": "10000011"},
    {"full_name": "Dorcas Muthoni", "tsc_number": "TN012", "id_number": "10000012"},
    {"full_name": "Patrick Mugendi", "tsc_number": "TN013", "id_number": "10000013"},
    {"full_name": "Lucy Karimi", "tsc_number": "TN014", "id_number": "10000014"},
    {"full_name": "Bernard Kinyua", "tsc_number": "TN015", "id_number": "10000015"},
]

class UserOnlySeeder:
    """Seed ONLY user accounts in the database"""
    
    def __init__(self):
        self.super_admin = None
        self.admin = None
        self.voter = None
        
    @transaction.atomic
    def seed(self):
        """Run all user seeding operations"""
        print("🌱 Starting user-only data seeding...")
        print("="*60)
        
        self.create_super_admin()
        self.create_admin()
        self.create_voter()
        self.create_tharaka_nithi_voters()
        
        print("="*60)
        print("✅ User seeding complete!")
        self.print_credentials()
        
    def create_super_admin(self):
        """Create super admin account"""
        print("\n👑 Creating super admin...")
        self.super_admin, created = User.objects.get_or_create(
            email=SUPER_ADMIN_EMAIL,
            defaults={
                'full_name': 'System Super Admin',
                'user_type': 'SUPER_ADMIN',
                'tsc_number': SUPER_ADMIN_TSC,
                'id_number': SUPER_ADMIN_ID,
                'kyc_status': 'VERIFIED',
                'tsc_verified': True,
                'account_status': 'ACTIVE',
                'is_active': True,
                'is_staff': True,
                'is_superuser': True,
                'email_verified': True,
                'county': 'Nairobi',
                'password': make_password(SUPER_ADMIN_PASSWORD)
            }
        )
        if created:
            print(f"  ✅ Super admin created: {SUPER_ADMIN_EMAIL}")
        else:
            print(f"  ℹ️ Super admin already exists")
    
    def create_admin(self):
        """Create regular admin account"""
        print("\n👤 Creating admin...")
        self.admin, created = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                'full_name': 'System Administrator',
                'user_type': 'ADMIN',
                'tsc_number': ADMIN_TSC,
                'id_number': ADMIN_ID,
                'kyc_status': 'VERIFIED',
                'tsc_verified': True,
                'account_status': 'ACTIVE',
                'is_active': True,
                'is_staff': True,
                'email_verified': True,
                'county': 'Nairobi',
                'password': make_password(ADMIN_PASSWORD)
            }
        )
        if created:
            print(f"  ✅ Admin created: {ADMIN_EMAIL}")
        else:
            print(f"  ℹ️ Admin already exists")
    
    def create_voter(self):
        """Create sample voter account"""
        print("\n👤 Creating sample voter...")
        self.voter, created = User.objects.get_or_create(
            email=VOTER_EMAIL,
            defaults={
                'full_name': 'Sample Voter',
                'user_type': 'VOTER',
                'tsc_number': VOTER_TSC,
                'id_number': VOTER_ID,
                'kyc_status': 'VERIFIED',
                'tsc_verified': True,
                'account_status': 'ACTIVE',
                'is_active': True,
                'email_verified': True,
                'county': 'Tharaka Nithi',
                'password': make_password(VOTER_PASSWORD)
            }
        )
        if created:
            print(f"  ✅ Sample voter created: {VOTER_EMAIL}")
        else:
            print(f"  ℹ️ Sample voter already exists")
    
    def create_tharaka_nithi_voters(self):
        """Create verified voters from Tharaka Nithi"""
        print(f"\n👥 Creating {len(THARAKA_NITHI_VOTERS)} Tharaka Nithi voters...")
        
        created_count = 0
        skipped_count = 0
        
        for voter_data in THARAKA_NITHI_VOTERS:
            email = f"{voter_data['tsc_number'].lower()}@agora.ke"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': voter_data['full_name'],
                    'user_type': 'VOTER',
                    'tsc_number': voter_data['tsc_number'],
                    'id_number': voter_data['id_number'],
                    'kyc_status': 'VERIFIED',
                    'tsc_verified': True,
                    'account_status': 'ACTIVE',
                    'is_active': True,
                    'email_verified': True,
                    'county': 'Tharaka Nithi',
                    'password': make_password('Voter@2026')
                }
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1
        
        print(f"  ✅ Created {created_count} new Tharaka Nithi voters")
        if skipped_count > 0:
            print(f"  ℹ️ {skipped_count} voters already existed")
    
    def print_credentials(self):
        """Print login credentials"""
        print("\n" + "="*60)
        print("🔐 LOGIN CREDENTIALS")
        print("="*60)
        print("\n👑 SUPER ADMIN:")
        print(f"  TSC Number: {SUPER_ADMIN_TSC}")
        print(f"  Password:   {SUPER_ADMIN_PASSWORD}")
        print(f"  Email:      {SUPER_ADMIN_EMAIL}")
        
        print("\n👤 ADMIN:")
        print(f"  TSC Number: {ADMIN_TSC}")
        print(f"  Password:   {ADMIN_PASSWORD}")
        print(f"  Email:      {ADMIN_EMAIL}")
        
        print("\n👤 SAMPLE VOTER:")
        print(f"  TSC Number: {VOTER_TSC}")
        print(f"  Password:   {VOTER_PASSWORD}")
        print(f"  Email:      {VOTER_EMAIL}")
        
        print("\n👥 THARAKA NITHI VOTERS:")
        print(f"  Password for all: Voter@2026")
        print(f"  Example: TSC: TN001, Email: tn001@agora.ke")
        print(f"  Total voters: {len(THARAKA_NITHI_VOTERS)}")
        print("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🗳️  KUPPET VOTING SYSTEM - USER ONLY SEEDER")
    print("="*60)
    print("This script will ONLY create user accounts.")
    print("No elections, teams, candidates, or votes will be created.\n")
    
    # Check if running on Render
    if os.environ.get('RENDER'):
        print("📡 Running on Render platform")
    
    seeder = UserOnlySeeder()
    seeder.seed()