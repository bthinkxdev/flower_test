(function () {
  "use strict";

  function syncEnhancedSelect(select) {
    var wrapper = select.closest(".floward-select");
    if (!wrapper) return;
    var selected = select.options[select.selectedIndex];
    var label = wrapper.querySelector(".floward-select__label");
    if (label) label.textContent = selected ? selected.textContent : "";
    wrapper
      .querySelectorAll(".floward-select__option")
      .forEach(function (option, index) {
        option.classList.toggle("is-selected", index === select.selectedIndex);
        option.setAttribute(
          "aria-selected",
          index === select.selectedIndex ? "true" : "false"
        );
      });
  }

  function syncOtherForms(source) {
    var sourceForm = source.closest("form.plp-filters");
    if (!sourceForm || sourceForm.dataset.syncing === "1" || !source.name) return;

    document.querySelectorAll("form.plp-filters").forEach(function (form) {
      if (form === sourceForm) return;
      form.dataset.syncing = "1";
      try {
        var target = form.querySelector('[name="' + source.name + '"]');
        if (!target) return;
        if (source.type === "checkbox") {
          target.checked = source.checked;
        } else {
          target.value = source.value;
          if (target.tagName === "SELECT") syncEnhancedSelect(target);
        }
      } finally {
        delete form.dataset.syncing;
      }
    });
  }

  document.body.addEventListener("change", function (event) {
    var input = event.target;
    if (!input || !input.closest || !input.closest("form.plp-filters")) return;
    syncOtherForms(input);
  });

  document.body.addEventListener("input", function (event) {
    var input = event.target;
    if (!input || !input.closest || !input.closest("form.plp-filters")) return;
    if (input.name === "min_price" || input.name === "max_price") {
      syncOtherForms(input);
    }
  });

  document.body.addEventListener("click", function (event) {
    if (!event.target.closest(".plp-clear-filters")) return;
    document.querySelectorAll("form.plp-filters").forEach(function (form) {
      form.querySelectorAll("select").forEach(function (select) {
        select.selectedIndex = 0;
        syncEnhancedSelect(select);
      });
      form
        .querySelectorAll('input[type="text"], input[type="number"]')
        .forEach(function (input) {
          input.value = "";
        });
      form
        .querySelectorAll('input[type="checkbox"]')
        .forEach(function (checkbox) {
          checkbox.checked = false;
        });
    });
  });

  var priceTimer = null;
  document.body.addEventListener("input", function (event) {
    var input = event.target;
    if (
      !input ||
      (input.name !== "min_price" && input.name !== "max_price")
    ) {
      return;
    }
    var form = input.closest("form.plp-filters");
    if (!form) return;
    clearTimeout(priceTimer);
    priceTimer = setTimeout(function () {
      if (window.htmx) {
        window.htmx.trigger(form, "submit");
      } else if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }, 400);
  });

  // Close only after the mobile form successfully refreshed the product grid.
  document.body.addEventListener("htmx:afterRequest", function (event) {
    var detail = event.detail || {};
    var source = detail.elt;
    if (!detail.successful || !source || !source.closest) return;
    if (!source.closest("#plpFilters")) return;
    if (!window.matchMedia("(max-width: 991.98px)").matches) return;

    var drawer = document.getElementById("plpFilters");
    if (!drawer || !window.bootstrap || !window.bootstrap.Offcanvas) return;
    var instance = window.bootstrap.Offcanvas.getInstance(drawer);
    if (instance) instance.hide();
  });
})();
