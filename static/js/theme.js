// Theme switcher with immediate execution
(function() {
    // Store original class for debugging
    const originalClass = document.documentElement.className;
    console.log('Initial HTML class:', originalClass);
    
    function getCurrentTheme() {
        const storedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (storedTheme === 'dark') return 'dark';
        if (storedTheme === 'light') return 'light';
        return systemPrefersDark ? 'dark' : 'light';
    }
    
    function setTheme(theme) {
        console.log('Setting theme to:', theme);
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
            document.documentElement.classList.remove('light');
        } else {
            document.documentElement.classList.remove('dark');
            document.documentElement.classList.add('light');
        }
        
        // Force repaint of all elements
        document.body.style.display = 'none';
        document.body.offsetHeight; // Trigger reflow
        document.body.style.display = '';
        
        // Update icons
        updateThemeIcons(theme === 'dark');
        
        // Save preference
        localStorage.setItem('theme', theme);
        
        // Dispatch event
        document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    }
    
    function updateThemeIcons(isDark) {
        document.querySelectorAll('.fa-moon, .fa-sun').forEach(icon => {
            if (icon.classList.contains('fa-moon')) {
                icon.style.display = isDark ? 'none' : 'inline-block';
            }
            if (icon.classList.contains('fa-sun')) {
                icon.style.display = isDark ? 'inline-block' : 'none';
            }
        });
    }
    
    function toggleTheme() {
        const isDark = document.documentElement.classList.contains('dark');
        setTheme(isDark ? 'light' : 'dark');
    }
    
    // Initialize theme on load
    function initializeTheme() {
        const theme = getCurrentTheme();
        console.log('Initializing theme:', theme);
        setTheme(theme);
    }
    
    // Run initialization immediately
    initializeTheme();
    
    // Set up event listeners when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupButtons);
    } else {
        setupButtons();
    }
    
    function setupButtons() {
        console.log('Setting up theme buttons');
        
        // Desktop theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            console.log('Found desktop theme toggle');
            themeToggle.addEventListener('click', function(e) {
                e.preventDefault();
                toggleTheme();
            });
        } else {
            console.warn('Desktop theme toggle not found');
        }
        
        // Mobile theme toggle
        const mobileThemeToggle = document.getElementById('mobile-theme-toggle');
        if (mobileThemeToggle) {
            console.log('Found mobile theme toggle');
            mobileThemeToggle.addEventListener('click', function(e) {
                e.preventDefault();
                toggleTheme();
            });
        } else {
            console.warn('Mobile theme toggle not found');
        }
        
        // Initial icon update
        updateThemeIcons(document.documentElement.classList.contains('dark'));
    }
    
    // Listen for system preference changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches ? 'dark' : 'light');
        }
    });
    
    // Make toggle function globally available
    window.toggleTheme = toggleTheme;
})();