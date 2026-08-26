# Linux container deployment

The container is the supported deployment method. It runs as a non-root user,
uses a read-only filesystem, and includes a health check.

## Requirements

- A Linux host with Docker Engine
- Docker Compose version 2
- Git, for source-based builds

If you want persistent Compose overrides, copy the environment example:

```console
cp .env.example .env
```

The default timezone is `Etc/UTC`. If you use the notifier, set `TZ` to your
local time zone.

## Run the demo

Build and start the demo:

```console
docker compose --profile demo up --build --detach demo
```

Open <http://127.0.0.1:8501>. The demo does not mount secrets or contact Google
Sheets.

Examine the service and health status:

```console
docker compose --profile demo ps
docker compose --profile demo logs --follow demo
```

Stop the service:

```console
docker compose --profile demo down
```

## Run with Google Sheets

Copy the secrets template and add the four link-readable tab URLs:

```console
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
chmod 600 .streamlit/secrets.toml
```

Validate the workbook:

```console
docker compose build live
docker compose --profile live run --rm --no-deps live python -m scripts.doctor
```

Start the live service:

```console
docker compose --profile live up --build --detach live
```

Compose mounts `.streamlit/secrets.toml` as a read-only file. The command stops
with an error if the file does not exist. Compose also mounts `config/` as
read-only. You can add ignored settings in `config/local.toml`.

## Network access

The default port publication is `127.0.0.1:8501:8501`. This publication accepts
connections from the Linux host only.

For a trusted LAN, publish on all host interfaces:

```console
HOST_ADDRESS=0.0.0.0 docker compose --profile live up --detach live
```

WARNING: The app has no login screen. Do not use public port forwarding.

For private VPN access, set `HOST_ADDRESS` to the host VPN address. A host reverse
proxy can connect to the default loopback address. The reverse proxy must provide
authentication and TLS before it accepts public traffic.

Use `PORT` to change the host port:

```console
PORT=8601 docker compose --profile live up --detach live
```

## Update the service

Get the new source and rebuild the image:

```console
git pull --ff-only
docker compose --profile live up --build --detach live
```

Compose replaces the container and preserves the host secrets file. The dashboard
does not store application data in the container.

## Stop and remove containers

```console
docker compose --profile demo --profile live down
```

This command preserves the notifier state volume and local secrets.

## Optional Discord notifier

The image includes the existing one-shot notifier. It does not install a schedule.
See [discord-notifier.md](discord-notifier.md) for commands and state behavior.

## Health check

Docker examines `http://127.0.0.1:8501/_stcore/health` inside the container. This
endpoint does not return financial data.

The image uses Docker Official Python and supports the architectures provided by
that base image. Automated `linux/amd64` and `linux/arm64` release builds are part
of the release-automation phase.
