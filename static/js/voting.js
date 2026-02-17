/**
 * KUPPET VOTING - BALLOT LOGIC
 * Handles candidate selection and vote submission
 */

(function () {
    'use strict';

    class BallotManager {
        constructor() {
            this.selections = {};
            this.positions = ['president', 'governor', 'senator', 'mp', 'mca'];
            this.init();
        }

        init() {
            this.attachListeners();
            this.updateProgress();
        }

        /**
         * Attach click listeners to candidate cards
         */
        attachListeners() {
            document.querySelectorAll('.candidate-card').forEach(card => {
                card.addEventListener('click', (e) => this.selectCandidate(e.currentTarget));
            });

            const submitBtn = document.getElementById('btn-submit-vote');
            if (submitBtn) {
                submitBtn.addEventListener('click', () => this.confirmVote());
            }
        }

        /**
         * Handle candidate selection
         */
        selectCandidate(card) {
            const position = card.dataset.position;
            const candidateId = card.dataset.id;
            const candidateName = card.querySelector('.candidate-name').textContent;

            // Deselect others in same position
            document.querySelectorAll(`.candidate-card[data-position="${position}"]`).forEach(c => {
                c.classList.remove('selected', 'active');
                c.querySelector('.selection-indicator').classList.add('d-none');
            });

            // Select this one
            card.classList.add('selected', 'active');
            card.querySelector('.selection-indicator').classList.remove('d-none');

            // Store selection
            this.selections[position] = {
                id: candidateId,
                name: candidateName
            };

            this.updateProgress();
            this.validateBallot();
        }

        /**
         * Update progress bar
         */
        updateProgress() {
            const total = this.positions.length;
            const current = Object.keys(this.selections).length;
            const percent = (current / total) * 100;

            const progressBar = document.getElementById('voting-progress');
            if (progressBar) {
                progressBar.style.width = `${percent}%`;
            }

            document.getElementById('selections-count').textContent = `${current}/${total}`;
        }

        /**
         * Check if ballot is complete
         */
        validateBallot() {
            const isComplete = this.positions.every(pos => this.selections[pos]);
            const reviewBtn = document.getElementById('btn-review-vote');

            if (reviewBtn) {
                reviewBtn.disabled = !isComplete;
                if (isComplete) {
                    reviewBtn.classList.add('pulse');
                } else {
                    reviewBtn.classList.remove('pulse');
                }
            }
            return isComplete;
        }

        /**
         * Show confirmation modal
         */
        showConfirmation() {
            if (!this.validateBallot()) return;

            const summaryList = document.getElementById('vote-summary-list');
            summaryList.innerHTML = '';

            this.positions.forEach(pos => {
                const selection = this.selections[pos];
                const item = document.createElement('div');
                item.className = 'd-flex justify-between mb-sm border-bottom pb-xs';
                item.innerHTML = `
                <span class="text-muted capitalize">${pos}</span>
                <span class="font-bold text-neon">${selection.name}</span>
            `;
                summaryList.appendChild(item);
            });

            // Show modal (simple CSS toggle for now)
            document.getElementById('confirmation-modal').classList.remove('d-none');
        }

        /**
         * Submit vote to backend
         */
        async confirmVote() {
            const btn = document.getElementById('btn-submit-vote');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Encrypting & Submitting...';

            // Simulate API call
            setTimeout(() => {
                // Build payload
                const payload = {
                    selections: this.selections,
                    fingerprint: document.getElementById('device-fingerprint')?.value,
                    csrfmiddlewaretoken: Agora.getCsrfToken()
                };

                console.log('Submitting Vote:', payload);

                // In real implementation:
                // Agora.fetch('/api/vote/cast/', { method: 'POST', body: JSON.stringify(payload) })
                // .then(...)

                // Redirect to results/success page
                window.location.href = '/voter/results.html?status=success';
            }, 2000);
        }
    }

    // Expose
    window.ballotManager = new BallotManager();

    // Bind the global function for the Review button
    window.reviewVote = function () {
        window.ballotManager.showConfirmation();
    }

})();