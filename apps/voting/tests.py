
# apps/voting/tests.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Position, Team, Candidate, Vote, ElectionSettings
import json

User = get_user_model()

class VotingTestCase(TestCase):
    """Test cases for voting functionality"""
    
    def setUp(self):
        self.client = Client()
        
        # Create election settings
        self.election = ElectionSettings.objects.create(
            election_name='Test Election',
            voting_date=timezone.now().date(),
            voting_start_time=(timezone.now() - timezone.timedelta(hours=1)).time(),
            voting_end_time=(timezone.now() + timezone.timedelta(hours=7)).time(),
            allow_voting=True,
            status='ACTIVE'
        )
        
        # Create positions
        self.positions = []
        for i in range(1, 4):  # Create 3 positions
            pos = Position.objects.create(
                order=i,
                name=f'Position {i}'
            )
            self.positions.append(pos)
        
        # Create teams
        self.team1 = Team.objects.create(name='Team A', color_code='#FF0000')
        self.team2 = Team.objects.create(name='Team B', color_code='#00FF00')
        
        # Create candidates
        self.candidates = []
        for pos in self.positions:
            for team in [self.team1, self.team2]:
                cand = Candidate.objects.create(
                    position=pos,
                    team=team,
                    full_name=f'{team.name} Candidate for {pos.name}',
                    is_active=True
                )
                self.candidates.append(cand)
        
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
        
        self.client.login(tsc_number='voter123', password='voterpass123')
    
    def test_position_creation(self):
        """Test position model"""
        position = Position.objects.create(order=5, name='New Position')
        self.assertEqual(str(position), 'New Position')
        self.assertEqual(position.max_votes, 1)
    
    def test_team_creation(self):
        """Test team model"""
        team = Team.objects.create(name='New Team', color_code='#0000FF')
        self.assertEqual(str(team), 'New Team')
    
    def test_candidate_vote_count_increment(self):
        """Test vote count increment"""
        candidate = self.candidates[0]
        initial_votes = candidate.vote_count
        candidate.increment_vote()
        candidate.refresh_from_db()
        self.assertEqual(candidate.vote_count, initial_votes + 1)
    
    def test_vote_creation(self):
        """Test vote creation"""
        # Select candidates (one per position)
        vote_data = {}
        for i, pos in enumerate(self.positions):
            candidate = Candidate.objects.filter(position=pos).first()
            vote_data[str(pos.order)] = str(candidate.id)
        
        response = self.client.post(
            reverse('core:voting_area'),
            data=json.dumps({'votes': vote_data}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check vote was recorded
        self.voter.refresh_from_db()
        self.assertTrue(self.voter.has_voted)
        
        # Check vote count increased
        vote = Vote.objects.get(voter=self.voter)
        self.assertEqual(vote.candidates.count(), len(self.positions))
    
    def test_prevent_multiple_votes(self):
        """Test user cannot vote twice"""
        # First vote
        vote_data = {}
        for i, pos in enumerate(self.positions):
            candidate = Candidate.objects.filter(position=pos).first()
            vote_data[str(pos.order)] = str(candidate.id)
        
        self.client.post(
            reverse('core:voting_area'),
            data=json.dumps({'votes': vote_data}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Second vote attempt
        response = self.client.post(
            reverse('core:voting_area'),
            data=json.dumps({'votes': vote_data}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 403)
    
    def test_election_settings_singleton(self):
        """Test only one election settings instance"""
        with self.assertRaises(ValueError):
            ElectionSettings.objects.create(
                election_name='Another Election',
                voting_date=timezone.now().date()
            )
    
    def test_voting_open_check(self):
        """Test voting open check"""
        settings = ElectionSettings.get_settings()
        self.assertTrue(settings.is_voting_open())
        
        # Close voting
        settings.allow_voting = False
        settings.save()
        self.assertFalse(settings.is_voting_open())