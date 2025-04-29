// FotoShr Main JavaScript - Modern Version

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length) {
        Array.from(tooltipTriggerList).map(tooltipTriggerEl => {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Initialize Bootstrap popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    if (popoverTriggerList.length) {
        Array.from(popoverTriggerList).map(popoverTriggerEl => {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
    
    // Dark mode toggle
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = themeToggleBtn?.querySelector('i');
    const navbar = document.getElementById('main-nav');
    
    // Check for saved theme preference or respect OS preference
    const savedTheme = localStorage.getItem('theme');
    
    function setDarkMode() {
        document.body.classList.add('dark-mode');
        document.body.classList.remove('light-mode');
        if (themeIcon) {
            themeIcon.classList.remove('bi-sun');
            themeIcon.classList.add('bi-moon-stars');
        }
        
        // Update navbar classes for dark mode
        if (navbar) {
            navbar.classList.remove('navbar-light');
            navbar.classList.add('navbar-dark');
        }
    }
    
    function setLightMode() {
        document.body.classList.remove('dark-mode');
        document.body.classList.add('light-mode');
        if (themeIcon) {
            themeIcon.classList.remove('bi-moon-stars');
            themeIcon.classList.add('bi-sun');
        }
        
        // Update navbar classes for light mode
        if (navbar) {
            navbar.classList.remove('navbar-dark');
            navbar.classList.add('navbar-light');
        }
    }
    
    if (savedTheme === 'light') {
        setLightMode();
    } else if (savedTheme === 'dark') {
        setDarkMode();
    } else {
        // If no saved preference, check OS preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            setDarkMode();
        } else {
            setLightMode();
        }
    }
    
    // Toggle theme
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            if (document.body.classList.contains('light-mode')) {
                setDarkMode();
                localStorage.setItem('theme', 'dark');
            } else {
                setLightMode();
                localStorage.setItem('theme', 'light');
            }
        });
    }
    
    // Auto dismiss flash messages after 5 seconds
    const flashMessages = document.querySelector('.alert:not(.alert-permanent)');
    if (flashMessages) {
        setTimeout(() => {
            const closeBtn = flashMessages.querySelector('.btn-close');
            if (closeBtn) {
                closeBtn.click();
            } else {
                flashMessages.classList.add('fade');
                setTimeout(() => {
                    flashMessages.remove();
                }, 500);
            }
        }, 5000);
    }
    
    // Lazy loading for images
    if ('loading' in HTMLImageElement.prototype) {
        // Browser supports native lazy loading
        const images = document.querySelectorAll('img:not([loading])');
        images.forEach(img => {
            img.setAttribute('loading', 'lazy');
        });
    } else {
        // Fallback for browsers that don't support native lazy loading
        const lazyImages = document.querySelectorAll('img[data-src]');
        if ('IntersectionObserver' in window && lazyImages.length > 0) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const image = entry.target;
                        image.src = image.dataset.src;
                        if (image.dataset.srcset) {
                            image.srcset = image.dataset.srcset;
                        }
                        imageObserver.unobserve(image);
                    }
                });
            });
            
            lazyImages.forEach(img => {
                imageObserver.observe(img);
            });
        } else {
            // Fallback for browsers that don't support Intersection Observer
            lazyImages.forEach(img => {
                img.src = img.dataset.src;
                if (img.dataset.srcset) {
                    img.srcset = img.dataset.srcset;
                }
            });
        }
    }
    
    // Tag filtering functionality
    const tagLinks = document.querySelectorAll('.badge');
    tagLinks.forEach(tag => {
        tag.addEventListener('click', function(e) {
            if (this.getAttribute('href') === '#') {
                e.preventDefault();
                const tagText = this.textContent.trim();
                window.location.href = `/search?query=${encodeURIComponent(tagText)}`;
            }
        });
    });
    
    // Animate elements when they come into view
    const animatedElements = document.querySelectorAll('.animate-on-scroll');
    if ('IntersectionObserver' in window && animatedElements.length > 0) {
        const animationObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                    animationObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        animatedElements.forEach(el => {
            animationObserver.observe(el);
        });
    } else {
        // Fallback for browsers that don't support Intersection Observer
        animatedElements.forEach(el => {
            el.classList.add('animated');
        });
    }
    
    // Initialize masonry layout if available
    const masonryGrid = document.querySelector('.masonry-grid');
    if (masonryGrid && typeof Masonry !== 'undefined' && typeof imagesLoaded !== 'undefined') {
        imagesLoaded(masonryGrid, function() {
            new Masonry(masonryGrid, {
                itemSelector: '.masonry-item',
                columnWidth: '.masonry-sizer',
                percentPosition: true
            });
        });
    }
}); 