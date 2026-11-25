from django.urls import path
from .views import product_create, product_list

app_name = "inventory"

urlpatterns = [
    path("", product_list, name="product_list"),
    path("add/", product_create, name="product_create"),
]