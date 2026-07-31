/**
 * Mobile header hide-on-scroll + accurate --floward-header-h sync.
 * Queries .site-header live so HTMX shell swaps need no re-bind.
 */
(function () {
  'use strict';

  var MQ = window.matchMedia('(max-width: 991.98px)');
  var REDUCE = window.matchMedia('(prefers-reduced-motion: reduce)');
  var TOP_REVEAL_PX = 12;
  var DELTA_MIN = 6;

  var lastY = 0;
  var ticking = false;
  var resizeObserver = null;

  function headerEl() {
    return document.querySelector('.site-header');
  }

  function trustEl(header) {
    return header ? header.querySelector('.trust-bar') : null;
  }

  function mobileSearchOpen() {
    if (document.body.classList.contains('mobile-search-open')) return true;
    var overlay = document.getElementById('mobile-search-overlay');
    return !!(overlay && overlay.classList.contains('is-open'));
  }

  function categoryNavOpen() {
    var nav = document.getElementById('mainNav');
    return !!(nav && nav.classList.contains('show'));
  }

  function shouldSuppressHide(header) {
    if (!MQ.matches) return true;
    if (mobileSearchOpen() || categoryNavOpen()) return true;
    if (header && header.contains(document.activeElement)) return true;
    return false;
  }

  function setHidden(header, hidden) {
    if (!header) return;
    if (hidden) {
      header.classList.add('is-hidden');
      header.setAttribute('data-header-hidden', 'true');
    } else {
      header.classList.remove('is-hidden');
      header.removeAttribute('data-header-hidden');
    }
  }

  function syncHeaderHeight() {
    var header = headerEl();
    if (!header) return;
    var trust = trustEl(header);
    var trustH = 0;
    if (trust && window.getComputedStyle(trust).display !== 'none') {
      trustH = Math.round(trust.getBoundingClientRect().height);
    }
    /* offsetHeight ignores transform, so hide-on-scroll does not skew sticky offsets */
    var total = header.offsetHeight || Math.round(header.getBoundingClientRect().height);
    document.documentElement.style.setProperty('--floward-trust-h', trustH + 'px');
    document.documentElement.style.setProperty('--floward-header-h', Math.max(total, 1) + 'px');
  }

  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () {
      ticking = false;
      var header = headerEl();
      if (!header) return;

      if (!MQ.matches) {
        setHidden(header, false);
        return;
      }

      var y = window.scrollY || window.pageYOffset || 0;
      if (shouldSuppressHide(header) || y <= TOP_REVEAL_PX) {
        setHidden(header, false);
        lastY = y;
        return;
      }

      var delta = y - lastY;
      if (Math.abs(delta) < DELTA_MIN) return;

      if (delta > 0) {
        setHidden(header, true);
      } else {
        setHidden(header, false);
      }
      lastY = y;
    });
  }

  function onFocusIn() {
    var header = headerEl();
    if (header && header.contains(document.activeElement)) {
      setHidden(header, false);
    }
  }

  function bindResizeObserver() {
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    var header = headerEl();
    if (!header || typeof ResizeObserver === 'undefined') return;
    resizeObserver = new ResizeObserver(function () {
      syncHeaderHeight();
    });
    resizeObserver.observe(header);
  }

  function onShellSwap() {
    lastY = window.scrollY || 0;
    setHidden(headerEl(), false);
    bindResizeObserver();
    syncHeaderHeight();
  }

  function init() {
    lastY = window.scrollY || 0;
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', syncHeaderHeight, { passive: true });
    document.addEventListener('focusin', onFocusIn);
    MQ.addEventListener('change', function () {
      setHidden(headerEl(), false);
      syncHeaderHeight();
    });
    REDUCE.addEventListener('change', function () {
      /* Transition gated in CSS; keep behavior identical */
      setHidden(headerEl(), false);
    });

    document.body.addEventListener('show.bs.offcanvas', function (event) {
      if (event.target && event.target.id === 'mainNav') {
        setHidden(headerEl(), false);
      }
    });
    document.body.addEventListener('hidden.bs.offcanvas', function (event) {
      if (event.target && event.target.id === 'mainNav') {
        lastY = window.scrollY || 0;
      }
    });

    document.addEventListener('floward:mobile-search-open', function () {
      setHidden(headerEl(), false);
    });
    document.addEventListener('floward:mobile-search-close', function () {
      lastY = window.scrollY || 0;
    });

    document.body.addEventListener('htmx:afterSwap', function (event) {
      var target = event.target || (event.detail && event.detail.target);
      if (target && target.id === 'floward-app-shell') {
        onShellSwap();
      }
    });

    bindResizeObserver();
    syncHeaderHeight();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
