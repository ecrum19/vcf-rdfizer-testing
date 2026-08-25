#!/usr/bin/env bash
set -euo pipefail

# Optional overrides:
#   VCF_RDFIZER_VERSION=1.0.0 bash scripts/install_vcf_rdfizer_ubuntu.sh
#   VCF_RDFIZER_VENV="$HOME/.venvs/vcf-rdfizer" bash scripts/install_vcf_rdfizer_ubuntu.sh
#   bash scripts/install_vcf_rdfizer_ubuntu.sh --docker-only
VCF_RDFIZER_VERSION="${VCF_RDFIZER_VERSION:-}"
VCF_RDFIZER_VENV="${VCF_RDFIZER_VENV:-$HOME/.local/share/vcf-rdfizer/venv}"
USER_BIN="${HOME}/.local/bin"
INSTALL_PYTHON_CLI=1

log() { printf '[vcf-rdfizer-install] %s\n' "$*"; }
fail() { printf '[vcf-rdfizer-install] ERROR: %s\n' "$*" >&2; exit 1; }

apt_package_is_installed() {
  dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q '^install ok installed$'
}

install_missing_apt_packages() {
  local missing_packages=()
  local package

  for package in "$@"; do
    if ! apt_package_is_installed "$package"; then
      missing_packages+=("$package")
    fi
  done

  if ((${#missing_packages[@]} == 0)); then
    log "Requested apt packages are already installed: $*"
    return
  fi

  log "Installing missing apt packages: ${missing_packages[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing_packages[@]}"
}

case "${1:-}" in
  "") ;;
  --docker-only)
    INSTALL_PYTHON_CLI=0
    ;;
  --help|-h)
    printf 'Usage: %s [--docker-only]\n' "$(basename "$0")"
    printf '\nBy default, install Docker and the VCF-RDFizer Python CLI.\n'
    printf '%s\n' '--docker-only: install and configure Docker without installing VCF-RDFizer.'
    exit 0
    ;;
  *)
    fail "Unknown option: $1 (use --help for usage)"
    ;;
esac

[[ "${EUID}" -ne 0 ]] || fail "Run this script as your normal user, not with sudo. It uses sudo only where needed."
command -v sudo >/dev/null 2>&1 || fail "sudo is required."
command -v apt-get >/dev/null 2>&1 || fail "This installer requires Ubuntu's apt package manager."

if [[ ! -r /etc/os-release ]]; then
  fail "Cannot identify the operating system."
fi
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || fail "This installer supports Ubuntu only; detected ${ID:-unknown}."

# unzip is needed by the VCF-RDFizer workflow in both normal and Docker-only
# modes, so ensure it independently of whether Docker is already installed.
install_missing_apt_packages unzip

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker CLI already installed: $(docker --version)"
    return
  fi

  local docker_packages=(
    docker-ce
    docker-ce-cli
    containerd.io
    docker-buildx-plugin
    docker-compose-plugin
  )
  local missing_docker_packages=()
  local package

  for package in "${docker_packages[@]}"; do
    if ! apt_package_is_installed "$package"; then
      missing_docker_packages+=("$package")
    fi
  done

  if ((${#missing_docker_packages[@]} == 0)); then
    log "Docker packages are already installed."
    return
  fi

  log "Installing Docker Engine from Docker's official apt repository"
  install_missing_apt_packages ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings

  if [[ ! -s /etc/apt/keyrings/docker.asc ]]; then
    log "Downloading Docker's apt signing key"
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  else
    log "Docker's apt signing key already present"
  fi
  sudo chmod a+r /etc/apt/keyrings/docker.asc

  if [[ ! -s /etc/apt/sources.list.d/docker.sources ]]; then
    sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  else
    log "Docker apt repository configuration already present"
  fi

  install_missing_apt_packages "${missing_docker_packages[@]}"
}

configure_docker() {
  log "Enabling Docker at boot"
  sudo systemctl enable --now docker

  if ! getent group docker >/dev/null 2>&1; then
    sudo groupadd docker
  fi
  if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    sudo usermod -aG docker "$USER"
    log "Added $USER to the docker group; log out and back in before running Docker without sudo."
  fi

  if docker info >/dev/null 2>&1; then
    log "Docker is available to the current shell."
  elif sudo docker info >/dev/null 2>&1; then
    log "Docker is running; the current shell needs a new login for non-root access."
  else
    fail "Docker is installed but the daemon is not responding. Check: sudo systemctl status docker"
  fi
}

install_python_cli() {
  log "Installing Python prerequisites"
  install_missing_apt_packages python3 python3-venv

  if [[ ! -x "$VCF_RDFIZER_VENV/bin/python" ]]; then
    log "Creating VCF-RDFizer virtual environment at $VCF_RDFIZER_VENV"
    python3 -m venv "$VCF_RDFIZER_VENV"
  else
    log "VCF-RDFizer virtual environment already present at $VCF_RDFIZER_VENV"
  fi

  if [[ ! -x "$VCF_RDFIZER_VENV/bin/pip" ]]; then
    log "Bootstrapping pip in the VCF-RDFizer virtual environment"
    "$VCF_RDFIZER_VENV/bin/python" -m ensurepip --upgrade
  fi

  local installed_version
  installed_version="$("$VCF_RDFIZER_VENV/bin/python" -c 'from importlib.metadata import version; print(version("vcf-rdfizer"))' 2>/dev/null || true)"

  if [[ -n "$installed_version" && -z "$VCF_RDFIZER_VERSION" ]]; then
    log "VCF-RDFizer already installed in the virtual environment: $installed_version"
  elif [[ -n "$installed_version" && "$installed_version" == "$VCF_RDFIZER_VERSION" ]]; then
    log "Requested VCF-RDFizer version already installed: $installed_version"
  elif [[ -n "$VCF_RDFIZER_VERSION" ]]; then
    log "Installing requested VCF-RDFizer version: $VCF_RDFIZER_VERSION"
    "$VCF_RDFIZER_VENV/bin/python" -m pip install --upgrade "vcf-rdfizer==${VCF_RDFIZER_VERSION}"
  else
    log "VCF-RDFizer is not installed; downloading the current package"
    "$VCF_RDFIZER_VENV/bin/python" -m pip install vcf-rdfizer
  fi

  mkdir -p "$USER_BIN"
  local cli_path
  if [[ -x "$VCF_RDFIZER_VENV/bin/vcf-rdfizer" ]]; then
    cli_path="$VCF_RDFIZER_VENV/bin/vcf-rdfizer"
  elif [[ -x "$VCF_RDFIZER_VENV/bin/vcf_rdfizer" ]]; then
    cli_path="$VCF_RDFIZER_VENV/bin/vcf_rdfizer"
  else
    fail "The vcf-rdfizer CLI was not created in $VCF_RDFIZER_VENV/bin."
  fi

  ln -sfn "$cli_path" "$USER_BIN/vcf-rdfizer"
  ln -sfn "$cli_path" "$USER_BIN/vcf_rdfizer"
}

configure_path() {
  local path_line='export PATH="$HOME/.local/bin:$PATH"'
  local startup_file

  for startup_file in "$HOME/.profile" "$HOME/.bashrc"; do
    touch "$startup_file"
    if ! grep -Fqx "$path_line" "$startup_file"; then
      printf '\n%s\n' "$path_line" >> "$startup_file"
    fi
  done

  export PATH="$USER_BIN:$PATH"
}

install_docker
configure_docker

if (( INSTALL_PYTHON_CLI )); then
  install_python_cli
  configure_path
else
  log "Docker-only mode: skipping VCF-RDFizer installation and PATH changes."
fi

log "Installation complete."
if (( INSTALL_PYTHON_CLI )); then
  log "Current shell commands:"
  log "  $USER_BIN/vcf-rdfizer --help"
  log "  $USER_BIN/vcf_rdfizer --help"
fi
log "Open a new login shell before running Docker without sudo."
