
// static/js/timer.js - Countdown Timer Functionality

class ElectionTimer {
    constructor(votingDate, startTime, endTime) {
        this.votingDate = new Date(votingDate);
        this.startTime = startTime;
        this.endTime = endTime;
        this.interval = null;
    }
    
    start() {
        this.update();
        this.interval = setInterval(() => this.update(), 1000);
    }
    
    stop() {
        if (this.interval) {
            clearInterval(this.interval);
        }
    }
    
    update() {
        const now = new Date();
        const electionStart = this.getElectionStart();
        const electionEnd = this.getElectionEnd();
        
        const timeToStart = electionStart - now;
        const timeToEnd = electionEnd - now;
        
        const timerElement = document.getElementById('votingTimer');
        const statusElement = document.getElementById('votingStatus');
        
        if (!timerElement || !statusElement) return;
        
        if (timeToStart > 0) {
            // Before election
            const days = Math.floor(timeToStart / (1000 * 60 * 60 * 24));
            const hours = Math.floor((timeToStart % (86400000)) / (3600000));
            const minutes = Math.floor((timeToStart % 3600000) / 60000);
            const seconds = Math.floor((timeToStart % 60000) / 1000);
            
            timerElement.innerHTML = `${days}d ${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;
            statusElement.innerHTML = 'Time until voting opens';
            statusElement.className = 'text-info';
            
        } else if (timeToEnd > 0) {
            // During election
            const hours = Math.floor(timeToEnd / 3600000);
            const minutes = Math.floor((timeToEnd % 3600000) / 60000);
            const seconds = Math.floor((timeToEnd % 60000) / 1000);
            
            timerElement.innerHTML = `${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;
            statusElement.innerHTML = 'Time remaining to vote';
            statusElement.className = 'text-success';
            
            // Check if voting is open and enable voting button
            const voteButton = document.getElementById('voteNowBtn');
            if (voteButton) {
                voteButton.disabled = false;
            }
            
        } else {
            // After election
            timerElement.innerHTML = '00:00:00';
            statusElement.innerHTML = 'Voting has ended';
            statusElement.className = 'text-danger';
            
            const voteButton = document.getElementById('voteNowBtn');
            if (voteButton) {
                voteButton.disabled = true;
                voteButton.innerHTML = '<i class="fas fa-ban"></i> Voting Closed';
            }
        }
    }
    
    getElectionStart() {
        const start = new Date(this.votingDate);
        const [hours, minutes] = this.startTime.split(':');
        start.setHours(parseInt(hours), parseInt(minutes), 0);
        return start;
    }
    
    getElectionEnd() {
        const end = new Date(this.votingDate);
        const [hours, minutes] = this.endTime.split(':');
        end.setHours(parseInt(hours), parseInt(minutes), 0);
        return end;
    }
}

// Initialize timer when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const timerElement = document.getElementById('votingTimer');
    if (timerElement) {
        const votingDate = timerElement.dataset.date;
        const startTime = timerElement.dataset.start;
        const endTime = timerElement.dataset.end;
        
        if (votingDate && startTime && endTime) {
            const timer = new ElectionTimer(votingDate, startTime, endTime);
            timer.start();
        }
    }
});