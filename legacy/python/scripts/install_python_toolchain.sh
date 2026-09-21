#!/usr/bin/env sh
# Install the uv and Python versions pinned by pyproject.toml.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
pyproject_path="$repo_root/pyproject.toml"
bin_dir="$repo_root/.tools/bin"
uv_bin="$bin_dir/uv"

: "${UV_PYTHON_INSTALL_DIR:=$repo_root/.tools/python}"
: "${UV_CACHE_DIR:=$repo_root/.local/uv-cache}"
export UV_PYTHON_INSTALL_DIR UV_CACHE_DIR

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

    echo "curl or wget is required to download uv" >&2
    exit 1
}

uv_has_version() {
    version="$1"
    [ -x "$uv_bin" ] && "$uv_bin" --version 2>/dev/null | grep -F "$version" >/dev/null 2>&1
}

detect_uv_archive() {
    case "$(uname -s)" in
        Linux) uv_os="unknown-linux-gnu" ;;
        Darwin) uv_os="apple-darwin" ;;
        *) echo "Unsupported OS for uv installation: $(uname -s)" >&2; exit 1 ;;
    esac

    case "$(uname -m)" in
        x86_64|amd64) uv_arch="x86_64" ;;
        arm64|aarch64) uv_arch="aarch64" ;;
        i386|i686) uv_arch="i686" ;;
        *) echo "Unsupported CPU architecture for uv installation: $(uname -m)" >&2; exit 1 ;;
    esac

    uv_archive="uv-$uv_arch-$uv_os.tar.gz"
}

install_uv() {
    version="$1"

    if uv_has_version "$version"; then
        return
    fi

    echo "[SETUP] Installing uv $version"
    tmp_dir=$(mktemp -d)
    archive_path="$tmp_dir/uv.tar.gz"
    url="https://github.com/astral-sh/uv/releases/download/$version/$uv_archive"

    download_file "$url" "$archive_path"
    tar -xzf "$archive_path" -C "$tmp_dir"

    uv_source=$(find "$tmp_dir" -type f -name uv | head -n 1)
    uvx_source=$(find "$tmp_dir" -type f -name uvx | head -n 1)
    if [ -z "$uv_source" ]; then
        echo "uv was not found in $url" >&2
        rm -rf "$tmp_dir"
        exit 1
    fi

    mkdir -p "$bin_dir"
    cp "$uv_source" "$uv_bin"
    chmod +x "$uv_bin"

    if [ -n "$uvx_source" ]; then
        cp "$uvx_source" "$bin_dir/uvx"
        chmod +x "$bin_dir/uvx"
    fi

    rm -rf "$tmp_dir"
}

python_version=$(get_bootstrap_version python)
uv_version=$(get_bootstrap_version uv)

detect_uv_archive
install_uv "$uv_version"
"$uv_bin" --version

echo "[SETUP] Ensuring Python $python_version"
"$uv_bin" python install --no-bin "$python_version"
