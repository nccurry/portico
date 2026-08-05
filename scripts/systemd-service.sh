#!/usr/bin/env sh
set -eu

service_name="tiller-streamlit"
unit_name="$service_name.service"
unit_path="/etc/systemd/system/$unit_name"
address="${ADDRESS:-0.0.0.0}"
port="${PORT:-8501}"
allow_context_overrides=false

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 is required."
}

require_linux() {
    [ "$(uname -s)" = "Linux" ] || fail "The systemd service is supported only on Linux."

    case "$(uname -m)" in
        x86_64|amd64|aarch64|arm64) ;;
        *) fail "A 64-bit x86_64 or ARM64 Linux installation is required." ;;
    esac
}

require_non_root() {
    [ "$(id -u)" -ne 0 ] || fail "Run installation as a non-root user with sudo access."
}

run_privileged() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        require_command sudo
        sudo "$@"
    fi
}

reject_newline() {
    value="$1"
    label="$2"
    case "$value" in
        *"
"*) fail "$label cannot contain a newline." ;;
    esac
}

escape_unit_value() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/%/%%/g'
}

resolve_service_context() {
    script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    default_repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

    if [ "$allow_context_overrides" = true ]; then
        repo_root="${REPO_ROOT:-$default_repo_root}"
        service_user="${SERVICE_USER:-$(id -un)}"
    else
        repo_root="$default_repo_root"
        service_user=$(id -un)
    fi

    if [ "$allow_context_overrides" = true ] && [ -n "${SERVICE_HOME:-}" ]; then
        service_home="$SERVICE_HOME"
    elif command -v getent >/dev/null 2>&1; then
        service_home=$(getent passwd "$service_user" | cut -d: -f6)
    else
        service_home="${HOME:-}"
    fi

    [ -n "$service_home" ] || fail "Could not determine the home directory for $service_user."

    streamlit_path="$repo_root/.venv/bin/streamlit"
    app_path="$repo_root/Home.py"
    secrets_path="$repo_root/.streamlit/secrets.toml"

    reject_newline "$repo_root" "Repository path"
    reject_newline "$service_user" "Service user"
    reject_newline "$service_home" "Service home"
    reject_newline "$address" "Address"
    reject_newline "$port" "Port"

    case "$port" in
        ''|*[!0-9]*) fail "PORT must be an integer between 1 and 65535." ;;
    esac
    [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || fail "PORT must be an integer between 1 and 65535."
}

render_unit() {
    resolve_service_context

    escaped_repo_root=$(escape_unit_value "$repo_root")
    escaped_streamlit_path=$(escape_unit_value "$streamlit_path")
    escaped_app_path=$(escape_unit_value "$app_path")
    escaped_service_user=$(escape_unit_value "$service_user")
    escaped_service_home=$(escape_unit_value "$service_home")
    escaped_address=$(escape_unit_value "$address")

    cat <<EOF
[Unit]
Description=Tiller Streamlit dashboard
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$escaped_service_user
WorkingDirectory="$escaped_repo_root"
ExecStart="$escaped_streamlit_path" run "$escaped_app_path" --server.address="$escaped_address" --server.port="$port" --server.headless=true --server.runOnSave=false --client.showErrorDetails=false
Environment="HOME=$escaped_service_home"
Environment="PYTHONUNBUFFERED=1"
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=multi-user.target
EOF
}

install_service() {
    require_linux
    require_non_root
    require_command sudo
    require_command systemctl
    require_command stat
    resolve_service_context

    [ -x "$streamlit_path" ] || fail "Runtime dependencies are missing. Run 'task deps:install:runtime'."
    [ -f "$app_path" ] || fail "Home.py was not found at $app_path."
    [ -f "$secrets_path" ] || fail "Missing $secrets_path. Configure Streamlit secrets before installing."

    secrets_owner=$(stat -c '%u' "$secrets_path")
    [ "$secrets_owner" = "$(id -u)" ] || fail "$secrets_path must be owned by $(id -un)."
    chmod 600 "$secrets_path"

    temp_dir=$(mktemp -d)
    temp_unit="$temp_dir/$unit_name"
    trap 'rm -f "$temp_unit"; rmdir "$temp_dir" 2>/dev/null || true' EXIT HUP INT TERM
    render_unit > "$temp_unit"

    if command -v systemd-analyze >/dev/null 2>&1; then
        systemd-analyze verify "$temp_unit"
    fi

    run_privileged install -m 0644 "$temp_unit" "$unit_path"
    run_privileged systemctl daemon-reload
    run_privileged systemctl enable "$unit_name"
    run_privileged systemctl restart "$unit_name"

    if ! run_privileged systemctl is-active --quiet "$unit_name"; then
        run_privileged systemctl --no-pager --full status "$unit_name" || true
        fail "$unit_name failed to start."
    fi

    printf '%s\n' "$unit_name is installed, enabled, and running on $address:$port."
}

uninstall_service() {
    require_linux
    require_command systemctl

    run_privileged systemctl disable --now "$unit_name" >/dev/null 2>&1 || true
    if [ -f "$unit_path" ]; then
        run_privileged rm -f "$unit_path"
    fi
    run_privileged systemctl daemon-reload
    run_privileged systemctl reset-failed "$unit_name" >/dev/null 2>&1 || true
    printf '%s\n' "$unit_name is not installed. Application files and secrets were preserved."
}

manage_service() {
    action="$1"
    require_linux
    require_command systemctl
    run_privileged systemctl "$action" "$unit_name"
}

show_status() {
    require_linux
    require_command systemctl
    run_privileged systemctl --no-pager --full status "$unit_name"
}

show_logs() {
    require_linux
    require_command journalctl
    run_privileged journalctl --unit "$unit_name" --lines 100 --follow
}

usage() {
    printf 'Usage: %s {render|install|uninstall|start|stop|restart|status|logs}\n' "$0" >&2
    exit 2
}

case "${1:-}" in
    render) allow_context_overrides=true; render_unit ;;
    install) install_service ;;
    uninstall) uninstall_service ;;
    start|stop|restart) manage_service "$1" ;;
    status) show_status ;;
    logs) show_logs ;;
    *) usage ;;
esac
