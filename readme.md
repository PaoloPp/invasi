# Invasi Web Application / Applicazione Web Invasi

## English

### Overview
The Invasi web application provides water-balance modelling tools (ModIn) for basins and river traverses. Authenticated users can load JSON datasets, generate reservoir balance visualisations, and run donor/receiver exchange simulations based on the ModIn logic implemented in the Flask blueprints.【F:invasi-app/blueprints/main/routes.py†L649-L775】【F:invasi-app/templates/dashboard.html†L1-L101】

### Prerequisites
- Python 3.10 or later
- A virtual environment tool such as `venv`
- System packages required by the libraries listed in `invasi-app/requirements.txt`
- (Optional) SMTP credentials if you plan to enable the email confirmation workflow referenced in `config.py`【F:invasi-app/config.py†L12-L16】

### Initial setup
1. Clone the repository and move into the project root.
2. Create and activate a virtual environment.
3. Install the backend dependencies: `pip install -r invasi-app/requirements.txt`.
4. Create the `invasi-app/instance/` directory if it does not yet exist; the SQLite database (`invasi.db`) and migration files will be stored there.【F:invasi-app/app.py†L22-L40】
5. Create `invasi-app/secret.py` with your mail credentials if you need outbound email:
   ```python
   MAIL_USERNAME = "your.address@example.com"
   MAIL_PASSWORD = "app-specific-password"
   ```
   These settings are imported by `config.py` to configure `flask-mail`.【F:invasi-app/config.py†L4-L16】

### Running the development server
From the `invasi-app/` directory, start the Flask application:
```bash
python app.py
```
The app factory initialises the database tables automatically on first launch and serves the site on `http://127.0.0.1:5000/` in debug mode.【F:invasi-app/app.py†L22-L47】

### Creating an administrator
New accounts are inactive by default. Use a Flask shell (or a short Python snippet) to seed an administrator capable of activating users:
```bash
python - <<'PY'
from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
app = create_app()
with app.app_context():
    admin = User(username="admin", password=generate_password_hash("change-me"), is_active=True, is_admin=True)
    db.session.add(admin)
    db.session.commit()
PY
```
Administrators can reach `/admin/dashboard` to review accounts and perform management tasks.【F:invasi-app/blueprints/admin/routes.py†L15-L66】

### Using the application
1. Navigate to `/auth/register` to create a user account, then ask an administrator to activate it (or update the `is_active` flag manually in the database).【F:invasi-app/blueprints/auth/routes.py†L24-L71】
2. After logging in at `/auth/login`, open the dashboard to select one of your saved basin JSON files and inspect cumulative balance tables and plots.【F:invasi-app/blueprints/main/routes.py†L649-L673】【F:invasi-app/templates/dashboard.html†L47-L118】
3. Use `/form` to capture basin inputs. You can load, delete, and save JSON datasets directly from the interface.【F:invasi-app/blueprints/main/routes.py†L674-L736】
4. Use `/form_traverse` to manage traverse flow datasets (`Pj`, `Pj(eco)`, `Pij`).【F:invasi-app/blueprints/main/routes.py†L736-L769】
5. Visit `/exchange` to configure donor/receiver exchanges. The route supports loading saved basins, applying ModIn criteria for surplus/deficit redistribution, and storing past exchanges for future comparison.【F:invasi-app/blueprints/main/routes.py†L775-L854】【F:invasi-app/utilities.py†L280-L352】
6. Generated plots are saved under `invasi-app/static/` as PNG files for download or PDF export.【F:invasi-app/utilities.py†L312-L347】

### Data persistence
- Basin and traverse datasets are stored per-user in the `JsonFile` and `JsonFileTraverse` tables, and can be retrieved through the dashboard selectors.【F:invasi-app/models.py†L14-L28】【F:invasi-app/utilities.py†L297-L310】
- Historical exchange runs are saved via the `PastExchange` model for later retrieval.【F:invasi-app/models.py†L30-L36】【F:invasi-app/utilities.py†L312-L352】
- All records live in `instance/invasi.db`, created automatically by SQLAlchemy migrations when the app starts.【F:invasi-app/app.py†L32-L39】

### Production notes
For production deployments, point the app to `ProductionConfig` when calling `create_app()`, configure a persistent database, and run the Flask app behind a production-ready WSGI server (e.g. Gunicorn or uWSGI).【F:invasi-app/app.py†L22-L50】【F:invasi-app/config.py†L18-L22】

---

## Italiano

### Panoramica
L'applicazione web Invasi mette a disposizione gli strumenti ModIn per il bilancio idrico di bacini e traverse. Gli utenti autenticati possono caricare dataset JSON, generare visualizzazioni dei volumi e simulare gli scambi tra donatori e riceventi secondo la logica ModIn implementata nei blueprint di Flask.【F:invasi-app/blueprints/main/routes.py†L649-L775】【F:invasi-app/templates/dashboard.html†L1-L101】

### Prerequisiti
- Python 3.10 o superiore
- Un gestore di ambienti virtuali (ad es. `venv`)
- Le librerie elencate in `invasi-app/requirements.txt`
- (Facoltativo) Credenziali SMTP per abilitare l'invio di email di conferma configurato in `config.py`【F:invasi-app/config.py†L12-L16】

### Configurazione iniziale
1. Clona il repository e spostati nella cartella principale del progetto.
2. Crea e attiva un ambiente virtuale.
3. Installa le dipendenze con `pip install -r invasi-app/requirements.txt`.
4. Crea la cartella `invasi-app/instance/` se non esiste: qui verranno salvati il database SQLite (`invasi.db`) e gli eventuali file di migrazione.【F:invasi-app/app.py†L22-L40】
5. Se devi inviare email, aggiungi `invasi-app/secret.py` con le tue credenziali:
   ```python
   MAIL_USERNAME = "tuo.indirizzo@example.com"
   MAIL_PASSWORD = "password-specifica"
   ```
   Questi valori vengono importati da `config.py` per configurare `flask-mail`.【F:invasi-app/config.py†L4-L16】

### Avvio del server di sviluppo
Dalla cartella `invasi-app/`, avvia Flask con:
```bash
python app.py
```
L'app factory crea automaticamente le tabelle del database al primo avvio e rende disponibile il sito su `http://127.0.0.1:5000/` in modalità debug.【F:invasi-app/app.py†L22-L47】

### Creazione di un amministratore
I nuovi account sono inattivi per impostazione predefinita. Utilizza una shell Flask (o un breve script Python) per creare un amministratore in grado di attivare gli utenti:
```bash
python - <<'PY'
from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
app = create_app()
with app.app_context():
    admin = User(username="admin", password=generate_password_hash("cambia-mi"), is_active=True, is_admin=True)
    db.session.add(admin)
    db.session.commit()
PY
```
Gli amministratori possono aprire `/admin/dashboard` per esaminare gli account e gestirli.【F:invasi-app/blueprints/admin/routes.py†L15-L66】

### Utilizzo dell'applicazione
1. Vai su `/auth/register` per creare un account e poi chiedi a un amministratore di attivarlo (oppure modifica manualmente il flag `is_active` nel database).【F:invasi-app/blueprints/auth/routes.py†L24-L71】
2. Dopo l'accesso tramite `/auth/login`, apri la dashboard per selezionare uno dei tuoi file JSON salvati e consultare tabelle e grafici dei bilanci cumulati.【F:invasi-app/blueprints/main/routes.py†L649-L673】【F:invasi-app/templates/dashboard.html†L47-L118】
3. Usa `/form` per inserire i dati del bacino; dal form puoi caricare, eliminare e salvare i dataset JSON.【F:invasi-app/blueprints/main/routes.py†L674-L736】
4. Usa `/form_traverse` per gestire i dataset relativi alle traverse (`Pj`, `Pj(eco)`, `Pij`).【F:invasi-app/blueprints/main/routes.py†L736-L769】
5. Visita `/exchange` per configurare gli scambi fra donatori e riceventi. La pagina permette di caricare i bacini salvati, applicare i criteri ModIn di ridistribuzione e archiviare gli scambi effettuati per confronti successivi.【F:invasi-app/blueprints/main/routes.py†L775-L854】【F:invasi-app/utilities.py†L280-L352】
6. I grafici generati vengono salvati in `invasi-app/static/` come file PNG scaricabili o esportabili in PDF.【F:invasi-app/utilities.py†L312-L347】

### Persistenza dei dati
- I dataset dei bacini e delle traverse sono memorizzati per utente nelle tabelle `JsonFile` e `JsonFileTraverse`, e sono disponibili nei menu a tendina della dashboard.【F:invasi-app/models.py†L14-L28】【F:invasi-app/utilities.py†L297-L310】
- Gli scambi storici sono salvati tramite il modello `PastExchange` per essere ricaricati in futuro.【F:invasi-app/models.py†L30-L36】【F:invasi-app/utilities.py†L312-L352】
- Tutti i record risiedono in `instance/invasi.db`, creato automaticamente da SQLAlchemy quando l'applicazione viene avviata.【F:invasi-app/app.py†L32-L39】

### Note per la produzione
Per la messa in produzione utilizza `ProductionConfig` durante la chiamata a `create_app()`, configura un database persistente e pubblica l'applicazione dietro un server WSGI adatto (ad es. Gunicorn o uWSGI).【F:invasi-app/app.py†L22-L50】【F:invasi-app/config.py†L18-L22】
