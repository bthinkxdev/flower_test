(function () {
  const form = document.getElementById("gift-builder-form");
  if (!form) return;

  const qtyPrimary = form.querySelector('[name="quantity"]');
  const qtyMirror = document.querySelector("[data-qty-mirror]");
  if (qtyPrimary && qtyMirror) {
    const sync = (from, to) => {
      from.addEventListener("input", () => {
        to.value = from.value;
      });
    };
    sync(qtyPrimary, qtyMirror);
    sync(qtyMirror, qtyPrimary);
  }

  function collectAddonIds() {
    const checked = form.querySelectorAll('input[name="addon_product_ids"]:checked');
    return Array.from(checked).map((el) => el.value);
  }

  function collectSelections() {
    const data = new FormData(form);
    return {
      personal_message: data.get("personal_message") || "",
      greeting_card_id: data.get("greeting_card_id") || null,
      gift_wrap_id: data.get("gift_wrap_id") || null,
      ribbon_id: data.get("ribbon_id") || null,
      photo_upload_id: data.get("photo_upload_id") || null,
      addon_product_ids: collectAddonIds(),
      delivery_date: data.get("delivery_date") || null,
      delivery_slot_id: data.get("delivery_slot_id") || null,
      delivery_instructions: data.get("delivery_instructions") || "",
      recipient_phone: data.get("recipient_phone") || "",
      is_anonymous: !!form.querySelector('[name="is_anonymous"]')?.checked,
      reveal_sender_after_delivery:
        !!form.querySelector('[name="reveal_sender_after_delivery"]')?.checked,
      is_gift_receipt: !!form.querySelector('[name="is_gift_receipt"]')?.checked,
    };
  }

  document.body.addEventListener("htmx:configRequest", function (event) {
    const elt = event.detail.elt;
    if (!elt) return;
    const eltId = elt.id;
    const fromForm = elt === form || form.contains(elt);
    const isAddToCart = eltId === "add-to-cart-btn" || eltId === "add-to-cart-btn-mobile";
    if (!fromForm && !isAddToCart) return;

    if (isAddToCart) {
      event.detail.parameters = {
        product_id: form.dataset.productId,
        quantity: form.querySelector('[name="quantity"]')?.value || 1,
        gift_selections: JSON.stringify(collectSelections()),
        line_item_ref_id: form.querySelector('[name="line_item_ref_id"]')?.value || "",
        snapshot_version: form.querySelector('[name="snapshot_version"]')?.value || "",
      };
      return;
    }

    event.detail.parameters["addon_product_ids"] = collectAddonIds().join(",");
  });

  function resetCartButtons() {
    ["add-to-cart-btn", "add-to-cart-btn-mobile"].forEach((id) => {
      const btn = document.getElementById(id);
      if (!btn || !btn.classList.contains("is-in-cart")) return;
      btn.classList.remove("is-in-cart");
      const label = btn.querySelector(".btn-label");
      if (label) {
        label.textContent = form.dataset.addToCartLabel || "Add to Cart";
      }
    });
  }

  form.addEventListener("change", resetCartButtons);

  document.body.addEventListener("cartItemAdded", function () {
    const el = document.getElementById("add-to-cart-feedback");
    if (el) {
      el.textContent = form.dataset.addedToCartLabel || "Added to cart!";
      setTimeout(() => { el.textContent = ""; }, 3000);
    }
  });

  document.body.addEventListener("htmx:afterRequest", function (event) {
    const elt = event.detail.elt;
    if (!elt || !elt.id) return;
    const isAddToCart = elt.id === "add-to-cart-btn" || elt.id === "add-to-cart-btn-mobile";
    if (!isAddToCart) return;
    if (!event.detail.successful) return;

    elt.classList.add("is-added");
    window.setTimeout(() => {
      elt.classList.remove("is-added");
      elt.classList.add("is-in-cart");
      const label = elt.querySelector(".btn-label");
      if (label) label.textContent = elt.dataset.addedLabel || "View Cart";
    }, 900);
  });
})();
