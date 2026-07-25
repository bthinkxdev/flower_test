(function () {
  function destroySelect(wrapper) {
    // Undo a previous enhancement: put the native <select> back where it was
    // and drop the decorative trigger/panel, so re-scanning a subtree never
    // stacks a second wrapper on top of an already-enhanced select.
    var select = wrapper.querySelector('select');
    if (select) {
      delete select.dataset.enhanced;
      select.classList.remove('floward-select__native');
      select.removeAttribute('tabindex');
      wrapper.parentNode.insertBefore(select, wrapper);
    }
    wrapper.parentNode.removeChild(wrapper);
  }

  function resetEnhanced(root) {
    (root || document).querySelectorAll('.floward-select').forEach(destroySelect);
  }

  function buildSelect(select) {
    if (select.dataset.enhanced || select.multiple) return;
    select.dataset.enhanced = "true";

    var isNav = select.classList.contains("preference-switcher");
    var wrapper = document.createElement("div");
    wrapper.className =
      "floward-select" +
      (select.classList.contains("form-select-sm") ? " floward-select--sm" : "") +
      (isNav ? " floward-select--nav" : "");

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "floward-select__trigger";
    trigger.disabled = select.disabled;
    if (select.getAttribute("aria-label")) {
      trigger.setAttribute("aria-label", select.getAttribute("aria-label"));
    }

    var label = document.createElement("span");
    label.className = "floward-select__label";

    var chevron = document.createElement("span");
    chevron.className = "floward-select__chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML =
      '<svg viewBox="0 0 12 8" width="10" height="7" fill="none"><path d="M1 1.5L6 6.5L11 1.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    trigger.appendChild(label);
    trigger.appendChild(chevron);

    var panel = document.createElement("div");
    panel.className = "floward-select__panel";
    panel.setAttribute("role", "listbox");

    Array.prototype.forEach.call(select.options, function (opt) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "floward-select__option" + (opt.selected ? " is-selected" : "");
      btn.textContent = opt.textContent;
      btn.dataset.value = opt.value;
      btn.setAttribute("role", "option");
      if (opt.selected) btn.setAttribute("aria-selected", "true");
      panel.appendChild(btn);
    });

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(trigger);
    wrapper.appendChild(panel);
    select.classList.add("floward-select__native");
    select.tabIndex = -1;

    function syncLabel() {
      var selectedOpt = select.options[select.selectedIndex];
      label.textContent = selectedOpt ? selectedOpt.textContent : "";
      Array.prototype.forEach.call(panel.children, function (child) {
        var selected = child.dataset.value === select.value;
        child.classList.toggle("is-selected", selected);
        child.setAttribute("aria-selected", selected ? "true" : "false");
      });
    }
    syncLabel();

    function closePanel() {
      wrapper.classList.remove("is-open");
      trigger.setAttribute("aria-expanded", "false");
    }
    function openPanel() {
      wrapper.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
    }

    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-haspopup", "listbox");

    trigger.addEventListener("click", function () {
      if (select.disabled) return;
      wrapper.classList.contains("is-open") ? closePanel() : openPanel();
    });

    document.addEventListener("click", function (evt) {
      if (!wrapper.isConnected) return;
      if (!wrapper.contains(evt.target)) closePanel();
    });

    document.addEventListener("keydown", function (evt) {
      if (evt.key === "Escape") closePanel();
    });

    Array.prototype.forEach.call(panel.children, function (btn) {
      btn.addEventListener("click", function () {
        select.value = btn.dataset.value;
        syncLabel();
        closePanel();
        select.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });

    select.addEventListener("change", syncLabel);
  }

  function init(root) {
    var scope = root || document;
    resetEnhanced(scope);
    scope
      .querySelectorAll(
        "select.form-select:not([multiple]), select.preference-switcher:not([multiple])"
      )
      .forEach(buildSelect);
  }

  document.addEventListener('DOMContentLoaded', function () { init(document); });
  document.body.addEventListener('htmx:afterSettle', function (evt) {
    init((evt.detail && evt.detail.target) || document);
  });
})();
