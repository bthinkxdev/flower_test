(function () {
  function buildSelect(select) {
    if (select.dataset.enhanced || select.multiple) return;
    select.dataset.enhanced = 'true';

    var wrapper = document.createElement('div');
    wrapper.className = 'floward-select' + (select.classList.contains('form-select-sm') ? ' floward-select--sm' : '');

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'floward-select__trigger';
    trigger.disabled = select.disabled;

    var label = document.createElement('span');
    label.className = 'floward-select__label';

    var chevron = document.createElement('span');
    chevron.className = 'floward-select__chevron';
    chevron.innerHTML = '<svg viewBox="0 0 12 8" width="12" height="8" fill="none"><path d="M1 1.5L6 6.5L11 1.5" stroke="#8b3a4a" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    trigger.appendChild(label);
    trigger.appendChild(chevron);

    var panel = document.createElement('div');
    panel.className = 'floward-select__panel';

    Array.prototype.forEach.call(select.options, function (opt) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'floward-select__option' + (opt.selected ? ' is-selected' : '');
      btn.textContent = opt.textContent;
      btn.dataset.value = opt.value;
      panel.appendChild(btn);
    });

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(trigger);
    wrapper.appendChild(panel);
    select.classList.add('floward-select__native');
    select.tabIndex = -1;

    function syncLabel() {
      var selectedOpt = select.options[select.selectedIndex];
      label.textContent = selectedOpt ? selectedOpt.textContent : '';
      Array.prototype.forEach.call(panel.children, function (child) {
        child.classList.toggle('is-selected', child.dataset.value === select.value);
      });
    }
    syncLabel();

    function closePanel() { wrapper.classList.remove('is-open'); }
    function openPanel() { wrapper.classList.add('is-open'); }

    trigger.addEventListener('click', function () {
      if (select.disabled) return;
      wrapper.classList.contains('is-open') ? closePanel() : openPanel();
    });

    document.addEventListener('click', function (evt) {
      if (!wrapper.contains(evt.target)) closePanel();
    });

    document.addEventListener('keydown', function (evt) {
      if (evt.key === 'Escape') closePanel();
    });

    Array.prototype.forEach.call(panel.children, function (btn) {
      btn.addEventListener('click', function () {
        select.value = btn.dataset.value;
        syncLabel();
        closePanel();
        select.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });

    select.addEventListener('change', syncLabel);
  }

  function init(root) {
    (root || document).querySelectorAll('select.form-select:not([multiple])').forEach(buildSelect);
  }

  document.addEventListener('DOMContentLoaded', function () { init(document); });
  document.body.addEventListener('htmx:afterSwap', function (evt) { init(evt.target); });
})();
