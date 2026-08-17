# One-time VM setup

Run these **once** on the GCP VM. After this, every push to `staging` deploys
automatically via `.github/workflows/deploy-staging.yml`.

Assumes Ubuntu/Debian. Replace `YOUR_VM_IP` and `youruser` throughout.

---

## 1. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Run docker without sudo. The CI deploy relies on this - it does not use sudo.
sudo usermod -aG docker $USER
newgrp docker      # or log out and back in

# Start on boot, so the stack returns after a VM restart
sudo systemctl enable docker
```

Verify: `docker compose version` should print v2.x.

---

## 2. Clone the repo

The repo is private, so this first clone needs your PAT. Create one at
GitHub → Settings → Developer settings → Personal access tokens, with **repo**
scope (classic) or **Contents: read** (fine-grained).

Clone into your home directory, alongside any other projects on the box. Home
is the right place for this rather than /opt: compose creates `postgres-data/`,
`cache/` and `logs/` relative to the project root, and those stay plainly owned
by you here with no sudo or chown needed.

```bash
cd ~
git clone -b staging \
  https://YOUR_PAT@github.com/TahaMoiz-4/logistics-management.git \
  nightingale
cd ~/nightingale

# Remove the token from the stored remote URL - `git clone` writes it into
# .git/config in plaintext, and the workflow supplies its own token per pull.
git remote set-url origin https://github.com/TahaMoiz-4/logistics-management.git
```

`-b staging` checks out the staging branch on clone. It does NOT limit what is
fetched - every branch still comes down; you just start on the right one, so the
first manual build uses the same code the pipeline will.

Whatever path you choose, it must match the `VM_APP_DIR` GitHub secret in
step 6. That secret is the only place this path appears.

---

## 3. Create `.env` (never in git)

```bash
cd ~/nightingale
cp .env.example .env
nano .env
```

Set these three; leave the rest at their defaults:

```bash
# Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=<paste the generated value>

FIREBASE_PROJECT_ID=nightingale-d1c23

# Your VM's external IP *with the published port*, no trailing slash. Origins
# are matched as exact strings - http://1.2.3.4:8030/ will NOT match
# http://1.2.3.4:8030
CORS_ORIGINS=http://YOUR_VM_IP:8030

# Host port for the console. The demo VM is shared: a host nginx owns :80,
# :8080 and :8099, and other projects sit on 8001-8020 and 8090. Change this
# only if 8030 is taken too - check with: sudo ss -tlnp | grep ':80'
WEB_PORT=8030
```

`DATABASE_URL` and `REDIS_URL` stay as-is: docker-compose overrides them with
container hostnames, and real env vars outrank the env file in pydantic-settings.

```bash
chmod 600 .env
```

---

## 4. Place the Firebase credential (never in git)

`src/secrets/` is gitignored, so the clone did not create it.

```bash
mkdir -p ~/nightingale/src/secrets
```

Then from **your laptop**, not the VM:

```bash
gcloud compute scp \
  src/secrets/nightingale-d1c23-firebase-adminsdk-fbsvc-98cd4eb584.json \
  YOUR_VM_NAME:nightingale/src/secrets/ --zone=YOUR_ZONE
```

Back on the VM:

```bash
chmod 600 ~/nightingale/src/secrets/*.json
```

Without this file the app still runs - FCM push falls back to stub mode
(logs intent, sends nothing). The deploy warns but does not fail.

---

## 5. SSH key for GitHub Actions

Generate the keypair **on your laptop**:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/nightingale_deploy -N "" -C "github-actions-deploy"
cat ~/.ssh/nightingale_deploy.pub
```

Add that public key to the VM (`~/.ssh/authorized_keys` for the deploy user):

```bash
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE
echo "<paste the .pub contents>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Test from your laptop before touching GitHub - if this fails, the pipeline will too:

```bash
ssh -i ~/.ssh/nightingale_deploy youruser@YOUR_VM_IP 'docker compose version'
```

---

## 6. GitHub repo secrets

Repo → Settings → Secrets and variables → Actions → **New repository secret**.
Five secrets, names must match exactly:

| Name | Value |
|---|---|
| `VM_HOST` | VM external IP, e.g. `34.16.22.101` |
| `VM_USER` | SSH username on the VM (`whoami` output) |
| `VM_APP_DIR` | `/home/taha/nightingale` (absolute path, no `~`) |
| `VM_SSH_PRIVATE_KEY` | Full contents of `~/.ssh/nightingale_deploy` (the file **without** `.pub`), including the BEGIN/END lines |
| `GH_PAT` | The personal access token from step 2 |

---

## 7. Open port 80 in the GCP firewall

```bash
gcloud compute firewall-rules create allow-nightingale-http \
  --allow=tcp:8030 \
  --source-ranges=0.0.0.0/0 \
  --description="Nightingale demo console"
```

`8030` (WEB_PORT) is the only port that needs opening - it is the stack's sole
published port. The backend, Postgres and Redis publish nothing to the host;
they are reachable only inside the Docker network.

To reach the database, get a shell on it rather than publishing a port:

```bash
docker compose exec postgres psql -U user -d LMS
```

---

## 8. First deploy

```bash
cd ~/nightingale
docker compose up -d --build      # ~5-10 min for the first build
docker compose ps                 # all four should reach (healthy)
```

Seed the demo data **once** (this wipes and reloads tenant data, so never
automate it):

```bash
docker compose exec backend python -m src.utils.scripts.seed_demo_dataset
```

Open `http://YOUR_VM_IP:8030` - log in as `admin1` / `password`.

---

## From here on

```bash
git checkout staging
git merge development
git push origin staging     # -> Actions builds on the VM and redeploys
```

Watch it in the repo's **Actions** tab. Container logs stream into the run
output, including when a deploy fails.

---

## Notes

- **HTTP only.** No domain means no certificate; browsers show "Not secure".
  Once you have a DNS name, the host nginx already on :80 can proxy to
  `127.0.0.1:8030` and terminate TLS - that is how the other projects on this
  VM are fronted. Then `CORS_ORIGINS` becomes `https://your.domain`.
- **Shared VM.** Roughly a dozen projects run here. Before changing any host
  port, check what is free: `sudo ss -tlnp | grep ':80'`
- **Backups.** Postgres data lives in `~/nightingale/postgres-data`. Migrations
  run automatically on every deploy, so before a schema-changing release:
  `docker compose exec postgres pg_dump -U user LMS > ~/backup-$(date +%F).sql`
- **Changing `.env`** does not take effect until containers restart:
  `docker compose up -d --force-recreate backend`
