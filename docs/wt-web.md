# set-web Dashboard

set-web is the browser-based dashboard for set-core. It provides real-time visibility into orchestration runs, worktree status, change progress, and agent activity.

Built with FastAPI (backend) + React/TypeScript (frontend), served by uvicorn.

## Quick Start

Start the dashboard manually:

```bash
set-orch-core serve --port 7400
```

Open http://localhost:7400/ in your browser.

To run it as a background service, use the installer (see below).

## Automated Install

The `set-web-install` command sets up set-web as a systemd user service:

```bash
set-web-install
```

This will:
1. Copy the service template to `~/.config/systemd/user/set-web.service`
2. Enable and start the service
3. Verify the dashboard is responding
4. Ask if you want to enable Tailscale HTTPS remote access

### Options

| Flag | Description |
|------|-------------|
| `--port <N>` | Listen on a custom port (default: 7400) |
| `--tailscale` | Enable Tailscale HTTPS without prompting |
| `--uninstall` | Stop and remove the service |
| `--help` | Show help |

### Examples

```bash
# Install with defaults (port 7400, prompt for Tailscale)
set-web-install

# Install on custom port
set-web-install --port 8000

# Install with Tailscale HTTPS (non-interactive)
set-web-install --tailscale

# Remove everything
set-web-install --uninstall
```

## Manual Setup

### Systemd Service

1. Copy the service template:

```bash
mkdir -p ~/.config/systemd/user
cp templates/systemd/set-web.service ~/.config/systemd/user/set-web.service
```

2. (Optional) Edit the service file to change the port:

```bash
# In ~/.config/systemd/user/set-web.service, change:
# ExecStart=%h/.local/bin/set-orch-core serve --port 7400
# to your desired port
```

3. Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable set-web
systemctl --user start set-web
```

4. Verify:

```bash
systemctl --user status set-web
curl -s http://localhost:7400/ | head -1
```

### Tailscale HTTPS (Remote Access)

Tailscale provides secure remote access via its WireGuard-based VPN. Only devices registered in your tailnet can access the dashboard.

**Prerequisites:**
- Tailscale installed and connected (`tailscale status`)
- HTTPS enabled in your tailnet admin (Admin Console → DNS → HTTPS Certificates)

**Setup:**

1. Configure Tailscale to proxy HTTPS traffic to set-web:

```bash
sudo tailscale serve --bg --https 443 http://localhost:7400
```

2. Find your Tailscale hostname:

```bash
tailscale status --json | jq -r '.Self.DNSName' | sed 's/\.$//'
```

3. Access from any device on your tailnet:

```
https://<your-hostname>.tailXXXXXX.ts.net/
```

**Security note:** Tailscale uses Let's Encrypt certificates, which means the hostname appears in Certificate Transparency logs. This is not a security concern — the service is only reachable from within the tailnet (device must be registered).

**To remove Tailscale serve:**

```bash
sudo tailscale serve --https 443 off
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WT_WEB_PORT` | `7400` | Port for the set-web server |
| `WT_TAILSCALE_HOSTNAME` | _(auto-detected)_ | Override the Tailscale hostname in notifications |
| `SONIOX_API_KEY` | _(none)_ | API key for voice input (optional) |
| `RESEND_API_KEY` | _(none)_ | Resend API key for email notifications |
| `RESEND_FROM` | _(none)_ | Sender email for notifications |
| `RESEND_TO` | _(none)_ | Recipient email for notifications |

### .env File

Environment variables can be set in the `.env` file at the set-core root:

```bash
WT_WEB_PORT=7400
WT_TAILSCALE_HOSTNAME=my-machine.tailXXXXXX.ts.net
RESEND_API_KEY=re_xxxxx
RESEND_FROM=noreply@example.com
RESEND_TO=you@example.com
```

### Service File

The systemd service template is at `templates/systemd/set-web.service`. The installed copy lives at `~/.config/systemd/user/set-web.service`.

Key settings:
- `Restart=always` — auto-restart on crash
- `RestartSec=5` — wait 5s between restarts
- `PYTHONPATH` — must point to `set-core/lib`

## Troubleshooting

### Service won't start

Check logs:

```bash
journalctl --user -u set-web -f
```

Common causes:
- **Python not found**: The service uses `set-orch-core` which must be in PATH. Verify: `which set-orch-core`
- **Port conflict**: Another process is using port 7400. Check: `ss -tlnp | grep 7400`
- **PYTHONPATH wrong**: The service needs `set-core/lib` on PYTHONPATH. Check the `Environment=` line in the service file

### Dashboard loads but shows no data

- Verify a project is registered: `set-config list`
- Check the API directly: `curl http://localhost:7400/api/projects`

### Tailscale HTTPS not working

- Verify Tailscale is connected: `tailscale status`
- Verify HTTPS is enabled in tailnet admin console (DNS → HTTPS Certificates)
- Check serve status: `tailscale serve status`
- Try accessing via Tailscale IP directly: `curl http://100.x.x.x:7400/`

### Tailscale cert fails with 500 Internal Server Error

The `tailscale cert` command may fail with `500 Internal Server Error: SetDNS ... failed to create DNS record`. This is a Tailscale coordination server issue that is resolved by restarting the tailscaled daemon:

```bash
sudo systemctl restart tailscaled
sleep 5
tailscale cert <your-hostname>.tailXXXXXX.ts.net
```

**Prerequisites for Tailscale HTTPS:**

1. **Enable operator mode** (once, allows `tailscale serve/cert` without sudo):
   ```bash
   sudo tailscale set --operator=$USER
   ```

2. **Enable HTTPS certificates** in Admin Console → DNS → HTTPS Certificates

The `set-web-install --tailscale` command handles all of this automatically, including the tailscaled restart retry.

### Service keeps restarting

Check for crash loops:

```bash
journalctl --user -u set-web --since "5 minutes ago"
```

Common causes:
- Missing dependencies (pip packages)
- Frontend not built (`web/dist/` directory missing)
- Database or config file corruption
