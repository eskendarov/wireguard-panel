# WireGuard Panel

A small, self-hosted web UI for managing a native WireGuard server — add/remove
clients, generate QR codes, and see live traffic/handshake stats. No Docker,
no third-party dashboard — just a thin layer over the `wg` CLI.

Built because existing options (wg-easy, WGDashboard) either take over the
whole WireGuard config or ship more than needed. This does one thing: manage
peers on an existing native `wg0` interface.

## How it works

- **Live stats** (who's online, traffic, last handshake) come straight from
  `wg show wg0 dump` — no database needed for that part.
- **Client metadata** WireGuard itself has no concept of — names, enabled/
  disabled state, and each client's private key (needed to regenerate its QR
  code later) — is stored in `config/peers.json`, which never leaves the
  server.
- Every change rewrites `/etc/wireguard/wg0.conf` from `peers.json` and
  applies it live with `wg syncconf`, which doesn't drop unrelated active
  sessions.

## Requirements

- A Linux server with a native WireGuard interface already up
  (`wg-quick up wg0`), not managed by any other tool (wg-easy, etc. — those
  run their own WireGuard inside a container, this panel needs direct access
  to the host's `wg` command).
- Python 3.9+
- Root privileges (or sudo) — `wg` commands need `CAP_NET_ADMIN`.

## Setup

```bash
git clone <this-repo> /opt/vpn-panel
cd /opt/vpn-panel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # fill in SERVER_ENDPOINT, ADMIN_PASSWORD, etc.
```

Get your server's WireGuard public key for `.env`:
```bash
wg show wg0 public-key
```

Run it once to check everything works:
```bash
python -m app.main
# visit http://127.0.0.1:8787 (put it behind an SSH tunnel, don't expose directly)
```

### Run as a service

```bash
cp deploy/vpn-panel.service.example /etc/systemd/system/vpn-panel.service
# edit paths inside if you didn't clone to /opt/vpn-panel
systemctl daemon-reload
systemctl enable --now vpn-panel
```

Access it the same way as any other admin panel on this box — over an SSH
tunnel, never exposed directly to the internet:
```bash
ssh -L 8787:localhost:8787 your-server
# then open http://localhost:8787
```

## Security notes

- **`.env` and `config/peers.json` contain real secrets** (admin password,
  client private keys). Both are gitignored. Never commit them.
- This repo is public — anyone can read the code, but nobody can do anything
  with it without your server's actual `.env`/`peers.json`, which never leave
  the box.
- Client private keys are stored server-side so the QR code / `.conf` file
  can be regenerated later without re-provisioning the client. This is the
  same trade-off wg-easy and most panels make. If that's not acceptable for
  your threat model, don't use this pattern — hand clients their key once and
  never store it.

## Updating

```bash
cd /opt/vpn-panel
git pull
systemctl restart vpn-panel
```
