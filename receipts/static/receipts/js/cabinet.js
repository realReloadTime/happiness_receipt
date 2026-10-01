(function () {
  "use strict";

  var table = document.getElementById("receipts-table");
  if (table) {
    initPolling(table);
  }

  var winModal = document.getElementById("win-modal");
  if (winModal) {
    initWinModal(winModal);
  }

  /* --- Автообновление статусов без перезагрузки ---------------------------- */
  function initPolling(table) {
    var POLL_INTERVAL = 15000; // каждые 15 секунд
    var page = parseInt(new URLSearchParams(window.location.search).get("page") || "1", 10);
    var apiUrl = "/api/receipts/?page=" + page;

    var STATUS_CLASSES = {
      pending: "status-pending",
      accepted: "status-accepted",
      rejected: "status-rejected",
      won: "status-won",
      lost: "status-lost"
    };

    function updateRow(row, data) {
      if (!row) return;

      var badge = row.querySelector(".status-badge");
      if (badge && badge.textContent !== data.status_display) {
        badge.textContent = data.status_display;
        badge.className = "status-badge " + (STATUS_CLASSES[data.status] || "status-pending");
      }

      var reason = row.querySelector(".reason-cell");
      if (reason && reason.textContent.trim() !== (data.rejection_reason || "—")) {
        reason.textContent = data.rejection_reason || "—";
      }
    }

    function poll() {
      fetch(apiUrl, {
        credentials: "same-origin",
        headers: { "Accept": "application/json" }
      })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (payload) {
          var byId = {};
          (payload.results || []).forEach(function (item) {
            byId[item.id] = item;
          });
          table.querySelectorAll("tbody tr[data-receipt-id]").forEach(function (row) {
            updateRow(row, byId[row.dataset.receiptId]);
          });
        })
        .catch(function () {
          /* Сетевые ошибки игнорируем: следующая попытка через интервал. */
        });
    }

    poll();
    setInterval(poll, POLL_INTERVAL);
  }

  /* --- Попап «Вы победитель» (показывается один раз на браузер) ------------ */
  function initWinModal(modal) {
    var DISMISS_KEY = "lucky_receipt_win_popup_dismissed";
    if (localStorage.getItem(DISMISS_KEY) === "1") return;

    var closeBtn = document.getElementById("win-modal-close");
    modal.hidden = false;

    function dismiss() {
      localStorage.setItem(DISMISS_KEY, "1");
      modal.hidden = true;
    }

    closeBtn.addEventListener("click", dismiss);
    modal.addEventListener("click", function (event) {
      if (event.target === modal) dismiss(); // клик по подложке
    });
  }
})();