# Hostinger VPS Multi-Project Deployment Guide

This guide sets up two different backend projects on one VPS:

- `api.powerfrill.com` -> Project A (`wezu-backend-laxman`) on `127.0.0.1:18081`
- `api1.powerfrill.com` -> Project B on `127.0.0.1:18082`

Use host `nginx.service` as the only public reverse proxy on ports `80/443`.

## 1. DNS in Hostinger hPanel

In `Domains -> powerfrill.com -> DNS / Nameservers`, set:

- `A` record: `api` -> `<YOUR_VPS_PUBLIC_IP>`
- `A` record: `api1` -> `<YOUR_VPS_PUBLIC_IP>`

Check propagation:

```bash
dig +short api.powerfrill.com A
dig +short api1.powerfrill.com A
```

## 2. Deploy Project A (this repo)

This repository now supports host port mapping through:

- `API_BIND_HOST` (default `127.0.0.1`)
- `API_HOST_PORT` (default `18081`)

Commands:

```bash
set -euo pipefail
cd /root/wezu-backend-laxman

git fetch origin
git checkout main
git reset --hard origin/main

test -s .env.production || cp .env.example .env.production
grep -q '^API_BIND_HOST=' .env.production || echo 'API_BIND_HOST=127.0.0.1' >> .env.production
grep -q '^API_HOST_PORT=' .env.production || echo 'API_HOST_PORT=18081' >> .env.production

docker compose down --remove-orphans
docker compose build api
docker compose up -d db redis api
docker compose ps -a
curl -fsS http://127.0.0.1:18081/health
```

## 3. Deploy Project B on a different local port

In Project B directory, ensure compose publishes to another localhost port:

```yaml
services:
  api:
    ports:
      - "127.0.0.1:18082:8000"
```

Then deploy Project B and verify:

```bash
curl -fsS http://127.0.0.1:18082/health
```

## 4. Configure host nginx for both domains

Create `/etc/nginx/sites-available/api.powerfrill.com.conf`:

```nginx
server {
    listen 80;
    server_name api.powerfrill.com;

    location / {
        proxy_pass http://127.0.0.1:18081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
```

Create `/etc/nginx/sites-available/api1.powerfrill.com.conf`:

```nginx
server {
    listen 80;
    server_name api1.powerfrill.com;

    location / {
        proxy_pass http://127.0.0.1:18082;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
```

Enable and reload:

```bash
sudo ln -sfn /etc/nginx/sites-available/api.powerfrill.com.conf /etc/nginx/sites-enabled/api.powerfrill.com.conf
sudo ln -sfn /etc/nginx/sites-available/api1.powerfrill.com.conf /etc/nginx/sites-enabled/api1.powerfrill.com.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 5. Remove conflicting duplicate server blocks

Before SSL, ensure each subdomain appears once:

```bash
sudo nginx -T | grep -n "server_name .*powerfrill.com"
```

If the same domain appears in multiple active files under `/etc/nginx/sites-enabled`, disable duplicates and reload.

## 6. Issue SSL certificates

```bash
sudo certbot --nginx -d api.powerfrill.com -d api1.powerfrill.com
```

## 7. Final verification

```bash
curl -fsS https://api.powerfrill.com/health
curl -fsS https://api1.powerfrill.com/health
curl -I https://api.powerfrill.com/docs
curl -I https://api1.powerfrill.com/docs
```

## 8. Safe rollback

If a new release fails:

```bash
cd /root/wezu-backend-laxman
docker compose logs --tail=200 api
docker compose down
git reset --hard <last-known-good-commit>
docker compose up -d db redis api
```
