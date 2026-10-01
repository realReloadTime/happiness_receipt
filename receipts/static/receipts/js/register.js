(function () {
  "use strict";

  var form = document.getElementById("receipt-form");
  if (!form) return;

  var messageBox = document.getElementById("form-message");
  var submitBtn = document.getElementById("submit-btn");
  var campaignStart = form.dataset.campaignStart || "";
  var campaignEnd = form.dataset.campaignEnd || "";
  var photoMaxMb = parseFloat(form.dataset.photoMaxMb || "10");
  var cabinetUrl = form.dataset.cabinetUrl || "/";

  function setFieldError(name, message) {
    var field = form.querySelector('[data-field="' + name + '"]');
    var box = form.querySelector('[data-error-for="' + name + '"]');
    if (field) field.classList.toggle("invalid", Boolean(message));
    if (box) box.textContent = message || "";
  }

  function clearAllErrors() {
    form.querySelectorAll(".field.invalid").forEach(function (f) {
      f.classList.remove("invalid");
    });
    form.querySelectorAll(".field-error").forEach(function (e) {
      e.textContent = "";
    });
  }

  /* --- Клиентская проверка форматов ДО отправки ----------------------------- */
  function validate() {
    var errors = {};
    var value;

    // ФН: ровно 16 цифр
    value = form.elements.fn.value.trim();
    if (!value) errors.fn = "Заполните ФН.";
    else if (!/^\d{16}$/.test(value)) errors.fn = "ФН должен содержать ровно 16 цифр.";

    // ФД: цифры, не более 10
    value = form.elements.fd.value.trim();
    if (!value) errors.fd = "Заполните ФД.";
    else if (!/^\d{1,10}$/.test(value)) errors.fd = "ФД должен содержать только цифры (до 10).";

    // ФП: цифры, не более 10
    value = form.elements.fp.value.trim();
    if (!value) errors.fp = "Заполните ФП.";
    else if (!/^\d{1,10}$/.test(value)) errors.fp = "ФП должен содержать только цифры (до 10).";

    // Дата и время покупки: формат YYYY-MM-DDTHH:MM + границы акции
    value = form.elements.purchased_at.value; // "YYYY-MM-DDTHH:MM"
    if (!value) {
      errors.purchased_at = "Укажите дату и время покупки.";
    } else if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
      errors.purchased_at = "Некорректный формат даты и времени.";
    } else if (campaignStart && value < campaignStart) {
      errors.purchased_at = "Покупка раньше начала акции.";
    } else if (campaignEnd && value > campaignEnd) {
      errors.purchased_at = "Покупка позже окончания акции.";
    }

    // Сумма: число >= 1000
    value = form.elements.amount.value.trim();
    var amount = parseFloat(value);
    if (!value) errors.amount = "Укажите сумму чека.";
    else if (isNaN(amount)) errors.amount = "Введите корректную сумму (например, 1890.50).";
    else if (amount < 1000) errors.amount = "Минимальная сумма чека — 1000 ₽.";

    // Фото (необязательно): формат и размер
    var fileInput = form.elements.photo;
    if (fileInput && fileInput.files && fileInput.files.length) {
      var file = fileInput.files[0];
      var allowed = ["image/jpeg", "image/png", "image/webp"];
      if (allowed.indexOf(file.type) === -1) {
        errors.photo = "Допустимы только изображения JPG, PNG или WebP.";
      } else if (file.size > photoMaxMb * 1024 * 1024) {
        errors.photo = "Файл больше " + photoMaxMb + " МБ.";
      }
    }

    return errors;
  }

  function showFormMessage(kind, html) {
    messageBox.hidden = false;
    messageBox.className = "alert alert-" + kind;
    messageBox.innerHTML = html;
  }

  /* --- Бонус: автозаполнение из строки QR-кода ------------------------------ */
  function formatDateFromQr(t) {
    // t = YYYYMMDDTHHMM → YYYY-MM-DDTHH:MM
    if (!/^\d{8}T\d{4}$/.test(t || "")) return null;
    return (
      t.slice(0, 4) + "-" + t.slice(4, 6) + "-" + t.slice(6, 8) +
      "T" + t.slice(9, 11) + ":" + t.slice(11, 13)
    );
  }

  var qrInput = form.elements.qr_line;
  qrInput.addEventListener("input", function () {
    var params = {};
    (this.value || "").trim().split("&").forEach(function (part) {
      var idx = part.indexOf("=");
      if (idx > 0) params[part.slice(0, idx).trim()] = part.slice(idx + 1).trim();
    });

    if (params.fn && /^\d{16}$/.test(params.fn) && !form.elements.fn.value) {
      form.elements.fn.value = params.fn;
    }
    if (params.i && /^\d{1,10}$/.test(params.i) && !form.elements.fd.value) {
      form.elements.fd.value = params.i;
    }
    if (params.fp && /^\d{1,10}$/.test(params.fp) && !form.elements.fp.value) {
      form.elements.fp.value = params.fp;
    }
    if (params.s && !form.elements.amount.value) {
      form.elements.amount.value = params.s;
    }
    var dt = formatDateFromQr(params.t);
    if (dt && !form.elements.purchased_at.value) {
      form.elements.purchased_at.value = dt;
    }
  });

  /* --- Отправка через fetch, ответ сервера — на странице -------------------- */
  function getCookie(name) {
    var match = document.cookie.match(
      new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)")
    );
    return match ? decodeURIComponent(match[1]) : "";
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearAllErrors();

    var errors = validate();
    Object.keys(errors).forEach(function (name) {
      setFieldError(name, errors[name]);
    });
    if (Object.keys(errors).length) {
      showFormMessage("error", "Проверьте выделенные поля.");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Отправка…";
    messageBox.hidden = true;

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data && result.data.ok) {
          showFormMessage(
            "success",
            "<div class=\"success-card\">" +
              "<span class=\"success-icon\">✓</span>" +
              "<b>Ваш чек загружен</b>" +
              "<p>Мы уже начали анализировать ваши покупки. Это займет всего пару секунд.</p>" +
              "<a href=\"" + cabinetUrl + "\" class=\"btn btn-primary\">На главную</a>" +
            "</div>"
          );
          form.reset();
        } else {
          var data = result.data || {};
          Object.keys(data.errors || {}).forEach(function (name) {
            setFieldError(name, data.errors[name]);
          });
          var nonField = (data.non_field_errors || []).join(" ");
          showFormMessage(
            "error",
            nonField || "Не удалось зарегистрировать чек. Проверьте выделенные поля."
          );
        }
      })
      .catch(function () {
        showFormMessage("error", "Произошла ошибка сети. Попробуйте ещё раз.");
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = "Отправить на проверку";
      });
  });
})();