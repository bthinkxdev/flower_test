
(function () {
  const form = document.getElementById("gift-builder-form");
  if (!form) return;

  form.addEventListener("htmx:configRequest", function (event) {
    const checked = form.querySelectorAll('input[name="addon_product_ids"]:checked');
    const ids = Array.from(checked).map((el) => el.value);
    event.detail.parameters["addon_product_ids"] = ids.join(",");
  });
})();
