#!/usr/bin/env sh
set -eu

service_name="tiller-discord-weekly"
service_unit="$service_name.service"
timer_unit="$service_name.timer"
service_path="/etc/systemd/system/$service_unit"
timer_path="/etc/systemd/system/$timer_unit"
allow_context_overrides=false

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$1 is required."
}

require_linux() {
    [ "$(uname -s)" = "Linux" ] || fail "The Discord timer is supported only on Linux."

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

escape_unit_path() {
    printf '%s' "$1" | sed -e 's/\\/\\x5c/g' -e 's/ /\\x20/g' -e 's/"/\\x22/g' -e 's/%/%%/g'
}

resolve_context() {
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

    python_path="$repo_root/.venv/bin/python"
    notifier_path="$repo_root/scripts/weekly-discord-summary.py"
    secrets_path="$repo_root/.streamlit/secrets.toml"

    reject_newline "$repo_root" "Repository path"
    reject_newline "$service_user" "Service user"
    reject_newline "$service_home" "Service home"
}

render_service() {
    resolve_context

    escaped_repo_root=$(escape_unit_path "$repo_root")
    escaped_python_path=$(escape_unit_value "$python_path")
    escaped_notifier_path=$(escape_unit_value "$notifier_path")
    escaped_service_user=$(escape_unit_value "$service_user")
    escaped_service_home=$(escape_unit_value "$service_home")

    cat <<EOF
[Unit]
Description=Tiller weekly Discord expense summary
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=30min
StartLimitBurst=3

[Service]
Type=oneshot
User=$escaped_service_user
WorkingDirectory=$escaped_repo_root
ExecStart="$escaped_python_path" "$escaped_notifier_path" send --output=json
Environment="HOME=$escaped_service_home"
Environment="PYTHONUNBUFFERED=1"
Restart=on-failure
RestartSec=5min
NoNewPrivileges=true
PrivateTmp=true
UMask=0077
EOF
}

render_timer() {
    cat <<EOF
[Unit]
Description=Run the Tiller weekly Discord expense summary

[Timer]
OnCalendar=Sun *-*-* 20:00:00
Persistent=true
Unit=$service_unit

[Install]
WantedBy=timers.target
EOF
}

install_timer() {
    require_linux
    require_non_root
    require_command sudo
    require_command systemctl
    require_command stat
    resolve_context

    [ -x "$python_path" ] || fail "Runtime dependencies are missing. Run 'task deps:install:runtime'."
    [ -f "$notifier_path" ] || fail "The Discord notifier was not found in the checkout."
    [ -f "$secrets_path" ] || fail "Missing $secrets_path. Configure Streamlit secrets before installing."

    secrets_owner=$(stat -c '%u' "$secrets_path")
    [ "$secrets_owner" = "$(id -u)" ] || fail "$secrets_path must be owned by $(id -un)."
    chmod 600 "$secrets_path"

    "$python_path" "$notifier_path" check --output=json >/dev/null

    temp_dir=$(mktemp -d)
    temp_service="$temp_dir/$service_unit"
    temp_timer="$temp_dir/$timer_unit"
    trap 'rm -f "$temp_service" "$temp_timer"; rmdir "$temp_dir" 2>/dev/null || true' EXIT HUP INT TERM
    render_service > "$temp_service"
    render_timer > "$temp_timer"

    if command -v systemd-analyze >/dev/null 2>&1; then
        systemd-analyze verify "$temp_service" "$temp_timer"
    fi

    run_privileged install -m 0644 "$temp_service" "$service_path"
    run_privileged install -m 0644 "$temp_timer" "$timer_path"
    run_privileged systemctl daemon-reload
    run_privileged systemctl reset-failed "$service_unit" "$timer_unit" >/dev/null 2>&1 || true
    run_privileged systemctl enable "$timer_unit"
    run_privileged systemctl restart "$timer_unit"

    if ! run_privileged systemctl is-active --quiet "$timer_unit"; then
        run_privileged systemctl --no-pager --full status "$timer_unit" || true
        fail "$timer_unit failed to start."
    fi

    printf '%s\n' "$timer_unit is installed, enabled, and active."
    run_privileged systemctl list-timers "$timer_unit" --no-pager
}

uninstall_timer() {
    require_linux
    require_command systemctl

    run_privileged systemctl disable --now "$timer_unit" >/dev/null 2>&1 || true
    run_privileged systemctl stop "$service_unit" >/dev/null 2>&1 || true
    if [ -f "$timer_path" ]; then
        run_privileged rm -f "$timer_path"
    fi
    if [ -f "$service_path" ]; then
        run_privileged rm -f "$service_path"
    fi
    run_privileged systemctl daemon-reload
    run_privileged systemctl reset-failed "$service_unit" "$timer_unit" >/dev/null 2>&1 || true
    printf '%s\n' "Discord notifier units are not installed. Application files, state, and secrets were preserved."
}

show_status() {
    require_linux
    require_command systemctl
    run_privileged systemctl --no-pager --full status "$timer_unit"
    run_privileged systemctl --no-pager show "$service_unit" \
        --property=ActiveState \
        --property=Result \
        --property=ExecMainStatus \
        --property=InactiveExitTimestamp
}

show_logs() {
    require_linux
    require_command journalctl
    run_privileged journalctl --unit "$service_unit" --lines 100 --follow
}

usage() {
    printf 'Usage: %s {render-service|render-timer|install|uninstall|status|logs}\n' "$0" >&2
    exit 2
}

case "${1:-}" in
    render-service) allow_context_overrides=true; render_service ;;
    render-timer) render_timer ;;
    install) install_timer ;;
    uninstall) uninstall_timer ;;
    status) show_status ;;
    logs) show_logs ;;
    *) usage ;;
esac
