
(function () {
  "use strict";


  function initSidebar() {
    var sidebar = document.getElementById("sidebar");
    var content = document.getElementById("content");
    var topbar = document.getElementById("topbar");
    var toggleBtn = document.getElementById("toggleBtn");
    var mobileBtn = document.getElementById("mobileBtn");
    var overlay = document.getElementById("overlay");

    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        if (sidebar) sidebar.classList.toggle("collapsed");
        if (content) content.classList.toggle("full");
        if (topbar) topbar.classList.toggle("full");
      });
    }
    if (mobileBtn) {
      mobileBtn.addEventListener("click", function () {
        if (sidebar) sidebar.classList.add("mobile-show");
        if (overlay) overlay.classList.add("show");
      });
    }
    if (overlay) {
      overlay.addEventListener("click", function () {
        if (sidebar) sidebar.classList.remove("mobile-show");
        if (overlay) overlay.classList.remove("show");
      });
    }

    if (sidebar) {
      var activeLink = sidebar.querySelector(".nav-link.active");
      if (activeLink) {
        var linkOffset = activeLink.offsetTop;
        var sidebarHeight = sidebar.clientHeight;
        sidebar.scrollTop = linkOffset - (sidebarHeight / 2) + (activeLink.clientHeight / 2);
      }
    }
  }


  function initFormValidation() {
    var forms = document.querySelectorAll(".needs-validation");
    Array.prototype.forEach.call(forms, function (form) {
      form.addEventListener("submit", function (event) {
        if (!form.checkValidity()) {
          event.preventDefault();
          event.stopPropagation();
          form.querySelectorAll(".is-invalid").forEach(function(el) { el.classList.remove("is-invalid"); });
          form.querySelectorAll(":invalid").forEach(function(el) {
              el.classList.add("is-invalid");
              var parent = el.parentNode;
              var feedback = parent.querySelector(".invalid-feedback");
              if (!feedback) {
                  feedback = document.createElement("div");
                  feedback.className = "invalid-feedback";
                  parent.appendChild(feedback);
              }
              feedback.style.display = "block";
              feedback.textContent = el.validationMessage || "Please fill out this field.";
          });
        }
      }, false);
      
      form.addEventListener("input", function(e) {
          if (e.target.classList.contains("is-invalid") && e.target.checkValidity()) {
              e.target.classList.remove("is-invalid");
              var feedback = e.target.parentNode.querySelector(".invalid-feedback");
              if (feedback) feedback.style.display = "none";
          }
      });
    });
  }


  function readJSON(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return fallback;
    }
  }

  function currency(val) {
    var n = Number(val || 0);
    return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  function initCharts() {
    if (typeof ApexCharts === "undefined") return;


    var salesEl = document.querySelector("#salesChart");
    if (salesEl) {
      var sales = readJSON("sales-chart-data", { categories: [], revenue: [], orders: [] });
      new ApexCharts(salesEl, {
        chart: {
          type: "area",
          height: 360,
          fontFamily: "Poppins, sans-serif",
          toolbar: { show: false },
          zoom: { enabled: false },
        },
        colors: ["#e66239", "#2e90fa"],
        stroke: { width: [3, 2], curve: "smooth" },
        dataLabels: { enabled: false },
        series: [
          { name: "Revenue", data: sales.revenue },
          { name: "Orders", data: sales.orders },
        ],
        fill: {
          type: "gradient",
          gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, stops: [0, 100] },
        },
        grid: { borderColor: "#eef0f3", strokeDashArray: 4, padding: { left: 8, right: 8 } },
        xaxis: {
          categories: sales.categories,
          tickPlacement: "on",
          axisBorder: { show: false },
          axisTicks: { show: false },
          labels: { style: { colors: "#667085", fontSize: "11px" } },
        },
        yaxis: [
          { labels: { formatter: currency, style: { colors: "#667085" } } },
          {
            opposite: true,
            labels: {
              formatter: function (v) { return Math.round(v); },
              style: { colors: "#667085" },
            },
          },
        ],
        tooltip: { shared: true },
        legend: { position: "top", horizontalAlign: "right", markers: { radius: 12 } },
      }).render();
    }

    var custEl = document.querySelector("#customerChart");
    if (custEl) {
      var cust = readJSON("customer-chart-data", { series: [0, 0] });
      new ApexCharts(custEl, {
        chart: { type: "donut", height: 260, fontFamily: "Poppins, sans-serif" },
        colors: ["#e66239", "#2e90fa"],
        series: cust.series,
        labels: ["New", "Returning"],
        stroke: { width: 0 },
        legend: { position: "bottom", markers: { radius: 12 } },
        dataLabels: {
          enabled: true,
          formatter: function (val) { return Math.round(val) + "%"; },
          style: { fontSize: "12px", fontWeight: 600 },
          dropShadow: { enabled: false },
        },
        plotOptions: {
          pie: {
            donut: {
              size: "70%",
              labels: {
                show: true,
                total: {
                  show: true,
                  label: "Customers",
                  fontSize: "13px",
                  color: "#667085",
                  formatter: function () { return "100%"; },
                },
              },
            },
          },
        },
      }).render();
    }
  }

  // ---- Dynamic inline formsets (product variants / images) ---------------
  function initFormsets() {
    var wraps = document.querySelectorAll("[data-formset]");
    Array.prototype.forEach.call(wraps, function (wrap) {
      var prefix = wrap.getAttribute("data-formset");
      var total = document.getElementById("id_" + prefix + "-TOTAL_FORMS");
      var body = wrap.querySelector("[data-formset-body]");
      var tmpl = wrap.querySelector("template[data-formset-empty]");
      var addBtn = wrap.querySelector("[data-formset-add]");

      if (addBtn && total && body && tmpl) {
        addBtn.addEventListener("click", function () {
          var idx = parseInt(total.value, 10);
          var html = tmpl.innerHTML.replace(/__prefix__/g, idx);
          var holder = document.createElement("tbody");
          holder.innerHTML = html.trim();
          var row = holder.firstElementChild;
          if (row) {
            body.appendChild(row);
            total.value = idx + 1;
          }
        });
      }

      wrap.addEventListener("click", function (e) {
        var btn = e.target.closest ? e.target.closest("[data-row-remove]") : null;
        if (!btn) return;
        var row = btn.closest("tr");
        if (!row) return;
        Array.prototype.forEach.call(row.querySelectorAll("input, select, textarea"), function (inp) {
          if (inp.type === "checkbox" || inp.type === "radio") inp.checked = false;
          else if (inp.type !== "hidden") inp.value = "";
        });
        row.style.display = "none";
      });

      wrap.addEventListener("change", function (e) {
        var inp = e.target;
        if (inp.type === "file" && inp.files && inp.files[0]) {
          var row = inp.closest("tr");
          var prev = row ? row.querySelector("[data-img-preview]") : null;
          if (prev) {
            prev.src = URL.createObjectURL(inp.files[0]);
            prev.classList.remove("d-none");
          }
          if (prefix === "images") {
            var checkboxes = wrap.querySelectorAll('input[type="checkbox"][name$="-is_primary"]');
            var isAnyPrimary = Array.prototype.some.call(checkboxes, function (cb) { return cb.checked; });
            if (!isAnyPrimary) {
              var currentCb = row ? row.querySelector('input[type="checkbox"][name$="-is_primary"]') : null;
              if (currentCb) currentCb.checked = true;
            }
          }
        }
      });
    });
  }

  function initAutoDismissAlerts() {
    document.querySelectorAll(".alert-dismissible").forEach(function (alertEl) {
      window.setTimeout(function () {
        if (window.bootstrap && document.body.contains(alertEl)) {
          bootstrap.Alert.getOrCreateInstance(alertEl).close();
        }
      }, 3000);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSidebar();
    initFormValidation();
    initCharts();
    initFormsets();
    initAutoDismissAlerts();
  });
})();
