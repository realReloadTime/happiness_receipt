from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Receipt
from .serializers import ReceiptSerializer


class ReceiptListAPIView(generics.ListAPIView):
    """GET /api/receipts/ — чеки текущего пользователя в JSON.

    Безопасность: выборка всегда жёстко фильтруется по request.user.
    Любые посторонние параметры запроса (user_id, id и т.п.) игнорируются
    и не могут повлиять на результат — чужие чеки не возвращаются
    ни при каких параметрах. Поддерживается только пагинация (?page=N).
    """

    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Receipt.objects.filter(user=self.request.user).order_by("-created_at")