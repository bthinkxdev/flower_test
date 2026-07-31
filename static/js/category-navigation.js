(function () {
  "use strict";

  function closeItem(item) {
    item.classList.remove("is-open");
    var toggle = item.querySelector("[data-category-toggle]");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }

  function closeAll(except) {
    document
      .querySelectorAll(".category-navigation__item.is-open")
      .forEach(function (item) {
        if (item !== except) closeItem(item);
      });
  }

  document.body.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-category-toggle]");
    if (toggle) {
      event.preventDefault();
      var item = toggle.closest(".category-navigation__item");
      if (!item) return;
      var willOpen = !item.classList.contains("is-open");
      closeAll(item);
      item.classList.toggle("is-open", willOpen);
      toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
      return;
    }

    if (!event.target.closest(".category-navigation__item")) closeAll();

    var navLink = event.target.closest("[data-mobile-nav-link]");
    var mobileNav = document.getElementById("mainNav");
    if (
      navLink &&
      mobileNav &&
      window.matchMedia("(max-width: 991.98px)").matches &&
      window.bootstrap &&
      window.bootstrap.Offcanvas
    ) {
      var navInstance = window.bootstrap.Offcanvas.getInstance(mobileNav);
      if (navInstance) navInstance.hide();
    }
  });

  var mobileNav = document.getElementById("mainNav");
  if (mobileNav) {
    mobileNav.addEventListener("hidden.bs.offcanvas", function () {
      closeAll();
    });
  }
})();
