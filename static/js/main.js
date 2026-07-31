(function () {
  'use strict';
  if (window.htmx && htmx.config && htmx.config.responseHandling) {
    htmx.config.responseHandling.unshift({ code: '400', swap: true, error: false });
  }

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
  var progressEl = document.getElementById('htmx-progress');
  var pendingGlobalProgress = 0;

  function triggeringElementHasIndicator(elt) {
    if (!elt) {
      return false;
    }
    if (elt.getAttribute && elt.getAttribute('hx-indicator')) {
      return true;
    }
    return !!elt.closest('[hx-indicator]');
  }

  function showGlobalProgress() {
    if (!progressEl) {
      return;
    }
    progressEl.hidden = false;
    progressEl.setAttribute('aria-hidden', 'false');
    progressEl.classList.add('is-active');
  }

  function hideGlobalProgress() {
    if (!progressEl || pendingGlobalProgress > 0) {
      return;
    }
    progressEl.classList.remove('is-active');
    progressEl.hidden = true;
    progressEl.setAttribute('aria-hidden', 'true');
  }

  function uiText(key, fallback) {
    var value = document.body && document.body.getAttribute(key);
    return value || fallback;
  }

  function showToast(message, kind) {
    var root = document.getElementById('htmx-toast-root');
    if (!root) {
      return;
    }
    var toastClass = kind === 'success' ? 'htmx-toast htmx-toast--success' : 'htmx-toast';
    root.hidden = false;
    root.innerHTML =
      '<div class="' + toastClass + '" role="alert">' +
      '<span class="htmx-toast__message"></span>' +
      '<button type="button" class="htmx-toast__close btn-ghost" aria-label="' + uiText('data-i18n-dismiss', 'Dismiss') + '">&times;</button>' +
      '</div>';
    root.querySelector('.htmx-toast__message').textContent = message;
    var closeBtn = root.querySelector('.htmx-toast__close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        root.hidden = true;
        root.innerHTML = '';
      });
    }
    window.setTimeout(function () {
      if (!root.hidden) {
        root.hidden = true;
        root.innerHTML = '';
      }
    }, 3000);
  }

  function showHtmxToast(message) {
    var root = document.getElementById('htmx-toast-root');
    if (!root) {
      return;
    }
    root.hidden = false;
    root.innerHTML =
      '<div class="htmx-toast" role="alert">' +
      '<span class="htmx-toast__message">' + (message || uiText('data-i18n-generic-error', 'Something went wrong, please try again.')) + '</span>' +
      '<button type="button" class="htmx-toast__close btn-ghost" aria-label="' + uiText('data-i18n-dismiss', 'Dismiss') + '">&times;</button>' +
      '</div>';
    var closeBtn = root.querySelector('.htmx-toast__close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        root.hidden = true;
        root.innerHTML = '';
      });
    }
    window.setTimeout(function () {
      if (!root.hidden) {
        root.hidden = true;
        root.innerHTML = '';
      }
    }, 6000);
  }

  document.body.addEventListener('htmx:configRequest', function (event) {
    if (csrfToken) {
      event.detail.headers['X-CSRFToken'] = csrfToken;
    }
  });

  document.body.addEventListener('htmx:beforeRequest', function (event) {
    if (triggeringElementHasIndicator(event.detail.elt)) {
      return;
    }
    pendingGlobalProgress += 1;
    showGlobalProgress();
  });

  document.body.addEventListener('htmx:afterRequest', function (event) {
    if (triggeringElementHasIndicator(event.detail.elt)) {
      return;
    }
    pendingGlobalProgress = Math.max(0, pendingGlobalProgress - 1);
    hideGlobalProgress();
  });

  document.body.addEventListener('htmx:responseError', function (event) {
    console.error('[HTMX] responseError', event.detail);
    showHtmxToast();
  });

  document.body.addEventListener('htmx:sendError', function (event) {
    console.error('[HTMX] sendError', event.detail);
    showHtmxToast();
  });

  window.showToast = showHtmxToast;

  document.body.addEventListener('addressSaved', function (event) {
    var message = (event.detail && event.detail.message) || uiText('data-i18n-address-saved', 'Address saved');
    showToast(message, 'success');

    var collapseEl = document.getElementById('addAddressCollapse');
    if (collapseEl && window.bootstrap) {
      bootstrap.Collapse.getOrCreateInstance(collapseEl).hide();
    }
  });

  document.body.addEventListener('stockLimitReached', function (event) {
    var message = (event.detail && event.detail.message) || uiText('data-i18n-stock-limit', 'No more stock available.');
    showToast(message);
  });

  document.body.addEventListener('htmx:beforeRequest', function (event) {
    if (triggeringElementHasIndicator(event.detail.elt)) {
      return;
    }
    pendingGlobalProgress += 1;
    showGlobalProgress();
  });

  document.body.addEventListener('htmx:afterRequest', function (event) {
    if (triggeringElementHasIndicator(event.detail.elt)) {
      return;
    }
    pendingGlobalProgress = Math.max(0, pendingGlobalProgress - 1);
    hideGlobalProgress();
  });

  document.body.addEventListener('htmx:responseError', function (event) {
    console.error('[HTMX] responseError', event.detail);
    showHtmxToast();
  });

  document.body.addEventListener('htmx:sendError', function (event) {
    console.error('[HTMX] sendError', event.detail);
    showHtmxToast();
  });

  function openCartDrawer() {
    var offcanvas = document.getElementById('cartOffcanvas');
    if (offcanvas && window.bootstrap) {
      var instance = bootstrap.Offcanvas.getOrCreateInstance(offcanvas);
      if (!offcanvas.classList.contains('show')) {
        instance.show();
      }
    }
  }

  function loadCartDrawerIfNeeded() {
    var body = document.getElementById('cart-drawer-body');
    if (!body || body.dataset.drawerHydrated === 'true' || !window.htmx) {
      return;
    }
    var url = body.getAttribute('hx-get');
    if (!url) {
      return;
    }
    htmx.ajax('GET', url, { target: '#cart-drawer-body', swap: 'innerHTML' });
    body.dataset.drawerHydrated = 'true';
  }

  document.body.addEventListener('cartItemAdded', function () {
    openCartDrawer();
  });

  var cartOffcanvas = document.getElementById('cartOffcanvas');
  if (cartOffcanvas) {
    cartOffcanvas.addEventListener('shown.bs.offcanvas', function () {
      loadCartDrawerIfNeeded();
    });
  }

  document.body.addEventListener('htmx:afterSwap', function (event) {
    if (event.detail.target && event.detail.target.id === 'cart-drawer-body') {
      event.detail.target.dataset.drawerHydrated = 'true';
    }
    if (event.detail.target && event.detail.target.id === 'search-suggestions') {
      initSearchSuggestionsKeyboard();
      updateSearchDropdownState();
    }
  });

  function updateSearchDropdownState() {
    var input = document.getElementById('site-search-input');
    var panel = document.getElementById('search-suggestions-dropdown');
    var results = document.getElementById('search-suggestions');
    if (!input || !panel || !results) {
      return;
    }
    var isOpen = results.innerHTML.trim().length > 0 || panel.querySelector('.htmx-request');
    input.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function closeSearchSuggestions() {
    var input = document.getElementById('site-search-input');
    var results = document.getElementById('search-suggestions');
    if (!input || !results) {
      return;
    }
    results.innerHTML = '';
    input.setAttribute('aria-expanded', 'false');
    input.focus();
  }

  function initSearchSuggestionsKeyboard() {
    var input = document.getElementById('site-search-input');
    var results = document.getElementById('search-suggestions');
    if (!input || !results) {
      return;
    }
    var links = results.querySelectorAll('.search-suggestion-link');
    links.forEach(function (link, index) {
      link.setAttribute('data-suggestion-index', String(index));
    });
    if (links.length) {
      input.dataset.activeSuggestion = '0';
      links[0].classList.add('is-active');
    } else {
      delete input.dataset.activeSuggestion;
    }
  }

  function setActiveSearchSuggestion(input, links, index) {
    links.forEach(function (link) { link.classList.remove('is-active'); });
    if (index < 0 || index >= links.length) {
      delete input.dataset.activeSuggestion;
      return;
    }
    input.dataset.activeSuggestion = String(index);
    links[index].classList.add('is-active');
    links[index].scrollIntoView({ block: 'nearest' });
  }

  var searchInput = document.getElementById('site-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function (event) {
      var results = document.getElementById('search-suggestions');
      if (!results) {
        return;
      }
      var links = results.querySelectorAll('.search-suggestion-link');
      var activeIndex = parseInt(searchInput.dataset.activeSuggestion || '-1', 10);

      if (event.key === 'Escape') {
        event.preventDefault();
        closeSearchSuggestions();
        return;
      }

      if (!links.length) {
        return;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        var next = activeIndex < links.length - 1 ? activeIndex + 1 : 0;
        setActiveSearchSuggestion(searchInput, links, next);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        var prev = activeIndex > 0 ? activeIndex - 1 : links.length - 1;
        setActiveSearchSuggestion(searchInput, links, prev);
      } else if (event.key === 'Enter' && activeIndex >= 0 && links[activeIndex]) {
        event.preventDefault();
        window.location.href = links[activeIndex].href;
      }
    });

    searchInput.addEventListener('input', function () {
      if (!searchInput.value.trim()) {
        closeSearchSuggestions();
      }
    });

    searchInput.addEventListener('blur', function () {
      window.setTimeout(function () {
        var results = document.getElementById('search-suggestions');
        if (!results || document.activeElement === searchInput) {
          return;
        }
        if (!results.contains(document.activeElement)) {
          results.innerHTML = '';
          searchInput.setAttribute('aria-expanded', 'false');
        }
      }, 150);
    });
  }

  document.body.addEventListener('htmx:beforeRequest', function (event) {
    if (event.detail.elt && event.detail.elt.id === 'site-search-input') {
      var results = document.getElementById('search-suggestions');
      if (results) {
        results.innerHTML = '';
      }
      updateSearchDropdownState();
    }
  });

  document.body.addEventListener('htmx:afterRequest', function (event) {
    if (event.detail.elt && event.detail.elt.id === 'site-search-input') {
      updateSearchDropdownState();
    }
  });

  function reinitPageScripts() {
    document.querySelectorAll('.view-toggle [data-view]').forEach(function (btn) {
      if (btn.dataset.boundViewToggle) return;
      btn.dataset.boundViewToggle = '1';
      btn.addEventListener('click', function () {
        var mode = this.getAttribute('data-view');
        document.cookie = 'plp_view=' + mode + ';path=/;max-age=31536000';
        var grid = document.getElementById('product-grid');
        if (grid) {
          grid.className = 'view-' + mode + ' product-grid-shell';
        }
        document.querySelectorAll('.view-toggle .btn').forEach(function (b) {
          b.classList.remove('active');
        });
        this.classList.add('active');
      });
    });

    document.querySelectorAll('.thumb-btn').forEach(function (btn) {
      if (btn.dataset.boundThumb) return;
      btn.dataset.boundThumb = '1';
      btn.addEventListener('click', function () {
        var main = document.getElementById('main-pdp-image');
        if (main) main.src = this.getAttribute('data-full');
        document.querySelectorAll('.thumb-btn').forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
      });
    });
  }

  function applyDocumentLocale(detail) {
    if (!detail || !detail.lang) {
      return;
    }
    document.documentElement.lang = detail.lang;
    document.documentElement.dir = detail.dir || 'ltr';
    var rtlHref = document.body.getAttribute('data-rtl-stylesheet');
    var rtlLink = document.getElementById('rtl-stylesheet');
    if (detail.dir === 'rtl') {
      if (!rtlLink && rtlHref) {
        rtlLink = document.createElement('link');
        rtlLink.id = 'rtl-stylesheet';
        rtlLink.rel = 'stylesheet';
        rtlLink.href = rtlHref;
        document.head.appendChild(rtlLink);
      }
    } else if (rtlLink) {
      rtlLink.remove();
    }

    var bootstrapLink = document.getElementById('bootstrap-stylesheet');
    if (bootstrapLink) {
      var nextHref = detail.dir === 'rtl'
        ? document.body.getAttribute('data-bootstrap-rtl')
        : document.body.getAttribute('data-bootstrap-ltr');
      if (nextHref && bootstrapLink.getAttribute('href') !== nextHref) {
        bootstrapLink.setAttribute('href', nextHref);
      }
    }
  }

  document.body.addEventListener('preferencesUpdated', function (event) {
    applyDocumentLocale(event.detail);
  });

  document.body.addEventListener('htmx:beforeRequest', function (event) {
    if (event.detail.elt && event.detail.elt.classList.contains('preference-switcher')) {
      sessionStorage.setItem('flowardScrollY', String(window.scrollY));
    }
  });

  document.body.addEventListener('htmx:afterSettle', function (event) {
    if (event.detail.target && event.detail.target.id === 'floward-app-shell') {
      var saved = sessionStorage.getItem('flowardScrollY');
      if (saved !== null) {
        window.scrollTo(0, parseInt(saved, 10));
        sessionStorage.removeItem('flowardScrollY');
      }
      reinitPageScripts();
    }
    if (event.detail.target && event.detail.target.id === 'product-grid') {
      event.detail.target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      reinitPageScripts();
    }
  });

  reinitPageScripts();


  (function initMobileSearch() {
    function getElements() {
      return {
        overlay: document.getElementById('mobile-search-overlay'),
        openBtn: document.getElementById('mobile-search-open'),
        input: document.getElementById('mobile-search-input'),
        clearBtn: document.getElementById('mobile-search-clear'),
        results: document.getElementById('mobile-search-results')
      };
    }

    function syncClearButton(elements) {
      if (elements.clearBtn && elements.input) {
        elements.clearBtn.hidden = !elements.input.value.trim();
      }
    }

    function openSearch() {
      var elements = getElements();
      if (!elements.overlay || !elements.openBtn || !elements.input) return;
      elements.overlay.classList.add('is-open');
      elements.overlay.setAttribute('aria-hidden', 'false');
      document.body.classList.add('mobile-search-open');
      elements.openBtn.setAttribute('aria-expanded', 'true');
      document.dispatchEvent(new CustomEvent('floward:mobile-search-open'));
      window.setTimeout(function () {
        var currentInput = document.getElementById('mobile-search-input');
        if (currentInput) currentInput.focus({ preventScroll: true });
      }, 120);
    }

    function closeSearch() {
      var elements = getElements();
      if (!elements.overlay) return;
      elements.overlay.classList.remove('is-open');
      elements.overlay.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('mobile-search-open');
      if (elements.openBtn) elements.openBtn.setAttribute('aria-expanded', 'false');
      if (elements.input) elements.input.blur();
      document.dispatchEvent(new CustomEvent('floward:mobile-search-close'));
    }

    document.addEventListener('click', function (event) {
      var openTrigger = event.target.closest('#mobile-search-open');
      if (openTrigger) {
        openSearch();
        return;
      }

      var dismissTrigger = event.target.closest('[data-search-dismiss]');
      if (dismissTrigger && dismissTrigger.closest('#mobile-search-overlay')) {
        closeSearch();
        return;
      }

      var clearTrigger = event.target.closest('#mobile-search-clear');
      if (!clearTrigger) return;
      var elements = getElements();
      if (!elements.input) return;
      elements.input.value = '';
      if (elements.results) elements.results.innerHTML = '';
      syncClearButton(elements);
      elements.input.focus({ preventScroll: true });
    });

    document.addEventListener('input', function (event) {
      if (!event.target.matches('#mobile-search-input')) return;
      var elements = getElements();
      syncClearButton(elements);
      if (!elements.input.value.trim() && elements.results) {
        elements.results.innerHTML = '';
      }
    });

    document.addEventListener('keydown', function (event) {
      var overlay = document.getElementById('mobile-search-overlay');
      if (event.key === 'Escape' && overlay && overlay.classList.contains('is-open')) {
        closeSearch();
      }
    });

    document.body.addEventListener('htmx:afterSwap', function (event) {
      if (event.detail.target && event.detail.target.id === 'mobile-search-results') {
        syncClearButton(getElements());
      }
    });
  })();

  function initHorizontalRails(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('[data-horizontal-rail]').forEach(function (rail) {
      if (rail.dataset.horizontalRailBound === 'true') return;

      var track = rail.querySelector('[data-horizontal-rail-track]');
      var leftButton = rail.querySelector('[data-horizontal-rail-scroll="-1"]');
      var rightButton = rail.querySelector('[data-horizontal-rail-scroll="1"]');
      if (!track || !leftButton || !rightButton) return;

      rail.dataset.horizontalRailBound = 'true';

      function updateButtons() {
        var trackRect = track.getBoundingClientRect();
        var hasContentToLeft = false;
        var hasContentToRight = false;

        Array.prototype.some.call(track.children, function (item) {
          var itemRect = item.getBoundingClientRect();
          hasContentToLeft = hasContentToLeft || itemRect.left < trackRect.left - 2;
          hasContentToRight = hasContentToRight || itemRect.right > trackRect.right + 2;
          return hasContentToLeft && hasContentToRight;
        });

        leftButton.disabled = !hasContentToLeft;
        rightButton.disabled = !hasContentToRight;
      }

      function scrollRail(direction) {
        var firstItem = track.firstElementChild;
        var gap = parseFloat(window.getComputedStyle(track).columnGap) || 0;
        var itemStep = firstItem ? firstItem.getBoundingClientRect().width + gap : 0;
        var distance = Math.max(itemStep * 2, track.clientWidth * 0.72);
        track.scrollBy({ left: direction * distance, behavior: 'smooth' });
      }

      leftButton.addEventListener('click', function () { scrollRail(-1); });
      rightButton.addEventListener('click', function () { scrollRail(1); });
      track.addEventListener('scroll', updateButtons, { passive: true });

      var isDown = false;
      var startX = 0;
      var startScrollLeft = 0;
      track.addEventListener('mousedown', function (event) {
        isDown = true;
        startX = event.pageX;
        startScrollLeft = track.scrollLeft;
        track.style.cursor = 'grabbing';
      });
      track.addEventListener('mouseleave', function () {
        isDown = false;
        track.style.cursor = '';
      });
      track.addEventListener('mouseup', function () {
        isDown = false;
        track.style.cursor = '';
      });
      track.addEventListener('mousemove', function (event) {
        if (!isDown) return;
        event.preventDefault();
        track.scrollLeft = startScrollLeft - (event.pageX - startX) * 1.5;
      });

      if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(updateButtons).observe(track);
      } else {
        window.addEventListener('resize', updateButtons);
      }
      updateButtons();
    });
  }

  initHorizontalRails(document);
  document.body.addEventListener('htmx:afterSwap', function (event) {
    initHorizontalRails(event.detail.target);
  });
})();

// subscription

(function () {
  var hiddenSelect = document.getElementById('id_product_id');
  var trigger = document.getElementById('sub-product-trigger');
  var panel = document.getElementById('sub-product-panel');
  var selectedLabel = document.getElementById('sub-product-selected');
  var search = document.getElementById('sub-product-search');
  var options = document.querySelectorAll('.sub-product-option');

  if (!hiddenSelect || !trigger) return;

  var preselectedId = hiddenSelect.value;
  if (preselectedId) {
    options.forEach(function (opt) {
      if (opt.dataset.id === preselectedId) {
        selectedLabel.innerHTML = opt.innerHTML;
        selectedLabel.classList.remove('text-muted');
      }
    });
  }

  trigger.addEventListener('click', function () {
    panel.classList.toggle('is-open');
    if (panel.classList.contains('is-open')) search.focus();
  });

  document.addEventListener('click', function (evt) {
    if (!evt.target.closest('.sub-product-picker')) panel.classList.remove('is-open');
  });

  options.forEach(function (opt) {
    opt.addEventListener('click', function () {
      hiddenSelect.value = opt.dataset.id;
      selectedLabel.innerHTML = opt.innerHTML;
      selectedLabel.classList.remove('text-muted');
      panel.classList.remove('is-open');
    });
  });

  search.addEventListener('input', function () {
    var q = this.value.trim().toLowerCase();
    options.forEach(function (opt) {
      var match = opt.dataset.name.toLowerCase().indexOf(q) !== -1;
      opt.style.display = match ? 'flex' : 'none';
    });
  });
})();

function toggleFullName(event, el) {
  event.preventDefault(); // stop navigation to PDP on click
  const span = el.querySelector('.name-display');
  const full = el.dataset.fullName;
  const isExpanded = el.dataset.expanded === 'true';

  if (isExpanded) {
    span.textContent = full.length > 30 ? full.slice(0, 30) + '…' : full;
    el.dataset.expanded = 'false';
  } else {
    span.textContent = full;
    el.dataset.expanded = 'true';
  }
  return false;
}