#!/usr/bin/env sh
# Install the pinned Task binary and run the requested Task command.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
pyproject_path="$repo_root/pyproject.toml"
bin_dir="$repo_root/.tools/bin"
task_bin="$bin_dir/task"

get_bootstrap_version() {
    name="$1"
    version=$(sed -n "s/^[[:space:]]*$name[[:space:]]*=[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$pyproject_path" | head -n 1)

    if [ -z "$version" ]; then
        echo "Missing $name version in $pyproject_path" >&2
        exit 1
    fi

    printf '%s\n' "$version"
}

download_file() {
    url="$1"
    output="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$output"
        return
    fi

    if command -v wget >/dev/null 2>&1; then
        wget -q "$url" -O "$output"
        return
    fi

    echo "curl or wget is required to download Task" >&2
    exit 1
}

task_has_version() {
    version="$1"
    [ -x "$task_bin" ] && "$task_bin" --version 2>/dev/null | grep -F "$version" >/dev/null 2>&1
}

detect_task_archive() {
    case "$(uname -s)" in
        Linux) task_os="linux" ;;
        Darwin) task_os="darwin" ;;
        *) echo "Unsupported OS for Task installation: $(uname -s)" >&2; exit 1 ;;
    esac

    case "$(uname -m)" in
        x86_64|amd64) task_arch="amd64" ;;
        arm64|aarch64) task_arch="arm64" ;;
        i386|i686) task_arch="386" ;;
        *) echo "Unsupported CPU architecture for Task installation: $(uname -m)" >&2; exit 1 ;;
    esac

    task_archive="task_${task_os}_${task_arch}.tar.gz"
}

install_task() {
    version="$1"

    if task_has_version "$version"; then
        return
    fi

    echo "[SETUP] Installing Task $version"
    tmp_dir=$(mktemp -d)
    archive_path="$tmp_dir/task.tar.gz"
    url="https://github.com/go-task/task/releases/download/v$version/$task_archive"

    download_file "$url" "$archive_path"
    tar -xzf "$archive_path" -C "$tmp_dir"

    task_source=$(find "$tmp_dir" -type f -name task | head -n 1)
    if [ -z "$task_source" ]; then
        echo "task was not found in $url" >&2
        rm -rf "$tmp_dir"
        exit 1
    fi

    mkdir -p "$bin_dir"
    cp "$task_source" "$task_bin"
    chmod +x "$task_bin"
    rm -rf "$tmp_dir"
}

task_version=$(get_bootstrap_version task)
detect_task_archive
install_task "$task_version"
"$task_bin" --version

cd "$repo_root"
if [ "$#" -eq 0 ]; then
    set -- setup
fi
"$task_bin" "$@"
