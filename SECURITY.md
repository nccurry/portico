# Security policy

## Supported versions

The latest release and the `main` branch receive security fixes.

## Report a vulnerability

Use the private security-advisory form in GitHub. Do not open a public issue for a vulnerability.

Do not include financial data, Google Sheet URLs, webhook URLs, or credentials in the report. Use synthetic examples when you describe the problem.

This app has no login screen. Source commands and container examples use
loopback by default. Use `task run:lan` or publish the container on all host
interfaces only on a network that you trust. Do not use public port forwarding
without an authenticated TLS reverse proxy.

The container runs as a non-root user with a read-only root filesystem. The
documented container command mounts the Streamlit secrets file as read-only.
These controls do not add user authentication to the dashboard.

The GitHub Pages demo is public. It contains synthetic data and runs in the
browser. It cannot load secrets, read Google Sheets, or send Discord messages.
Do not add private data or configuration files to its build inputs.
