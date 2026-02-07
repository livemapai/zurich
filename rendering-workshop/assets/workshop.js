/**
 * MapLibre Pipeline Workshop - Shared JavaScript
 * Utility functions for code copy, accordions, and micro-interactions
 *
 * This is an exploratory reference guide - no progress tracking.
 */

(function() {
  'use strict';

  // ==========================================================================
  // Code Copy Functionality
  // ==========================================================================

  const CodeCopy = {
    /**
     * Initialize copy buttons for all code blocks
     */
    init() {
      document.querySelectorAll('pre').forEach(pre => {
        // Skip if already has copy button
        if (pre.querySelector('.code-copy-btn')) return;

        // Create copy button
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.textContent = 'Copy';
        btn.addEventListener('click', () => this.copy(pre, btn));

        // Make pre position relative if not already
        if (getComputedStyle(pre).position === 'static') {
          pre.style.position = 'relative';
        }

        pre.appendChild(btn);
      });
    },

    /**
     * Copy code content to clipboard
     */
    async copy(pre, btn) {
      const code = pre.querySelector('code') || pre;
      const text = code.textContent;

      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = '\u2713 Copied';
        btn.classList.add('copied');

        setTimeout(() => {
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        }, 2000);
      } catch (e) {
        console.warn('Failed to copy:', e);
        btn.textContent = 'Failed';
        setTimeout(() => {
          btn.textContent = 'Copy';
        }, 2000);
      }
    }
  };

  // ==========================================================================
  // Accordion Component
  // ==========================================================================

  const Accordion = {
    /**
     * Initialize accordions with smooth animations
     */
    init() {
      document.querySelectorAll('details.accordion-item').forEach(details => {
        const content = details.querySelector('.accordion-content');
        if (!content) return;

        details.addEventListener('toggle', () => {
          if (details.open) {
            content.style.maxHeight = content.scrollHeight + 'px';
          } else {
            content.style.maxHeight = '0';
          }
        });
      });
    }
  };

  // ==========================================================================
  // Smooth Scroll
  // ==========================================================================

  const SmoothScroll = {
    /**
     * Initialize smooth scrolling for anchor links
     */
    init() {
      document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', (e) => {
          const targetId = anchor.getAttribute('href').slice(1);
          const target = document.getElementById(targetId);

          if (target) {
            e.preventDefault();
            target.scrollIntoView({
              behavior: 'smooth',
              block: 'start'
            });
          }
        });
      });
    }
  };

  // ==========================================================================
  // Task Card Enhancements
  // ==========================================================================

  const TaskCards = {
    /**
     * Add keyboard accessibility to task cards
     */
    init() {
      document.querySelectorAll('.task-card').forEach(card => {
        // Add keyboard accessibility
        card.setAttribute('tabindex', '0');
        card.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            card.click();
          }
        });
      });
    }
  };

  // ==========================================================================
  // Navigation Helpers
  // ==========================================================================

  const Navigation = {
    /**
     * Get base path for workshop relative links
     */
    getBasePath() {
      const path = window.location.pathname;

      // Check if we're in a subdirectory
      if (path.includes('/tasks/')) {
        return path.includes('/03-maputnik/') || path.includes('/05-planetiler/')
          ? '../..'
          : '..';
      }
      if (path.includes('/capstone/')) {
        return '..';
      }

      return '.';
    }
  };

  // ==========================================================================
  // Console Welcome
  // ==========================================================================

  const ConsoleWelcome = {
    show() {
      console.log(
        '%c\ud83d\uddfa MapLibre Pipeline Workshop',
        'color: #d97706; font-size: 20px; font-weight: bold;'
      );
      console.log(
        '%cFrom raw vectors to rendered pixels!',
        'color: #a8a29e; font-size: 14px;'
      );
      console.log('');
      console.log('%cExplore the full vector tile pipeline.', 'color: #0ea5e9;');
      console.log('Use the navigation links to move between tasks.');
      console.log('');
    }
  };

  // ==========================================================================
  // Initialize Everything
  // ==========================================================================

  function init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    // Initialize all modules
    CodeCopy.init();
    TaskCards.init();
    Accordion.init();
    SmoothScroll.init();
    ConsoleWelcome.show();
  }

  // ==========================================================================
  // Public API
  // ==========================================================================

  window.Workshop = {
    // Navigation helper
    getBasePath() {
      return Navigation.getBasePath();
    },

    // Re-initialize (useful after dynamic content loads)
    reinit() {
      CodeCopy.init();
      TaskCards.init();
    }
  };

  // Start initialization
  init();
})();
