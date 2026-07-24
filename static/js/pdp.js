(function () {
  var variantSelect = document.getElementById('variant-select');
  if (variantSelect) {
    variantSelect.addEventListener('change', function () {
      var url = this.getAttribute('data-price-url');
      var vid = this.value;
      document.querySelectorAll('.pdp-variant-id-field').forEach(function (field) {
        field.value = vid;
      });
      fetch(url + (vid ? '?variant_id=' + vid : ''))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var priceEl = document.getElementById('pdp-price');
          if (priceEl) priceEl.textContent = data.price + ' ' + data.currency_code;
          var stickyPriceEl = document.getElementById('pdp-sticky-price');
          if (stickyPriceEl) stickyPriceEl.textContent = data.price + ' ' + data.currency_code;

          var inStock = data.is_in_stock === 'true' || data.is_in_stock === true;
          document.querySelectorAll('.pdp-add-to-cart-btn').forEach(function (btn) {
            btn.disabled = !inStock || btn.classList.contains('is-in-cart') === false ? !inStock : btn.disabled;
            btn.disabled = !inStock;
          });
          var stockText = document.getElementById('pdp-stock-text');
          if (stockText) {
            stockText.textContent = inStock ? 'In stock(' + data.stock_quantity + ') — order now' : 'Out of stock';
            stockText.classList.toggle('text-success', inStock);
            stockText.classList.toggle('text-danger', !inStock);
          }
        });
    });
  }

  var citySelect = document.getElementById('delivery-city');
  if (citySelect) {
    citySelect.addEventListener('change', function () {
      var url = this.getAttribute('data-estimate-url') + '?city=' + this.value;
      fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var el = document.getElementById('delivery-estimate-text');
          if (el) el.textContent = 'Delivery: ' + data.label + ' to ' + data.city;
        });
    });
  }

  function openCartDrawer() {
    var offcanvasEl = document.getElementById('cartOffcanvas');
    if (offcanvasEl && window.bootstrap) {
      window.bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl).show();
    }
  }

  document.querySelectorAll('.pdp-add-to-cart-btn').forEach(function (btn) {
    btn.addEventListener('click', function (evt) {
      if (btn.classList.contains('is-in-cart')) {
        evt.preventDefault();
        evt.stopImmediatePropagation();
        if (btn.dataset.cartUrl) {
          window.location.href = btn.dataset.cartUrl;
        } else {
          openCartDrawer();
        }
      }
    }, true);
  });

  document.body.addEventListener('htmx:afterRequest', function (event) {
    var elt = event.detail.elt;
    if (!elt || !elt.classList) return;
    var isCartForm = elt.classList.contains('pdp-add-to-cart-form');
    var isCartBtn = elt.classList.contains('pdp-add-to-cart-btn');
    if (!isCartForm && !isCartBtn) return;
    if (!event.detail.successful) return;

    var btn = isCartBtn ? elt : elt.querySelector('.pdp-add-to-cart-btn');
    if (!btn) return;

    btn.classList.add('is-added');
    window.setTimeout(function () {
      btn.classList.remove('is-added');
      btn.classList.add('is-in-cart');
      var label = btn.querySelector('.btn-label');
      if (label) label.textContent = btn.dataset.addedLabel || 'View Cart';
    }, 900);
  });
})();