#!/usr/bin/env bash

create_venv() {
    local env_name=${1:-".venv"}

    python3 -m venv $env_name
}

install_deps() {
    local env_name=${1:-".venv"}

    source $env_name/bin/activate

    pip install -U pip

    if [ -f "requirements.txt" ]; then
        pip install -r ./requirements.txt
    fi

    if [ -f "setup.py" ]; then
        pip install -e .
    fi
}

activate_venv() {
    local env_name=${1:-".venv"}

    source $env_name/bin/activate
}

check_venv() {
    local env_name=${1:-".venv"}

    if [ -d "$env_name" ]; then
        true
    else
        false
    fi
}

venv_name=$HOME/.venv/ezshare_resmed
if ! check_venv $venv_name ; then
    create_venv $venv_name
fi

install_deps $venv_name
mkdir -p $HOME/.local/bin
mkdir -p $HOME/.config/ezshare_resmed
cp ezshare_resmed $HOME/.local/bin
cp ezshare_resmed.py $HOME/.local/bin
cp ezshare_resmed.ini $HOME/.config/ezshare_resmed/config.ini

if ! [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    echo -e "\nezshare_resmed is installed to $HOME/.local/bin which is not in your PATH"
    echo "Add \$HOME/.local/bin to your PATH before running ezshare_resmed"

    shell=$(basename $SHELL)
    if [[ $shell == "zsh" ]]; then
        echo "Your shell appears to be zsh. To set the PATH in zsh run:"
        echo -e "\necho 'export PATH="\$HOME/.local/bin:\$PATH"' >> ~/.zshrc"
        echo -e "source ~/.zshrc\n"
    elif [[ $shell == "bash" ]]; then
        echo "Your shell appears to be bash. To set the PATH in bash run:"
        echo -e "\necho 'export PATH="\$HOME/.local/bin:\$PATH"' >> ~/.bashrc"
        echo -e "source ~/.bashrc\n"
    fi
fi

echo "Installation complete"
echo "Default configuration file saved at $HOME/.config/ezshare_resmed/config.ini"
echo "Run with:"
echo -e "\nezshare_resmed"