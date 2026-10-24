"""python manage.py train_model  -> trains and saves the expiry risk model"""
from django.core.management.base import BaseCommand

from ai_engine.risk_model import train_model


class Command(BaseCommand):
    help = "Train the Random Forest expiry-risk model and print evaluation metrics"

    def add_arguments(self, parser):
        parser.add_argument("--samples", type=int, default=6000)

    def handle(self, *args, **opts):
        m = train_model(n_samples=opts["samples"])
        self.stdout.write(f"Trained on {m['n_train']} rows, tested on {m['n_test']} rows")
        for name, s in m["comparison"].items():
            self.stdout.write(f"  {name:20s} acc={s['accuracy']:.3f} prec={s['precision']:.3f} "
                              f"rec={s['recall']:.3f} f1={s['f1']:.3f} auc={s['roc_auc']:.3f}")
        self.stdout.write(f"Confusion matrix: {m['confusion_matrix']}")
        self.stdout.write("Feature importance:")
        for f in m["feature_importance"]:
            self.stdout.write(f"  {f['feature']:16s} {f['importance']:.3f}")
        self.stdout.write(self.style.SUCCESS("Model saved to ai_engine/ml_models/"))
