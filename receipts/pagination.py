from rest_framework.pagination import PageNumberPagination


class ReceiptPagination(PageNumberPagination):
    """Пагинация для /api/receipts/: фиксированные 10 элементов на страницу."""

    page_size = 10
    page_size_query_param = None
    max_page_size = 10