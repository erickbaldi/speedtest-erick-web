# Speedtest Web Monitor

Un'applicazione web autonoma, leggera e moderna per il monitoraggio della velocità di rete (Download, Upload, Ping), sviluppata in **Python (Flask)**, servita da **Gunicorn** e integrata dietro reverse proxy **NGINX**.

L'interfaccia grafica è sviluppata in **SVG puro** (senza dipendenze CDN esterne), con un selettore dinamico dei server, storico su **SQLite** e meccanismo di **Cache & Lock** per prevenire l'uso improprio della banda.

---

## 📁 Struttura del Repository

```text
speedtest-web/
├── .gitignore
├── .gitattributes
├── README.md
├── requirements.txt
├── speedtest_app.py
├── templates/
│   └── index.html
└── deploy/
    ├── speedtest-erick.conf
    └── speedtest-web.service
```

---

## 🛠️ Requisiti

* Sistema Operativo: Linux (Debian, Ubuntu, Raspberry Pi OS, ecc.)
* Python 3.8+ con modulo `venv`
* NGINX (configurato in HTTPS)
* SQLite3

---

## 🚀 Guida all'Installazione

### 1. Clonare il repository

Clona il repository nella tua home directory:

```bash
cd ~
git clone https://github.com/TUO_UTENTE/speedtest-web.git
cd speedtest-web
```

### 2. Creare l'ambiente virtuale e installare le dipendenze

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Configurazione dei Servizi

### 3. Configurare il Servizio Utente Systemd

Crea la directory delle unità utente (se non esiste già) e copia il file di servizio fornito:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/speedtest-web.service ~/.config/systemd/user/
```

> **Nota:** Verifica che all'interno di `~/.config/systemd/user/speedtest-web.service` il percorso dell'eseguibile Gunicorn e della cartella coincida con il tuo utente Linux (sostituisci `/home/erick` con il tuo percorso reale se diverso).

Abilita la persistenza dell'utente e avvia il servizio:

```bash
# Permette all'utente di mantenere i servizi attivi anche disconnesso
sudo loginctl enable-linger $USER

# Ricarica systemd ed esegui il servizio
systemctl --user daemon-reload
systemctl --user enable speedtest-web.service
systemctl --user restart speedtest-web.service
```

Verifica lo stato del servizio:
```bash
systemctl --user status speedtest-web.service
```

### 4. Configurare NGINX Reverse Proxy

Apri il file di configurazione del tuo sito su NGINX (es. `/etc/nginx/sites-available/subsonic` o `/etc/nginx/sites-available/default`) e aggiungi il blocco contenuto in `deploy/nginx.conf`:

```nginx
# Redirect per garantire lo slash finale
location = /speedtest-erick {
    return 301 https://$host/speedtest-erick/;
}

# Proxy pass verso Gunicorn (porta 7878)
location /speedtest-erick/ {
    proxy_pass http://127.0.0.1:7878/;

    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_set_header X-Forwarded-Prefix /speedtest-erick;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_connect_timeout 30s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
}
```

Verifica la configurazione e ricarica NGINX:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 📡 API Endpoints

| Endpoint | Metodo | Descrizione |
|---|---|---|
| `/` | `GET` | Pagina web principale (UI Dashboard) |
| `/api/servers` | `GET` | Restituisce la lista dei server vicini disponibili |
| `/api/history` | `GET` | Restituisce le ultime 15 misurazioni e l'ultimo risultato in cache |
| `/api/speedtest` | `GET / POST` | Esegue il test di velocità (`force=1` per ignorare la cache, `server_id` facoltativo) |

---

## 📄 Licenza

Questo progetto è distribuito sotto licenza **MIT**. Libero per uso personale e commerciale.
