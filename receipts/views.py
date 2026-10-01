from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .campaign import campaign_period_display
from .forms import DUPLICATE_MESSAGE, ReceiptForm, RegistrationForm
from .models import Receipt


def signup(request):
    """Регистрация нового участника акции: стандартная форма + обязательный e-mail."""
    if request.user.is_authenticated:
        return redirect("receipts:cabinet")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("receipts:cabinet")
    else:
        form = RegistrationForm()
    return render(request, "registration/signup.html", {"form": form})


def is_ajax(request) -> bool:
    """Запрос отправлен через fetch (с нашего фронтенда)?"""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def form_errors_to_flat(form) -> dict[str, str]:
    """Плоский словарь ошибок по полям: {field: "первое сообщение"}."""
    flat = {}
    for field, errors in form.errors.get_json_data().items():
        if field == "__all__":
            continue
        flat[field] = " ".join(err["message"] for err in errors)
    return flat


@login_required
def register_receipt(request):
    """Страница регистрации чека.

    Обычный POST → редирект на кабинет.
    Запрос через fetch → JSON с результатом (успех или ошибки по полям).
    """
    if request.method == "POST":
        form = ReceiptForm(request.POST, request.FILES)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.user = request.user
            receipt.status = Receipt.Status.PENDING  # новый чек всегда «на проверке»
            try:
                receipt.save()
            except IntegrityError:
                # Гонка: два одновременных запроса с одним чеком. Даём
                # понятное сообщение вместо 500.
                if is_ajax(request):
                    return JsonResponse(
                        {"ok": False, "non_field_errors": [DUPLICATE_MESSAGE]},
                        status=400,
                    )
                messages.error(request, DUPLICATE_MESSAGE)
                return redirect("receipts:register_receipt")
            if is_ajax(request):
                return JsonResponse({"ok": True, "receipt_id": receipt.id})
            messages.success(request, "Чек отправлен на проверку.")
            return redirect("receipts:cabinet")

        if is_ajax(request):
            return JsonResponse(
                {
                    "ok": False,
                    "errors": form_errors_to_flat(form),
                    "non_field_errors": [str(e) for e in form.non_field_errors()],
                },
                status=400,
            )
    else:
        form = ReceiptForm()

    start, end = campaign_period_display()
    return render(
        request,
        "receipts/register.html",
        {"form": form, "campaign_start": start, "campaign_end": end},
    )


@login_required
def cabinet(request):
    """Личный кабинет: свои чеки, от новых к старым, пагинация по 10."""
    receipts = request.user.receipts.all()
    paginator = Paginator(receipts, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    won_receipt = request.user.receipts.filter(status=Receipt.Status.WON).first()
    return render(
        request,
        "receipts/cabinet.html",
        {"page_obj": page_obj, "won_receipt": won_receipt},
    )


def rules(request):
    """Страница правил участия в акции."""
    return render(
        request,
        "receipts/rules.html",
        {"winners_count": settings.PROMO_WINNERS_COUNT},
    )