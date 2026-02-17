// static/js/camera.js
// Camera capture functionality for KYC

class CameraCapture {
    constructor(videoElementId, canvasElementId, captureButtonId) {
        this.video = document.getElementById(videoElementId);
        this.canvas = document.getElementById(canvasElementId);
        this.captureButton = document.getElementById(captureButtonId);
        this.stream = null;
    }
    
    async start() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'user'
                } 
            });
            
            this.video.srcObject = this.stream;
            await this.video.play();
            
            this.captureButton.disabled = false;
            this.captureButton.addEventListener('click', () => this.capture());
            
        } catch (error) {
            console.error('Camera access error:', error);
            this.showError('Could not access camera. Please ensure camera permissions are granted.');
        }
    }
    
    capture() {
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        
        const context = this.canvas.getContext('2d');
        context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Convert to blob
        this.canvas.toBlob((blob) => {
            this.onCapture(blob);
        }, 'image/jpeg', 0.9);
        
        this.stop();
    }
    
    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.video.srcObject = null;
        this.captureButton.disabled = true;
    }
    
    onCapture(blob) {
        // Override this method to handle the captured image
        console.log('Captured image:', blob);
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-error';
        errorDiv.textContent = message;
        this.video.parentNode.insertBefore(errorDiv, this.video);
    }
}