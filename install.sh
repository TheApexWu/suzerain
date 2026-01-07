#!/bin/bash
#
# Suzerain Installer
# Voice-activated Claude Code interface
#
# "Whatever exists without my knowledge exists without my consent."
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/YOURUSER/suzerain/main/install.sh | bash
#   or
#   ./install.sh
#

set -e

# === Colors ===

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# === Configuration ===

SUZERAIN_HOME="${HOME}/.suzerain"
VENV_DIR="${SUZERAIN_HOME}/venv"
CONFIG_FILE="${SUZERAIN_HOME}/config.yaml"
REPO_URL="https://github.com/YOURUSER/suzerain.git"  # TODO: Update with actual repo
MIN_PYTHON_VERSION="3.11"

# === Helper Functions ===

print_header() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${BOLD}$1${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[X]${NC} $1"
}

print_info() {
    echo -e "${DIM}    $1${NC}"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Compare version strings (returns 0 if $1 >= $2)
version_ge() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# === Pre-flight Checks ===

check_os() {
    print_step "Checking operating system..."

    case "$(uname -s)" in
        Darwin*)
            OS="macos"
            print_success "macOS detected"
            ;;
        Linux*)
            OS="linux"
            print_success "Linux detected"
            ;;
        *)
            print_error "Unsupported OS: $(uname -s)"
            print_info "Suzerain supports macOS and Linux"
            exit 1
            ;;
    esac
}

check_python() {
    print_step "Checking Python version..."

    # Try python3 first, then python
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        print_error "Python not found"
        print_info "Install Python 3.11+ from https://python.org"
        exit 1
    fi

    # Get version
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

    if version_ge "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
        print_success "Python $PYTHON_VERSION found ($PYTHON_CMD)"
    else
        print_error "Python $PYTHON_VERSION is too old (need $MIN_PYTHON_VERSION+)"
        print_info "Install Python 3.11+ from https://python.org"
        exit 1
    fi
}

check_portaudio() {
    print_step "Checking PortAudio (required for audio input)..."

    # Check if portaudio is installed
    PORTAUDIO_FOUND=false

    if [ "$OS" = "macos" ]; then
        # Check via brew
        if command_exists brew && brew list portaudio &>/dev/null; then
            PORTAUDIO_FOUND=true
        fi
        # Check via pkg-config
        if command_exists pkg-config && pkg-config --exists portaudio-2.0 2>/dev/null; then
            PORTAUDIO_FOUND=true
        fi
    else
        # Linux: check for development headers
        if [ -f /usr/include/portaudio.h ] || [ -f /usr/local/include/portaudio.h ]; then
            PORTAUDIO_FOUND=true
        fi
        if command_exists pkg-config && pkg-config --exists portaudio-2.0 2>/dev/null; then
            PORTAUDIO_FOUND=true
        fi
    fi

    if [ "$PORTAUDIO_FOUND" = true ]; then
        print_success "PortAudio found"
    else
        print_warning "PortAudio not found"

        if [ "$OS" = "macos" ]; then
            if command_exists brew; then
                echo ""
                read -p "    Install PortAudio via Homebrew? [Y/n] " -n 1 -r
                echo ""
                if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                    print_step "Installing PortAudio..."
                    brew install portaudio
                    print_success "PortAudio installed"
                else
                    print_warning "Skipping PortAudio - audio features may not work"
                fi
            else
                print_error "Homebrew not found"
                print_info "Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                print_info "Then run: brew install portaudio"
                exit 1
            fi
        else
            print_info "Install PortAudio using your package manager:"
            print_info "  Ubuntu/Debian: sudo apt-get install portaudio19-dev"
            print_info "  Fedora: sudo dnf install portaudio-devel"
            print_info "  Arch: sudo pacman -S portaudio"
            exit 1
        fi
    fi
}

check_claude() {
    print_step "Checking Claude Code CLI..."

    if command_exists claude; then
        CLAUDE_VERSION=$(claude --version 2>/dev/null | head -n1 || echo "unknown")
        print_success "Claude Code found: $CLAUDE_VERSION"
    else
        print_warning "Claude Code CLI not found"
        print_info "Install from: https://docs.anthropic.com/en/docs/claude-code"
        print_info "Suzerain will work, but cannot execute commands without Claude Code"
    fi
}

# === Installation ===

create_suzerain_home() {
    print_step "Creating Suzerain home directory..."

    if [ -d "$SUZERAIN_HOME" ]; then
        print_warning "Directory exists: $SUZERAIN_HOME"
    else
        mkdir -p "$SUZERAIN_HOME"
        print_success "Created: $SUZERAIN_HOME"
    fi
}

create_virtualenv() {
    print_step "Creating virtual environment..."

    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment exists: $VENV_DIR"
        read -p "    Recreate it? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
        else
            print_info "Using existing virtual environment"
            return
        fi
    fi

    $PYTHON_CMD -m venv "$VENV_DIR"
    print_success "Created virtual environment"
}

install_package() {
    print_step "Installing Suzerain..."

    # Activate venv
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip --quiet

    # Check if we're in a suzerain source directory
    if [ -f "pyproject.toml" ] && grep -q "suzerain" pyproject.toml 2>/dev/null; then
        print_info "Installing from local source..."
        pip install -e ".[wakeword]" --quiet
    elif [ -d "$SUZERAIN_HOME/src" ] && [ -f "$SUZERAIN_HOME/src/pyproject.toml" ]; then
        print_info "Installing from $SUZERAIN_HOME/src..."
        pip install -e "$SUZERAIN_HOME/src[wakeword]" --quiet
    else
        # Clone and install
        print_info "Cloning repository..."
        if [ -d "$SUZERAIN_HOME/src" ]; then
            rm -rf "$SUZERAIN_HOME/src"
        fi
        git clone --depth 1 "$REPO_URL" "$SUZERAIN_HOME/src" 2>/dev/null || {
            print_warning "Could not clone repository"
            print_info "Install manually: pip install suzerain"

            # Try installing from PyPI as fallback
            print_info "Trying PyPI install..."
            pip install suzerain --quiet 2>/dev/null || {
                print_error "Installation failed"
                print_info "Please install manually from source"
                exit 1
            }
        }

        if [ -d "$SUZERAIN_HOME/src" ]; then
            pip install -e "$SUZERAIN_HOME/src[wakeword]" --quiet
        fi
    fi

    deactivate

    print_success "Suzerain installed"
}

# === Shell Configuration ===

setup_shell_alias() {
    print_step "Setting up shell alias..."

    # Determine which shell config to use
    SHELL_NAME=$(basename "$SHELL")
    case "$SHELL_NAME" in
        zsh)
            SHELL_RC="$HOME/.zshrc"
            ;;
        bash)
            if [ -f "$HOME/.bash_profile" ]; then
                SHELL_RC="$HOME/.bash_profile"
            else
                SHELL_RC="$HOME/.bashrc"
            fi
            ;;
        fish)
            SHELL_RC="$HOME/.config/fish/config.fish"
            mkdir -p "$(dirname "$SHELL_RC")"
            ;;
        *)
            print_warning "Unknown shell: $SHELL_NAME"
            SHELL_RC="$HOME/.profile"
            ;;
    esac

    # Create alias command
    ALIAS_CMD="alias suzerain='$VENV_DIR/bin/python -m src.main'"

    # For fish shell, use different syntax
    if [ "$SHELL_NAME" = "fish" ]; then
        ALIAS_CMD="alias suzerain '$VENV_DIR/bin/python -m src.main'"
    fi

    # Check if alias already exists
    if grep -q "alias suzerain=" "$SHELL_RC" 2>/dev/null || grep -q "alias suzerain " "$SHELL_RC" 2>/dev/null; then
        print_warning "Alias already exists in $SHELL_RC"
        print_info "Updating existing alias..."
        # Remove old alias
        if [ "$OS" = "macos" ]; then
            sed -i '' '/alias suzerain/d' "$SHELL_RC"
        else
            sed -i '/alias suzerain/d' "$SHELL_RC"
        fi
    fi

    # Add alias
    echo "" >> "$SHELL_RC"
    echo "# Suzerain - Voice-activated Claude Code" >> "$SHELL_RC"
    echo "$ALIAS_CMD" >> "$SHELL_RC"

    print_success "Added alias to $SHELL_RC"
    print_info "Run 'source $SHELL_RC' or start a new terminal to use 'suzerain'"
}

# === API Key Setup ===

prompt_for_api_keys() {
    print_header "API KEY CONFIGURATION"

    echo -e "  ${DIM}Suzerain needs API keys for speech recognition.${NC}"
    echo -e "  ${DIM}You can skip this and configure later with 'suzerain --setup'${NC}"
    echo ""

    # Deepgram
    echo -e "  ${BOLD}Deepgram API Key${NC} (speech-to-text)"
    echo -e "  ${DIM}Get free key at: https://console.deepgram.com/${NC}"
    echo -e "  ${DIM}Free tier includes \$200 credit${NC}"
    echo ""

    read -p "    Enter Deepgram API key (or press Enter to skip): " -s DEEPGRAM_KEY
    echo ""

    # Picovoice (optional)
    echo ""
    echo -e "  ${BOLD}Picovoice Access Key${NC} (optional, for wake word)"
    echo -e "  ${DIM}Get free key at: https://console.picovoice.ai/${NC}"
    echo ""

    read -p "    Enter Picovoice key (or press Enter to skip): " -s PICOVOICE_KEY
    echo ""

    # Save config if any keys provided
    if [ -n "$DEEPGRAM_KEY" ] || [ -n "$PICOVOICE_KEY" ]; then
        print_step "Saving configuration..."

        cat > "$CONFIG_FILE" << EOF
# Suzerain Configuration
# Generated by install.sh

api_keys:
  deepgram: ${DEEPGRAM_KEY:-null}
  picovoice: ${PICOVOICE_KEY:-null}

preferences:
  default_mode: push_to_talk
  wake_keyword: computer
  confirmation_required: true
  verbose: false
  sandbox_mode: false

audio:
  sample_rate: 16000
  record_duration: 3
EOF

        # Secure the config file
        chmod 600 "$CONFIG_FILE"

        print_success "Configuration saved to $CONFIG_FILE"
    else
        print_warning "No API keys provided"
        print_info "Configure later with: suzerain --setup"
    fi
}

# === Main ===

main() {
    print_header "SUZERAIN INSTALLER"

    echo -e "  ${DIM}Voice-activated Claude Code interface${NC}"
    echo -e "  ${DIM}\"Whatever exists without my knowledge exists without my consent.\"${NC}"
    echo ""

    # Pre-flight checks
    check_os
    check_python
    check_portaudio
    check_claude

    print_header "INSTALLATION"

    # Installation
    create_suzerain_home
    create_virtualenv
    install_package
    setup_shell_alias

    # API Keys
    echo ""
    read -p "Configure API keys now? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        prompt_for_api_keys
    else
        print_info "Skipping API configuration"
        print_info "Configure later with: suzerain --setup"
    fi

    # Done
    print_header "INSTALLATION COMPLETE"

    echo -e "  ${GREEN}Suzerain has been installed!${NC}"
    echo ""
    echo -e "  ${BOLD}Next steps:${NC}"
    echo ""
    echo -e "    1. Start a new terminal (or run: source ~/.zshrc)"
    echo ""
    echo -e "    2. ${CYAN}suzerain --test${NC}      # Test mode (type commands)"
    echo -e "       ${CYAN}suzerain --list${NC}      # List grimoire commands"
    echo -e "       ${CYAN}suzerain${NC}             # Voice mode"
    echo ""
    echo -e "    3. Try saying: ${BOLD}\"the judge smiled\"${NC} (runs tests)"
    echo ""
    echo -e "  ${DIM}For help: suzerain --help${NC}"
    echo -e "  ${DIM}Re-run setup: suzerain --setup${NC}"
    echo ""
}

# Run main
main
