// Page loading effects
(function() {
    // Create loading overlay
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm z-[9999] flex items-center justify-center transition-opacity duration-300';
    loadingOverlay.style.opacity = '0';
    loadingOverlay.style.pointerEvents = 'none';
    
    // Create pulsing circles
    loadingOverlay.innerHTML = `
        <div class="relative">
            <div class="w-16 h-16 border-4 border-gray-300 border-t-white rounded-full animate-spin"></div>
            <div class="absolute inset-0 flex items-center justify-center">
                <div class="w-8 h-8 bg-white rounded-full animate-pulse"></div>
            </div>
        </div>
    `;
    
    document.body.appendChild(loadingOverlay);
    
    // Show loading on page navigation
    let loadingTimeout;
    
    function showLoading() {
        clearTimeout(loadingTimeout);
        loadingOverlay.style.opacity = '1';
        loadingOverlay.style.pointerEvents = 'all';
    }
    
    function hideLoading() {
        loadingTimeout = setTimeout(() => {
            loadingOverlay.style.opacity = '0';
            loadingOverlay.style.pointerEvents = 'none';
        }, 300);
    }
    
    // Intercept all link clicks
    document.addEventListener('click', function(e) {
        const link = e.target.closest('a');
        if (link && 
            link.href && 
            !link.href.includes('#') && 
            !link.target && 
            link.origin === window.location.origin) {
            
            // Don't show loading for downloads or external links
            if (!link.hasAttribute('download')) {
                showLoading();
            }
        }
    });
    
    // Intercept form submissions
    document.addEventListener('submit', function() {
        showLoading();
    });
    
    // Hide loading when page loads
    window.addEventListener('load', hideLoading);
    window.addEventListener('pageshow', hideLoading);
    
    // Add skeleton loading for content
    function addSkeletonEffect() {
        const contentAreas = document.querySelectorAll('.skeleton-load');
        contentAreas.forEach(area => {
            area.classList.add('animate-pulse', 'bg-gray-200', 'dark:bg-gray-700');
        });
    }
})();