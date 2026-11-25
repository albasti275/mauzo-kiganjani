from django.urls import path
from .views import debt_list_and_repay, return_create, sale_create , close_business_day, daybook_view

app_name = "transactions"

urlpatterns = [
    path("sale/", sale_create, name="sale_create"),
    path("returns/", return_create, name="return_create"),
    path("debts/", debt_list_and_repay, name="debt_list"),
    path("close-day/", close_business_day, name="close_day"),
    path("daybooks/", daybook_view, name="daybook"),
]