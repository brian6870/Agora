#!/usr/bin/env python
"""
Production database seeding script for Agora Voting System
This script creates:
- Super admin account
- Verified admin accounts
- Verified voters from Tharaka Nithi
- Complete election with positions from the image
- Simulated voting with 3 teams
- Published results
"""

import os
import sys
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db import transaction

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings')
django.setup()

from apps.accounts.models import User
from apps.voting.models import (
    Election, Position, Team, Candidate, 
    CandidateApplication, Vote, VoteAuditLog
)
from apps.core.models import ElectionSettings

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

# Positions from the image
POSITIONS = [
    {"order": 1, "name": "Executive Secretary", "max_votes": 1},
    {"order": 2, "name": "Assistant Executive Secretary", "max_votes": 1},
    {"order": 3, "name": "Chair Person", "max_votes": 1},
    {"order": 4, "name": "Vice Chair Person", "max_votes": 1},
    {"order": 5, "name": "Treasurer", "max_votes": 1},
    {"order": 6, "name": "Vice Treasurer", "max_votes": 1},
    {"order": 7, "name": "Secretary Gender", "max_votes": 1},
    {"order": 8, "name": "Secretary Tertiary", "max_votes": 1},
    {"order": 9, "name": "Secretary Secondary", "max_votes": 1},
    {"order": 10, "name": "Organising Secretary", "max_votes": 1},
    {"order": 11, "name": "Secretary Jss", "max_votes": 1},
    {"order": 12, "name": "Youth Rep", "max_votes": 1},
    {"order": 13, "name": "1st Assistant Gender", "max_votes": 1},
    {"order": 14, "name": "2nd Assistant sec Gender PWD", "max_votes": 1},
]

# Teams
TEAMS = [
    {"name": "The Real Deal", "acronym": "TRD", "color_code": "#FF0000"},
    {"name": "KUPPET Savior", "acronym": "KPS", "color_code": "#0000FF"},
    {"name": "Unity Alliance", "acronym": "UA", "color_code": "#00FF00"},
]

# Candidates mapping (position -> list of candidates with team assignments)
CANDIDATES = {
    "Executive Secretary": [
        {"full_name": "Njeibu James", "team": "The Real Deal"},
        {"full_name": "Kamau Peter", "team": "KUPPET Savior"},
        {"full_name": "Mwangi John", "team": "Unity Alliance"},
    ],
    "Assistant Executive Secretary": [
        {"full_name": "Mbaka Michelini", "team": "The Real Deal"},
        {"full_name": "Wanjiku Jane", "team": "KUPPET Savior"},
        {"full_name": "Kipchoge Eliud", "team": "Unity Alliance"},
    ],
    "Chair Person": [
        {"full_name": "Mambo Misiani", "team": "The Real Deal"},
        {"full_name": "Odhiambo Tom", "team": "KUPPET Savior"},
        {"full_name": "Wekesa Michael", "team": "Unity Alliance"},
    ],
    "Vice Chair Person": [
        {"full_name": "Linda Nkatha", "team": "The Real Deal"},
        {"full_name": "Mwende Syokau", "team": "KUPPET Savior"},
        {"full_name": "Atieno Beryl", "team": "Unity Alliance"},
    ],
    "Treasurer": [
        {"full_name": "Poly Nyamu", "team": "The Real Deal"},
        {"full_name": "Mutua David", "team": "KUPPET Savior"},
        {"full_name": "Kilonzo Stephen", "team": "Unity Alliance"},
    ],
    "Vice Treasurer": [
        {"full_name": "Michael Kathenya", "team": "The Real Deal"},
        {"full_name": "Njeri Anne", "team": "KUPPET Savior"},
        {"full_name": "Chebet Sharon", "team": "Unity Alliance"},
    ],
    "Secretary Gender": [
        {"full_name": "Sarah Muchoki", "team": "The Real Deal"},
        {"full_name": "Auma Pauline", "team": "KUPPET Savior"},
        {"full_name": "Jeruto Mercy", "team": "Unity Alliance"},
    ],
    "Secretary Tertiary": [
        {"full_name": "Emma", "team": "The Real Deal"},
        {"full_name": "Mukami Grace", "team": "KUPPET Savior"},
        {"full_name": "Wairimu Ann", "team": "Unity Alliance"},
    ],
    "Secretary Secondary": [
        {"full_name": "Wilfred Njue", "team": "The Real Deal"},
        {"full_name": "Koech Amos", "team": "KUPPET Savior"},
        {"full_name": "Rotich Wesley", "team": "Unity Alliance"},
    ],
    "Organising Secretary": [
        {"full_name": "Munene oo Kagaani", "team": "The Real Deal"},
        {"full_name": "Omondi Felix", "team": "KUPPET Savior"},
        {"full_name": "Mwita Charles", "team": "Unity Alliance"},
    ],
    "Secretary Jss": [
        {"full_name": "Sultan Ken", "team": "The Real Deal"},
        {"full_name": "Ochieng Brian", "team": "KUPPET Savior"},
        {"full_name": "Musyoka Patrick", "team": "Unity Alliance"},
    ],
    "Youth Rep": [
        {"full_name": "KEN (sir ken)", "team": "The Real Deal"},
        {"full_name": "Maina Kevin", "team": "KUPPET Savior"},
        {"full_name": "Mwangangi Mutua", "team": "Unity Alliance"},
    ],
    "1st Assistant Gender": [
        {"full_name": "Dennitah", "team": "The Real Deal"},
        {"full_name": "Akinyi Millicent", "team": "KUPPET Savior"},
        {"full_name": "Nthenya Rose", "team": "Unity Alliance"},
    ],
    "2nd Assistant sec Gender PWD": [
        {"full_name": "Timwi Njagi", "team": "The Real Deal"},
        {"full_name": "Mwololo Daniel", "team": "KUPPET Savior"},
        {"full_name": "Kioko Benjamin", "team": "Unity Alliance"},
    ],
}

class ProductionDataSeeder:
    """Seed production database with initial data"""
    
    def __init__(self):
        self.super_admin = None
        self.admin = None
        self.voter = None
        self.election = None
        self.teams = {}
        self.positions = {}
        self.candidates = {}
        
    @transaction.atomic
    def seed(self):
        """Run all seeding operations"""
        print("🌱 Starting production data seeding...")
        
        self.create_settings()
        self.create_super_admin()
        self.create_admin()
        self.create_voter()
        self.create_tharaka_nithi_voters()
        self.create_teams()
        self.create_election()
        self.create_positions()
        self.create_candidates()
        self.simulate_voting()
        self.publish_results()
        
        print("✅ Production data seeding complete!")
        self.print_credentials()
        
    def create_settings(self):
        """Create election settings"""
        print("📝 Creating election settings...")
        settings, created = ElectionSettings.objects.get_or_create(
            pk=1,
            defaults={
                'election_name': 'KUPPET Elections 2026',
                'status': 'COMPLETED',
                'allow_voting': False,
                'results_published': True
            }
        )
        if not created:
            settings.election_name = 'KUPPET Elections 2026'
            settings.status = 'COMPLETED'
            settings.allow_voting = False
            settings.results_published = True
            settings.save()
    
    def create_super_admin(self):
        """Create super admin account"""
        print("👑 Creating super admin...")
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
                'phone_verified': True,
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
        print("👤 Creating admin...")
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
                'phone_verified': True,
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
        print("👤 Creating sample voter...")
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
                'phone_verified': True,
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
        print(f"👥 Creating {len(THARAKA_NITHI_VOTERS)} Tharaka Nithi voters...")
        
        created_count = 0
        for voter_data in THARAKA_NITHI_VOTERS:
            email = f"{voter_data['tsc_number'].lower()}@agora.ke"
            _, created = User.objects.get_or_create(
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
                    'phone_verified': True,
                    'county': 'Tharaka Nithi',
                    'password': make_password('Voter@2026')
                }
            )
            if created:
                created_count += 1
        
        print(f"  ✅ Created {created_count} new Tharaka Nithi voters")
    
    def create_teams(self):
        """Create participating teams"""
        print("🏢 Creating teams...")
        
        for team_data in TEAMS:
            team, created = Team.objects.get_or_create(
                name=team_data['name'],
                defaults={
                    'acronym': team_data['acronym'],
                    'color_code': team_data['color_code'],
                    'description': f"{team_data['name']} - Official team for KUPPET Elections 2026",
                    'is_active': True,
                    'status': 'APPROVED'
                }
            )
            self.teams[team_data['name']] = team
            if created:
                print(f"  ✅ Team created: {team.name}")
    
    def create_election(self):
        """Create the main election"""
        print("🗳️ Creating election...")
        
        # Set election date to yesterday (so it's completed)
        election_date = timezone.now().date() - timedelta(days=1)
        
        self.election, created = Election.objects.get_or_create(
            name='KUPPET Elections 2026',
            defaults={
                'election_type': 'NATIONAL',
                'description': 'KUPPET National Elections for Executive Positions',
                'voting_date': election_date,
                'voting_start_time': '08:00:00',
                'voting_end_time': '17:00:00',
                'status': 'COMPLETED',
                'allow_voting': False,
                'results_published': True,
                'total_voters_eligible': len(THARAKA_NITHI_VOTERS) + 1,  # +1 for sample voter
                'auto_open': True,
                'auto_close': True,
                'auto_publish': True
            }
        )
        
        if created:
            print(f"  ✅ Election created: {self.election.name}")
        else:
            # Update existing election
            self.election.status = 'COMPLETED'
            self.election.results_published = True
            self.election.allow_voting = False
            self.election.save()
            print(f"  ℹ️ Election updated to COMPLETED")
    
    def create_positions(self):
        """Create all positions"""
        print("📋 Creating positions...")
        
        for pos_data in POSITIONS:
            position, created = Position.objects.get_or_create(
                election=self.election,
                name=pos_data['name'],
                defaults={
                    'order': pos_data['order'],
                    'max_votes': pos_data['max_votes'],
                    'description': f"Position for {pos_data['name']}",
                    'is_active': True
                }
            )
            self.positions[pos_data['name']] = position
            if created:
                print(f"  ✅ Position created: {position.name}")
    
    def create_candidates(self):
        """Create candidates for each position"""
        print("👥 Creating candidates...")
        
        total_candidates = 0
        for position_name, candidates_list in CANDIDATES.items():
            position = self.positions.get(position_name)
            if not position:
                print(f"  ⚠️ Position '{position_name}' not found, skipping...")
                continue
            
            for candidate_data in candidates_list:
                team = self.teams.get(candidate_data['team'])
                candidate, created = Candidate.objects.get_or_create(
                    election=self.election,
                    position=position,
                    full_name=candidate_data['full_name'],
                    defaults={
                        'team': team,
                        'bio': f"{candidate_data['full_name']} is contesting for {position_name}",
                        'manifesto': f"Manifesto for {candidate_data['full_name']}",
                        'is_active': True,
                        'order': candidates_list.index(candidate_data) + 1
                    }
                )
                if created:
                    total_candidates += 1
                    
                # Store for voting simulation
                key = f"{position_name}_{candidate_data['full_name']}"
                self.candidates[key] = candidate
        
        print(f"  ✅ Created {total_candidates} candidates")
    
    def simulate_voting(self):
        """Simulate voting by all voters"""
        print("🗳️ Simulating voting process...")
        
        # Get all voters (Tharaka Nithi voters + sample voter)
        voters = list(User.objects.filter(
            user_type='VOTER',
            county='Tharaka Nithi',
            kyc_status='VERIFIED'
        )) + [self.voter]
        
        print(f"  Simulating votes for {len(voters)} voters...")
        
        votes_created = 0
        for voter in voters:
            # Create a vote for this voter
            vote = Vote.objects.create(
                election=self.election,
                voter=voter,
                ip_address='127.0.0.1',
                device_fingerprint=f"simulated_{voter.id}",
                vote_token=f"simulated_{voter.id}_{timezone.now().timestamp()}"
            )
            
            # For each position, randomly select a candidate with bias towards The Real Deal
            for position_name, candidates_list in CANDIDATES.items():
                position = self.positions.get(position_name)
                
                # Get candidates for this position
                position_candidates = []
                for cand_data in candidates_list:
                    key = f"{position_name}_{cand_data['full_name']}"
                    candidate = self.candidates.get(key)
                    if candidate:
                        position_candidates.append(candidate)
                
                if position_candidates:
                    # Weighted random: The Real Deal gets 60% chance, others 20% each
                    weights = []
                    for cand in position_candidates:
                        if cand.team and cand.team.name == "The Real Deal":
                            weights.append(0.6)
                        else:
                            weights.append(0.2)
                    
                    # Normalize weights
                    total = sum(weights)
                    weights = [w/total for w in weights]
                    
                    # Select candidate
                    selected = random.choices(position_candidates, weights=weights)[0]
                    
                    # Add to vote
                    vote.candidates.add(selected)
                    
                    # Increment candidate vote count
                    selected.vote_count += 1
                    selected.save()
            
            # Update voter status
            voter.has_voted = True
            voter.voted_at = timezone.now()
            voter.save()
            
            # Create audit log
            VoteAuditLog.objects.create(
                election=self.election,
                vote=vote,
                action='VOTE_CAST',
                ip_address='127.0.0.1',
                user_agent='Simulation Script',
                metadata={'simulated': True}
            )
            
            votes_created += 1
            if votes_created % 10 == 0:
                print(f"    ...{votes_created} votes processed")
        
        # Update election stats
        self.election.total_votes_cast = votes_created
        self.election.save()
        
        print(f"  ✅ Simulated {votes_created} votes")
    
    def publish_results(self):
        """Ensure results are published"""
        print("📊 Publishing results...")
        
        self.election.results_published = True
        self.election.save()
        
        print("  ✅ Results published")
    
    def print_credentials(self):
        """Print login credentials"""
        print("\n" + "="*60)
        print("🔐 LOGIN CREDENTIALS")
        print("="*60)
        print("\n👑 SUPER ADMIN:")
        print(f"  Email: {SUPER_ADMIN_EMAIL}")
        print(f"  Password: {SUPER_ADMIN_PASSWORD}")
        print(f"  TSC: {SUPER_ADMIN_TSC}")
        
        print("\n👤 ADMIN:")
        print(f"  Email: {ADMIN_EMAIL}")
        print(f"  Password: {ADMIN_PASSWORD}")
        print(f"  TSC: {ADMIN_TSC}")
        
        print("\n👤 SAMPLE VOTER:")
        print(f"  Email: {VOTER_EMAIL}")
        print(f"  Password: {VOTER_PASSWORD}")
        print(f"  TSC: {VOTER_TSC}")
        
        print("\n👥 THARAKA NITHI VOTERS:")
        print(f"  Password for all: Voter@2026")
        print(f"  Sample voter: {THARAKA_NITHI_VOTERS[0]['tsc_number']}@agora.ke")
        
        print("\n📊 ELECTION SUMMARY:")
        print(f"  Election: KUPPET Elections 2026")
        print(f"  Status: COMPLETED")
        print(f"  Positions: {len(POSITIONS)}")
        print(f"  Teams: {len(TEAMS)}")
        print(f"  Total Voters: {User.objects.filter(user_type='VOTER', county='Tharaka Nithi').count() + 1}")
        print(f"  Votes Cast: {self.election.total_votes_cast}")
        print("="*60)


if __name__ == "__main__":
    seeder = ProductionDataSeeder()
    seeder.seed()