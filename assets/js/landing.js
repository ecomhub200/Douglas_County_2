    // Helper: run callback on DOMContentLoaded, or immediately if already loaded
    // Needed because this file is loaded with defer (DOM may already be ready)
    function onReady(fn) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fn);
      } else {
        fn();
      }
    }

    // toggleMobileMenu is defined inline in index.html for instant availability

    // Close mobile menu when clicking outside
    document.addEventListener('click', function(e) {
      const menu = document.getElementById('mobileMenu');
      const btn = document.querySelector('.mobile-menu-btn');
      if (menu && btn && !menu.contains(e.target) && !btn.contains(e.target)) {
        menu.classList.remove('show');
      }
    });

    // ROI Calculator
    function calculateROI() {
      const studies = parseInt(document.getElementById('studiesPerYear').value) || 12;
      const hoursPerStudy = parseInt(document.getElementById('hoursPerStudy').value) || 40;
      const hourlyRate = parseInt(document.getElementById('hourlyRate').value) || 75;
      const hsipApps = parseInt(document.getElementById('hsipApps').value) || 3;

      // CRASH LENS reduces analysis time by ~70%
      const timeReduction = 0.70;
      const currentHours = studies * hoursPerStudy;
      const hoursSaved = Math.round(currentHours * timeReduction);
      const costSavings = hoursSaved * hourlyRate;

      // Annual cost of CRASH LENS (Individual plan)
      const annualCost = 150 * 12;
      const roi = Math.round(((costSavings - annualCost) / annualCost) * 100);

      document.getElementById('hoursSaved').textContent = hoursSaved.toLocaleString() + ' hours';
      document.getElementById('costSavings').textContent = '$' + costSavings.toLocaleString();
      document.getElementById('roiPercent').textContent = (roi > 0 ? roi.toLocaleString() : '0') + '%';
    }

    // Initialize ROI calculator on page load
    onReady(calculateROI);

    // Video Demo Player
    function playDemoVideo() {
      const container = document.getElementById('demoVideoContainer');
      const video = document.getElementById('demoVideo');

      // Check if video source exists
      if (video && video.querySelector('source').src) {
        container.classList.add('playing');
        video.play().catch(function(error) {
          // If video fails to play (e.g., file not found), show message
          console.log('Video not available yet. Add your demo video to: data/videos/crash-lens-demo.mp4');
          alert('Demo video coming soon! Contact us for a live demo.');
        });
      } else {
        alert('Demo video coming soon! Contact us for a live demo.');
      }
    }

    // ============================================================
    // CRASH VISUALIZATION - Scenario Selection
    // ============================================================

    // Current scenario state
    let currentScenario = 0;

    // Send message to visualization iframe
    function sendVizMessage(type, data) {
      const iframe = document.getElementById('crashVizIframe');
      if (iframe && iframe.contentWindow) {
        iframe.contentWindow.postMessage({ type, data }, '*');
      }
    }

    // Set crash scenario (from crash type cards)
    function setScenario(index) {
      currentScenario = index;

      // Update crash type card states
      document.querySelectorAll('.crash-type-item').forEach((item, i) => {
        item.classList.toggle('active', i === index);
      });

      // Send message to iframe
      sendVizMessage('setScenario', index);
    }

    // Make crash type cards clickable
    onReady(function() {
      document.querySelectorAll('.crash-type-item').forEach((item, index) => {
        item.addEventListener('click', () => setScenario(index));
      });

      // Lazy-load crash-scenarios iframe when it scrolls near the viewport
      var crashIframe = document.getElementById('crashVizIframe');
      if (crashIframe && crashIframe.dataset.src) {
        var iframeObserver = new IntersectionObserver(function(entries) {
          entries.forEach(function(entry) {
            if (entry.isIntersecting) {
              crashIframe.src = crashIframe.dataset.src;
              iframeObserver.disconnect();
            }
          });
        }, { rootMargin: '300px' });
        iframeObserver.observe(crashIframe);
      }
    });

    // Listen for messages from iframe (scenario changes)
    window.addEventListener('message', function(event) {
      if (event.data && event.data.type === 'scenarioChanged') {
        const index = event.data.scenario;
        currentScenario = index;

        // Update crash type card states
        document.querySelectorAll('.crash-type-item').forEach((item, i) => {
          item.classList.toggle('active', i === index);
        });
      }
    });

    // ============================================================
    // LANDING PAGE ANIMATION SYSTEM
    // ============================================================

    // Intersection Observer for scroll-triggered animations
    function initScrollAnimations() {
      // Check for reduced motion preference
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        // Show all elements without animation
        document.querySelectorAll('.animate-on-scroll, .stagger-children').forEach(el => {
          el.classList.add('animate-visible');
        });
        return;
      }

      const observerOptions = {
        root: null,
        rootMargin: '0px 0px -50px 0px',
        threshold: 0.1
      };

      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-visible');

            // Handle .reveal and .stagger classes
            if (entry.target.classList.contains('reveal') || entry.target.classList.contains('stagger')) {
              entry.target.classList.add('visible');
            }

            // Trigger count-up for stats
            if (entry.target.classList.contains('stats-grid')) {
              animateCountUp(entry.target);
            }

            // Unobserve after animation
            observer.unobserve(entry.target);
          }
        });
      }, observerOptions);

      // Observe elements
      const animatedElements = document.querySelectorAll(
        '.animate-on-scroll, .stagger-children, .reveal, .stagger, ' +
        '.features-header, .case-studies-header, ' +
        '.how-it-works-header, .demo-video-header, .roi-calculator-header, ' +
        '.features-grid, .case-studies-grid, .steps-container, ' +
        '.stats-grid'
      );

      animatedElements.forEach(el => observer.observe(el));
    }

    // Count-Up Animation for Statistics
    function animateCountUp(container) {
      const statValues = container.querySelectorAll('.stat-value');

      statValues.forEach(el => {
        const text = el.textContent.trim();
        const hasPlus = text.includes('+');
        const hasPercent = text.includes('%');
        const hasDollar = text.includes('$');
        const hasK = text.includes('K');
        const hasM = text.includes('M');

        // Extract numeric value
        let numericValue = parseFloat(text.replace(/[^0-9.]/g, ''));
        if (isNaN(numericValue)) return;

        // Adjust for K/M suffixes
        let suffix = '';
        if (hasK) suffix = 'K';
        if (hasM) suffix = 'M';

        const prefix = hasDollar ? '$' : '';
        const postfix = (hasPlus ? '+' : '') + (hasPercent ? '%' : '');

        // Animate
        el.classList.add('counting');
        const duration = 1500;
        const startTime = performance.now();
        const startValue = 0;

        function updateValue(currentTime) {
          const elapsed = currentTime - startTime;
          const progress = Math.min(elapsed / duration, 1);

          // Easing function (ease-out-expo)
          const easeOutExpo = 1 - Math.pow(2, -10 * progress);
          const currentValue = startValue + (numericValue - startValue) * easeOutExpo;

          // Format the value
          let displayValue;
          if (numericValue >= 100) {
            displayValue = Math.round(currentValue);
          } else if (numericValue >= 10) {
            displayValue = Math.round(currentValue);
          } else {
            displayValue = currentValue.toFixed(1);
          }

          el.textContent = prefix + displayValue.toLocaleString() + suffix + postfix;

          if (progress < 1) {
            requestAnimationFrame(updateValue);
          } else {
            el.classList.remove('counting');
          }
        }

        requestAnimationFrame(updateValue);
      });
    }

    // Navigation scroll effect (throttled via rAF)
    function initNavScrollEffect() {
      const nav = document.querySelector('.nav');
      if (!nav) return;

      let navTicking = false;
      window.addEventListener('scroll', () => {
        if (!navTicking) {
          navTicking = true;
          requestAnimationFrame(() => {
            if (window.pageYOffset > 50) {
              nav.classList.add('scrolled');
            } else {
              nav.classList.remove('scrolled');
            }
            navTicking = false;
          });
        }
      }, { passive: true });
    }

    // Smooth scroll for anchor links
    function initSmoothScroll() {
      document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
          const targetId = this.getAttribute('href');
          if (targetId === '#') return;

          const targetElement = document.querySelector(targetId);
          if (targetElement) {
            e.preventDefault();
            targetElement.scrollIntoView({
              behavior: 'smooth',
              block: 'start'
            });
          }
        });
      });
    }

    // Add stagger-children class to grids
    function initStaggeredGrids() {
      const grids = document.querySelectorAll(
        '.features-grid, .case-studies-grid, .steps-container, .trusted-logos'
      );
      grids.forEach(grid => {
        grid.classList.add('stagger-children');
      });
    }

    // Scroll Progress Bar (throttled via rAF)
    function initScrollProgress() {
      const scrollProgress = document.getElementById('scrollProgress');
      if (!scrollProgress) return;

      let progressTicking = false;
      window.addEventListener('scroll', () => {
        if (!progressTicking) {
          progressTicking = true;
          requestAnimationFrame(() => {
            const scrollTop = document.documentElement.scrollTop;
            const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            scrollProgress.style.width = (scrollTop / scrollHeight) * 100 + '%';
            progressTicking = false;
          });
        }
      }, { passive: true });
    }

    // Initialize all animations on DOM ready
    onReady(function() {
      initStaggeredGrids();
      initScrollAnimations();
      initNavScrollEffect();
      initSmoothScroll();
      initScrollProgress();
    });

    // Remove loading overlay on DOMContentLoaded (faster than window.load)
    // Content is visible and interactive — no need to wait for all images/iframes
    onReady(function() {
      var overlay = document.getElementById('pageLoadingOverlay');
      if (overlay) {
        overlay.classList.add('fade-out');
        setTimeout(function() { overlay.remove(); }, 300);
      }
    });

    // Newsletter Subscription (Brevo Contacts API via server proxy)
    async function subscribeNewsletter() {
      const emailInput = document.getElementById('newsletterEmail');
      const btn = document.getElementById('newsletterBtn');
      const msg = document.getElementById('newsletterMsg');
      const email = emailInput.value.trim();

      // Basic email validation
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        msg.style.display = 'block';
        msg.style.color = '#f87171';
        msg.textContent = 'Please enter a valid email address.';
        return;
      }

      // Disable button during request
      btn.disabled = true;
      btn.textContent = 'Subscribing...';
      msg.style.display = 'none';

      try {
        const response = await fetch('/api/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email })
        });

        const data = await response.json();

        if (response.ok || response.status === 409) {
          msg.style.display = 'block';
          msg.style.color = '#34d399';
          msg.textContent = response.status === 409
            ? 'You are already subscribed. Thank you!'
            : 'Thank you for subscribing! You will receive updates on traffic safety insights.';
          emailInput.value = '';
        } else {
          throw new Error(data.message || 'Subscription failed');
        }
      } catch (err) {
        msg.style.display = 'block';
        msg.style.color = '#f87171';
        msg.textContent = 'Unable to subscribe right now. Please email us at support@aicreatesai.com';
        console.error('[Newsletter]', err);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Subscribe';
      }
    }

    // Allow Enter key to submit newsletter
    onReady(function() {
      var newsletterInput = document.getElementById('newsletterEmail');
      if (newsletterInput) {
        newsletterInput.addEventListener('keypress', function(e) {
          if (e.key === 'Enter') { e.preventDefault(); subscribeNewsletter(); }
        });
      }
    });
