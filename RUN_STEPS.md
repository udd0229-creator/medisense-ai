# How to Run MediSense AI

## Requirements
- Python 3.10+ (tested on 3.12, Ubuntu)
- Internet only for the first `pip install`

## First-time setup

Run these from the project folder (the one containing `manage.py`):

```bash
cd /home/om/Desktop/UDAY/medisense

# 1. Install packages
#    (python3-venv was not installed on this machine, so no virtualenv is used)
pip install --break-system-packages -r requirements.txt

# 2. Create database tables
python manage.py migrate

# 3. Load demo data (36 medicines, 142 batches, 3473 sale rows) and users
python manage.py seed_data

# 4. Train the AI model
python manage.py train_model
```

Optional: to use a virtualenv instead, run `sudo apt install python3.12-venv`,
then `python3 -m venv venv && source venv/bin/activate` before step 1
(and drop `--break-system-packages`).

## Start the server

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.
Stop the server with `Ctrl+C`.

## Logins

| Username   | Password   | Role                                       |
|------------|------------|--------------------------------------------|
| admin      | admin@123  | Administrator (retrain model, `/admin/`)   |
| pharmacist | pharma@123 | Store staff                                |

## Later runs

Setup is done once. Afterwards only this is needed:

```bash
cd /home/om/Desktop/UDAY/medisense
python manage.py runserver
```

## Extras

- Run tests: `python3 manage.py test`
- Reset demo data: `python3 manage.py seed_data` (see README.md for options)
- Android app: see section 2a of `README.md` (`MediSense_AI.apk`)
