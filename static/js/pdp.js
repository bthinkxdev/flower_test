(function () {
  var variantSelect = document.getElementById('variant-select');
  if (variantSelect) {
    variantSelect.addEventListener('change', function () {
      var url = this.getAttribute('data-price-url');
      var vid = this.value;
      fetch(url + (vid ? '?variant_id=' + vid : ''))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var el = document.getElementById('pdp-price');
          if (el) el.textContent = data.price + ' QAR';
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
})();
