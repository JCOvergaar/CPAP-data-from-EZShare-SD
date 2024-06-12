#!/usr/bin/env bash

create_venv() {
    local env_name=${1:-".venv"}

    if [ -d "$env_name" ]; then
        echo "Virtual environment '$env_name' already exists. Aborting."
        return 1
    fi

    python3 -m venv "$env_name"
    source "./$env_name/bin/activate"
    pip install -U pip
}

activate_venv() {
    local env_name=${1:-".venv"}

    if [ ! -d "$env_name" ]; then
        echo "Virtual environment '$env_name' not found. Use '$0 create [env_name]' to create one."
        return 1
    fi

    source "./$env_name/bin/activate"
}

install_deps() {
    local env_name=${1:-".venv"}

    if [ ! -d "$env_name" ]; then
        echo "Virtual environment '$env_name' not found. Use '$0 create [env_name]' to create one."
        return 1
    fi

    source "./$env_name/bin/activate"

    if [ -f "requirements.txt" ]; then
        pip install -r ./requirements.txt
    fi

    if [ -f "setup.py" ]; then
        pip install -e .
    fi
}

remove_venv() {
    local env_name=${1:-".venv"}

    if [ ! -d "$env_name" ]; then
        echo "Virtual environment '$env_name' not found."
        return 1
    fi

    deactivate
    rm -rf "$env_name"
}

print_help() {
    # Help message explaining script usage
    echo "Usage: $0 [option] [env_name]"
    echo "Options:"
    echo "  create   Create a new virtual environment (default name: .venv)"
    echo "  activate Activate an existing virtual environment (default name: .venv)"
    echo "  install  Install dependencies within a virtual environment (default name: .venv)"
    echo "  remove   Remove an existing virtual environment (default name: .venv)"
    echo "  setup   Create a new virtual enviornment and install dependencies (default name: .venv)"
    return 0
}
case "$1" in
    "create")
        create_venv "$2"
        ;;
    "activate")
        activate_venv "$2"
        ;;
    "install")
        install_deps "$2"
        ;;
    "export")
        export_deps "$2"
        ;;
    "remove")
        remove_venv "$2"
        ;;
    "setup")
        create_venv "$2"
        install_deps "$2"
        ;;
    "--help")
        print_help
        ;;
    "-h")
        print_help
        ;;
    *)
        echo "Unknown option: $1"
        print_help
        exit 1
        ;;
esac