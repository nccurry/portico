# Security policy

## Supported versions

The latest release and the `main` branch receive security fixes.

## Report a vulnerability

Use the private security-advisory form in GitHub. Do not open a public issue for a vulnerability.

Do not include financial data, Google Sheet URLs, webhook URLs, or credentials in the report. Use synthetic examples when you describe the problem.

This app has no login screen. Source commands and container port publications
use loopback by default. Use `task run:lan` or `HOST_ADDRESS=0.0.0.0` only on a
network that you trust. Do not use public port forwarding without an
authenticated TLS reverse proxy.

The container runs as a non-root user with a read-only root filesystem. Compose
mounts the Streamlit secrets file as read-only. These controls do not add user
authentication to the dashboard.
