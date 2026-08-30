#!/usr/bin/env sh
set -eu

pyproject_path=${1:?usage: install-tools.sh PYPROJECT}

read_version() {
    name=$1
    python -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["tool"]["portico"]["bootstrap"][sys.argv[2]])' \
        "$pyproject_path" "$name"
}

case "$(uname -m)" in
    x86_64|amd64)
        uv_arch=x86_64
        task_arch=amd64
        ;;
    arm64|aarch64)
        uv_arch=aarch64
        task_arch=arm64
        ;;
    *)
        echo "Unsupported development container architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

python_version=$(read_version python)
uv_version=$(read_version uv)
task_version=$(read_version task)

if [ "$(python -c 'import platform; print(platform.python_version())')" != "$python_version" ]; then
    echo "The development image Python version does not match pyproject.toml" >&2
    exit 1
fi

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

curl -fsSL \
    "https://github.com/astral-sh/uv/releases/download/$uv_version/uv-$uv_arch-unknown-linux-gnu.tar.gz" \
    -o "$tmp_dir/uv.tar.gz"
tar -xzf "$tmp_dir/uv.tar.gz" -C "$tmp_dir"
install "$(find "$tmp_dir" -type f -name uv -print -quit)" /usr/local/bin/uv
uvx_source=$(find "$tmp_dir" -type f -name uvx -print -quit)
if [ -n "$uvx_source" ]; then
    install "$uvx_source" /usr/local/bin/uvx
fi

curl -fsSL \
    "https://github.com/go-task/task/releases/download/v$task_version/task_linux_$task_arch.tar.gz" \
    -o "$tmp_dir/task.tar.gz"
tar -xzf "$tmp_dir/task.tar.gz" -C "$tmp_dir" task
install "$tmp_dir/task" /usr/local/bin/task

uv --version
task --version
