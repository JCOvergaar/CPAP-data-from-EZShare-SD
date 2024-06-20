#!/usr/bin/env bash

create_venv() {
    local env_name=${1:-".venv"}

    python3 -m venv $env_name
}

install_deps() {
    local env_name=${1:-".venv"}

    source $env_name/bin/activate

    if [ -f "requirements.txt" ]; then
        pip install -r ./requirements.txt
    fi

    if [ -f "setup.py" ]; then
        pip install -e .
    fi
}

check_venv() {
    local env_name=${1:-".venv"}

    if [ -d "$env_name" ]; then
        true
    else
        false
    fi
}

check_python() {
    if command -v python3 > /dev/null 2>&1 ; then
        true
    else
        false
    fi
}

venv_name=$HOME/.venv/ezshare_resmed
if ! check_python ; then
    echo "Python3 not installed, please install"
    exit 1
fi

if ! check_venv $venv_name ; then
    create_venv $venv_name
fi

install_deps $venv_name
mkdir -p $HOME/.local/bin
mkdir -p $HOME/.config/ezshare_resmed
cp ezshare_resmed $HOME/.local/bin
cp ezshare_resmed.py $HOME/.local/bin
cp ezshare_resmed_default.ini $HOME/.config/ezshare_resmed/config.ini

chmod +x $HOME/.local/bin/ezshare_resmed
chmod +x $HOME/.local/bin/ezshare_resmed.py

if ! [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    echo -e "\nezshare_resmed is installed to $HOME/.local/bin which is not in your PATH"
    echo "Add \$HOME/.local/bin to your PATH before running ezshare_resmed"

    shell=$(basename $SHELL)
    if [[ $shell == "zsh" ]]; then
        echo "Your shell appears to be zsh. To set the PATH in zsh run:"
        echo -e "\necho 'export PATH="\$HOME/.local/bin:\$PATH"' >> ~/.zshrc"
        echo "source ~/.zshrc"
    elif [[ $shell == "bash" ]]; then
        echo "Your shell appears to be bash. To set the PATH in bash run:"
        echo -e "\necho 'export PATH="\$HOME/.local/bin:\$PATH"' >> ~/.bashrc"
        echo "source ~/.bashrc"
    fi
fi

echo -e "\nInstallation complete"
echo "Default configuration file saved at $HOME/.config/ezshare_resmed/config.ini"
echo "Run with:"
echo -e "\nezshare_resmed"