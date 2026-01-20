# Ubuntu Deployment Guide (Nginx + Systemd)

This guide walks you through deploying your 3 Streamlit applications on an Ubuntu 24.04 LTS server.

**Target Architecture:**

* **App 1 (Profit Income)**: `http://YOUR_IP/profit` (Internal Port: 8501)
* **App 2 (Stock JST)**: `http://YOUR_IP/stock` (Internal Port: 8502)
* **App 3 (Shop Dashboard)**: `http://YOUR_IP/shop` (Internal Port: 8503)
* **Database**: PostgreSQL running via Docker (Port 5432)
* **Reverse Proxy**: Nginx handles the routing.
* **Process Manager**: Systemd keeps apps running.

---

## 1. System Preparation

Login to your server and update the system.

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential tools: Git, Python, Pip, Venv, Nginx
sudo apt install -y git python3-pip python3-venv nginx curl

# Install Docker & Docker Compose (for PostgreSQL)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# (Optional) Log out and log back in for docker group changes to take effect
```

---

## 2. Clone Repository

Clone your code to the `/var/www` or your home directory. We will use the home directory for simplicity.

```bash
cd ~
git clone <YOUR_GITHUB_REPO_URL> profit-income-project
cd profit-income-project
```

---

## 3. Database Setup (PostgreSQL)

We will use the `docker-compose.yml` included in your project to start the database.

```bash
# Start Postgres in daemon mode
docker compose up -d

# Verify it is running
docker compose ps
```

---

## 4. Python Environment Setup

Create a virtual environment and install dependencies.

```bash
# Create venv
python3 -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies (including gspread)
pip install -r requirements.txt
```

---

## 5. Secrets Configuration (CRITICAL)

Since credentials are gitignored, you must recreate them on the server.

### A. Profit Income (Database)

Edit/Create `profit_income/.streamlit/secrets.toml` (if you added DB config there) OR verify `profit_income/utils/db_service.py` defaults.

* *Note: Since Postgres is in Docker on the same machine, the default connection string `postgresql://admin:mos2025@localhost:5432/profit_income` usually works. If issues arise, use `admin:mos2025@172.17.0.1:5432`.*

### B. Stock JST Secrets

```bash
mkdir -p stock_jst/.streamlit
nano stock_jst/.streamlit/secrets.toml
```

* **Action**: Paste the content of your local `stock_jst/.streamlit/secrets.toml` here.
* *Save: Ctrl+O, Enter, Ctrl+X*

### C. Shop Dashboard Secrets

```bash
mkdir -p shop_dashboard/.streamlit
nano shop_dashboard/.streamlit/secrets.toml
```

* **Action**: Paste the content of your local `shop_dashboard/.streamlit/secrets.toml` here.
* *Save: Ctrl+O, Enter, Ctrl+X*

---

## 6. Systemd Service Setup

We will create 3 background services so your apps run automatically.

### Service 1: Profit Income

```bash
sudo nano /etc/systemd/system/profit_income.service
```

**Paste content:** (Replace `/root/mos_app` with your actual path if different)

```ini
[Unit]
Description=Streamlit Profit Income
After=network.target

[Service]
User=root
WorkingDirectory=/root/mos_app
ExecStart=/root/mos_app/venv/bin/streamlit run profit_income/streamlit_app.py --server.port 8501 --server.baseUrlPath=profit --server.headless=true
Restart=always

[Install]
WantedBy=multi-user.target
```

### Service 2: Stock JST

```bash
sudo nano /etc/systemd/system/stock_jst.service
```

**Paste content:**

```ini
[Unit]
Description=Streamlit Stock JST
After=network.target

[Service]
User=root
WorkingDirectory=/root/mos_app
ExecStart=/root/mos_app/venv/bin/streamlit run stock_jst/app.py --server.port 8502 --server.baseUrlPath=stock --server.headless=true
Restart=always

[Install]
WantedBy=multi-user.target
```

### Service 3: Shop Dashboard

```bash
sudo nano /etc/systemd/system/shop_dashboard.service
```

**Paste content:**

```ini
[Unit]
Description=Streamlit Shop Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/root/mos_app
ExecStart=/root/mos_app/venv/bin/streamlit run shop_dashboard/app.py --server.port 8503 --server.baseUrlPath=shop --server.headless=true
Restart=always

[Install]
WantedBy=multi-user.target
```

### Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable profit_income stock_jst shop_dashboard
sudo systemctl start profit_income stock_jst shop_dashboard

# Check Status
sudo systemctl status profit_income stock_jst shop_dashboard
```

---

## 7. Nginx Setup (Reverse Proxy)

Configure Nginx to route traffic to the correct ports.

```bash
sudo nano /etc/nginx/sites-available/streamlit_apps
```

**Paste content:**

```nginx
server {
    listen 80;
    server_name _;  # Or your domain name like example.com

    client_max_body_size 100M; # Allow large file uploads

    # App 1: Profit Income
    location /profit/ {
        proxy_pass http://localhost:8501/profit/;
        proxy_set_header        Host $host;
        proxy_set_header        X-Real-IP $remote_addr;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header        X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # App 2: Stock JST
    location /stock/ {
        proxy_pass http://localhost:8502/stock/;
        proxy_set_header        Host $host;
        proxy_set_header        X-Real-IP $remote_addr;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header        X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # App 3: Shop Dashboard
    location /shop/ {
        proxy_pass http://localhost:8503/shop/;
        proxy_set_header        Host $host;
        proxy_set_header        X-Real-IP $remote_addr;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header        X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable Site & Restart Nginx:**

```bash
sudo ln -s /etc/nginx/sites-available/streamlit_apps /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default page
sudo nginx -t  # Test config
sudo systemctl restart nginx
```

---

## 8. Final Verification

Open your browser and access:

1. `http://<YOUR_SERVER_IP>/profit`
2. `http://<YOUR_SERVER_IP>/stock`
3. `http://<YOUR_SERVER_IP>/shop`

> **Note on Permissions**:
> Ensure the `data` folder is writable by the user running the app (usually `ubuntu`).
>
> ```bash
> mkdir -p profit_income/data
> chown -R ubuntu:ubuntu profit_income/data
> ```
