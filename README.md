# MediSense AI
### AI-Based Medicine Expiry Risk & Inventory Optimization System
BCA Final Year Project · Django + SQLite + scikit-learn

MediSense AI is a pharmacy inventory web app that:

- predicts the **expiry risk** of every batch in stock with a Random Forest model (High / Medium / Low, plus expected loss in ₹)
- **forecasts demand** for the next 30 days per medicine (Linear Regression with trend and weekday, checked against a moving average)
- computes **safety stock, reorder point and EOQ**, capped so you never buy more than can be sold before expiry
- sells stock using **FEFO** (First-Expiry-First-Out) automatically and blocks expired stock
- shows everything on a dashboard with charts, and exports CSV reports

---

## 1. Requirements
- Python 3.10 or newer (check with `python --version`)
- Any OS: Windows 10/11, Ubuntu, macOS
- No internet needed after installing packages (Bootstrap and Chart.js are bundled in `static/vendor`)

## 2. Setup (first time)

```bash
# 1. open a terminal in the project folder (the one with manage.py)
cd medisense

# 2. create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / macOS

# 3. install packages
pip install -r requirements.txt

# 4. create the database tables
python manage.py migrate

# 5. load demo data (36 medicines, ~150 batches, 120 days of sales) and users
python manage.py seed_data

# 6. train the AI model (prints accuracy, confusion matrix, feature importance)
python manage.py train_model

# 7. start the server
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

| Username   | Password    | Role                                         |
|------------|-------------|----------------------------------------------|
| admin      | admin@123   | Administrator (can retrain model, /admin/)   |
| pharmacist | pharma@123  | Store staff                                  |

Run the automated tests: `python manage.py test` (21 test cases).

## 2a. Android app (MediSense_AI.apk)

The APK is a native Android app (Android 7.0 or newer) that opens the MediSense server.
The AI and database still run in Django on your laptop (or on a hosted server); the phone is the screen.

1. Start the server so other devices can reach it:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
2. Find the laptop's IP address: Windows `ipconfig` → "IPv4 Address" (e.g. 192.168.1.5);
   Linux/macOS `ip addr` or `ifconfig`.
3. Connect the phone to the same Wi‑Fi, or turn on the phone's hotspot and connect the laptop to it.
4. Copy `MediSense_AI.apk` to the phone, open it, and allow "Install unknown apps" when asked.
   Play Protect may warn because the app is not from the Play Store: tap "Install anyway".
5. Open MediSense AI, enter `http://<laptop-IP>:8000` and tap Connect. Log in as pharmacist / pharma@123.

If it cannot connect: allow Python through Windows Firewall for Private networks, and check that
`http://<laptop-IP>:8000` opens in the phone's Chrome. Use the app menu (⋮) → "Change server" to fix the address.
CSV reports are saved to the phone's Downloads folder.

Rebuilding the APK: the source is in `android/` (one Java file, manifest, icons). On Ubuntu:
`sudo apt install android-sdk-platform-23 aapt dalvik-exchange zipalign apksigner default-jdk`
then `./android/build.sh`. You can also open the folder in Android Studio.

## 3. Project structure

```
medisense/
├── manage.py
├── requirements.txt
├── medisense/              # project settings and root URLs
│   ├── settings.py         # MEDISENSE config: ordering cost, holding rate, risk thresholds
│   └── urls.py
├── inventory/              # app 1: stock, sales, suppliers
│   ├── models.py           # Category, Supplier, Medicine, Batch, Sale
│   ├── services.py         # sell_fefo(): FEFO dispensing in a DB transaction
│   ├── forms.py            # validation (expiry after mfg date, etc.)
│   ├── views.py            # dashboard, CRUD screens, sales, CSV stock report
│   ├── tests.py
│   └── management/commands/seed_data.py
├── ai_engine/              # app 2: AI and optimisation
│   ├── features.py         # feature engineering (days of stock, coverage ratio...)
│   ├── training_data.py    # simulated historical batch dataset
│   ├── risk_model.py       # Random Forest training, prediction, recommendations
│   ├── forecast.py         # demand forecasting
│   ├── reorder.py          # safety stock, ROP, EOQ, shelf-life cap
│   ├── views.py            # expiry risk, forecast, reorder, model pages
│   ├── tests.py
│   ├── ml_models/          # saved model (.joblib) and metrics (.json)
│   └── management/commands/train_model.py
├── dataset/expiry_training_data.csv   # generated when the model is trained
├── templates/              # HTML (Bootstrap 5)
└── static/                 # CSS + bundled Bootstrap, icons, Chart.js
```

## 4. Demo script for the viva (5 minutes)
1. Log in as **pharmacist** → Dashboard: show stock value, high-risk batches, potential loss, charts.
2. **Expiry Risk**: point out that *Paracetamol 500mg* expires in ~25 days but is **Low** risk (it sells ~20/day), while *Aceclofenac 100mg* expires in ~4 months but is **High** risk (294 units, sells < 1/day). This is the key idea: risk depends on sales speed, not only on the date.
3. **Demand Forecast**: pick *Cetirizine 10mg*, show the rising seasonal trend and the forecast.
4. **Reorder Planner**: explain ROP, EOQ and the shelf-life cap; download the purchase order CSV.
5. **New Sale**: sell 70 units of Paracetamol 500mg and show the message — it takes units from the earliest-expiring batch first, then the next (FEFO).
6. **AI Model**: show accuracy/recall, confusion matrix, feature importance and the comparison with Logistic Regression and Decision Tree. Log in as admin to press **Retrain**.

## 5. Configuration
Edit `MEDISENSE` in `medisense/settings.py`:

| Key | Meaning | Default |
|---|---|---|
| ORDERING_COST | ₹ per purchase order (S) | 200 |
| HOLDING_RATE | yearly holding cost as fraction of unit cost (H) | 0.20 |
| SERVICE_LEVEL_Z | z for service level (1.65 = 95%) | 1.65 |
| HIGH_RISK / MEDIUM_RISK | probability thresholds | 0.70 / 0.40 |
| SHELF_LIFE_USE_FRACTION | max share of shelf life to cover with one order | 0.8 |

## 6. Notes
- `seed_data` deletes existing inventory data and reloads the demo set. Do not run it on real data.
- The training dataset is **simulated** from realistic pharmacy patterns (explained in `ai_engine/training_data.py`). With real history, replace `simulate_dataset()` with records of past batches.
- To switch to MySQL, change `DATABASES` in settings and `pip install mysqlclient`.
