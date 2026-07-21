(function () {
  'use strict';

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
      '<button type="button" class="htmx-toast__close btn-ghost" aria-label="Dismiss">&times;</button>' +
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
      '<span class="htmx-toast__message">' + (message || 'Something went wrong, please try again.') + '</span>' +
      '<button type="button" class="htmx-toast__close btn-ghost" aria-label="Dismiss">&times;</button>' +
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
    var message = (event.detail && event.detail.message) || 'Address saved';
    showToast(message, 'success');

    var collapseEl = document.getElementById('addAddressCollapse');
    if (collapseEl && window.bootstrap) {
      bootstrap.Collapse.getOrCreateInstance(collapseEl).hide();
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
    var overlay = document.getElementById('mobile-search-overlay');
    var openBtn = document.getElementById('mobile-search-open');
    var input = document.getElementById('mobile-search-input');
    var clearBtn = document.getElementById('mobile-search-clear');
    var results = document.getElementById('mobile-search-results');
    if (!overlay || !openBtn || !input) {
      return;
    }

    function openSearch() {
      overlay.classList.add('is-open');
      overlay.setAttribute('aria-hidden', 'false');
      document.body.classList.add('mobile-search-open');
      openBtn.setAttribute('aria-expanded', 'true');
      window.setTimeout(function () {
        input.focus({ preventScroll: true });
      }, 120);
    }

    function closeSearch() {
      overlay.classList.remove('is-open');
      overlay.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('mobile-search-open');
      openBtn.setAttribute('aria-expanded', 'false');
      input.blur();
    }

    function syncClearButton() {
      if (!clearBtn) {
        return;
      }
      clearBtn.hidden = !input.value.trim();
    }

    openBtn.addEventListener('click', openSearch);

    overlay.querySelectorAll('[data-search-dismiss]').forEach(function (el) {
      el.addEventListener('click', closeSearch);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && overlay.classList.contains('is-open')) {
        closeSearch();
      }
    });

    input.addEventListener('input', function () {
      syncClearButton();
      if (!input.value.trim() && results) {
        results.innerHTML = '';
      }
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        input.value = '';
        if (results) {
          results.innerHTML = '';
        }
        syncClearButton();
        input.focus({ preventScroll: true });
      });
    }

    document.body.addEventListener('htmx:afterSwap', function (event) {
      if (event.detail.target && event.detail.target.id === 'mobile-search-results') {
        syncClearButton();
      }
    });
  })();

  document.querySelectorAll('.product-rail-scroll, .chip-scroll').forEach(function (rail) {
    var isDown = false;
    var startX;
    var scrollLeft;
    rail.addEventListener('mousedown', function (e) {
      isDown = true;
      startX = e.pageX - rail.offsetLeft;
      scrollLeft = rail.scrollLeft;
      rail.style.cursor = 'grabbing';
    });
    rail.addEventListener('mouseleave', function () { isDown = false; rail.style.cursor = ''; });
    rail.addEventListener('mouseup', function () { isDown = false; rail.style.cursor = ''; });
    rail.addEventListener('mousemove', function (e) {
      if (!isDown) return;
      e.preventDefault();
      var x = e.pageX - rail.offsetLeft;
      rail.scrollLeft = scrollLeft - (x - startX) * 1.5;
    });
  });
})();

// Featured brands rail: arrow scrolling + auto-hide disabled state
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.brand-rail').forEach((rail) => {
    const track = rail.querySelector('[data-brand-track]');
    const prevBtn = rail.querySelector('[data-brand-scroll="prev"]');
    const nextBtn = rail.querySelector('[data-brand-scroll="next"]');
    if (!track || !prevBtn || !nextBtn) return;

    const scrollByCard = (dir) => {
      const card = track.querySelector('.brand-card');
      const gap = 20;
      const distance = card ? card.offsetWidth + gap : 220;
      track.scrollBy({ left: dir * distance * 2, behavior: 'smooth' });
    };

    prevBtn.addEventListener('click', () => scrollByCard(-1));
    nextBtn.addEventListener('click', () => scrollByCard(1));

    const updateArrowState = () => {
      const maxScroll = track.scrollWidth - track.clientWidth - 1;
      prevBtn.disabled = track.scrollLeft <= 0;
      nextBtn.disabled = track.scrollLeft >= maxScroll || maxScroll <= 0;
    };

    track.addEventListener('scroll', updateArrowState, { passive: true });
    window.addEventListener('resize', updateArrowState);
    updateArrowState();
  });
});

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

// Reset filter selects/inputs visually when "Clear Filters" is clicked
document.body.addEventListener('click', function (evt) {
  var btn = evt.target.closest('.plp-clear-filters');
  if (!btn) return;
  var form = btn.closest('form');
  if (!form) return;

  form.querySelectorAll('select').forEach(function (sel) {
    sel.selectedIndex = 0;
    var wrapper = sel.closest('.floward-select');
    if (wrapper) {
      var label = wrapper.querySelector('.floward-select__label');
      var opt = sel.options[0];
      if (label) label.textContent = opt ? opt.textContent : '';
      wrapper.querySelectorAll('.floward-select__option').forEach(function (o, i) {
        o.classList.toggle('is-selected', i === 0);
      });
    }
  });
  form.querySelectorAll('input[type="text"], input[type="number"]').forEach(function (inp) { inp.value = ''; });
  form.querySelectorAll('input[type="checkbox"]').forEach(function (cb) { cb.checked = false; });
});