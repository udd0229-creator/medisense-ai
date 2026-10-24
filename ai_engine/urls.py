from django.urls import path

from . import views as v

urlpatterns = [
    path("expiry-risk/", v.expiry_risk, name="expiry_risk"),
    path("expiry-risk.csv", v.expiry_risk_csv, name="expiry_risk_csv"),
    path("forecast/", v.forecast, name="forecast"),
    path("reorder/", v.reorder, name="reorder"),
    path("reorder.csv", v.reorder_csv, name="reorder_csv"),
    path("model/", v.model_info, name="model_info"),
    path("model/retrain/", v.retrain, name="retrain"),
]
