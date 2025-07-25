#!/bin/bash

# Setup automatic Git commit signing for devcontainer users
# This script configures Git to use SSH keys for commit signing if the host machine has commit.gpgsign set to true in ~/.gitconfig
# NOTE: this assumes that you are using your SSH authentication key for signing your commits. If you use a separate GPG key
# for signing commits, this won't work correctly as your commits will be signed with your auth SSH key.

set -e

# If commit signing isn't set up on the host git config then we just exit
# You can still make and push commits, they just won't be signed
if [ "$(git config --get commit.gpgsign)" != "true" ]; then
    echo "Git commit signing is not enabled on host system in ~/.gitconfig so will not be enabled in devcontainer. Exiting."
    exit 0
fi

echo "Setting up Git commit signing..."

# Check if SSH agent is available
if [ -z "$SSH_AUTH_SOCK" ]; then
    echo "Warning: SSH agent not available in devcontainer. Without ssh-agent we can't find the correct key for GitHub."
    git config commit.gpgsign false
    exit 0
fi

# Check if there are SSH keys loaded
if ! ssh-add -L &>/dev/null; then
    echo "Warning: No SSH keys loaded in ssh-agent. Commits will not be signed."
    git config commit.gpgsign false
    exit 0
fi

# Function to test if a key works with GitHub
test_github_key() {
    local key_file="$1"
    ssh -o BatchMode=yes -o ConnectTimeout=5 -i "$key_file" -T git@github.com 2>&1 | grep -q "successfully authenticated"
}

# Function to find the GitHub authentication key
find_github_key() {
    echo "Finding GitHub authentication key..."

    # Create a temporary directory for key testing
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    # Get all SSH keys from ssh-agent
    local key_count=0
    while IFS= read -r ssh_key; do
        if [ -n "$ssh_key" ]; then
            key_count=$((key_count + 1))
            local temp_key="$temp_dir/key_$key_count"

            # Extract just the public key part (remove ssh-agent metadata)
            echo "$ssh_key" | awk '{print $1 " " $2}' > "$temp_key.pub"

            # Test GitHub authentication with this key by trying to connect
            echo "Testing key $key_count..."
            if timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no git@github.com 2>&1 | grep -q "successfully authenticated"; then
                echo "Found working GitHub key: ${ssh_key:0:50}..."
                echo "$ssh_key"
                return 0
            fi
        fi
    done < <(ssh-add -L)

    # If we can't determine which key works, fall back to first key
    echo "Could not determine GitHub authentication key, using first available key"
    ssh-add -L | head -n1
}

# Get the GitHub authentication key
# Tail only the last line produced by find_github_key (otherwise we get all the echoes)
SSH_KEY=$(find_github_key | tail -n1)

if [ -z "$SSH_KEY" ]; then
    echo "Warning: Could not retrieve SSH key from ssh-agent."
    exit 0
fi

echo "Found SSH key for GitHub authentication. Assuming we also want to use it for signing commits: ${SSH_KEY:0:50}..."

# Configure Git for SSH commit signing (preserve user identity from host)
git config user.signingkey "$SSH_KEY"

# Verify user identity is configured (from mounted host .gitconfig)
if ! git config user.name >/dev/null 2>&1 || ! git config user.email >/dev/null 2>&1; then
    echo "Warning: Git user identity not configured. Please set user.name and user.email:"
    echo "  git config --global user.name 'Your Name'"
    echo "  git config --global user.email 'your.email@example.com'"
fi

echo "Git commit signing configured successfully!"
echo "Using SSH key: ${SSH_KEY:0:50}..."

# Verify configuration
echo "Current Git configuration:"
echo "  Format: $(git config --get gpg.format)"
echo "  Signing key: $(git config --get user.signingkey | cut -c1-50)..."
echo "  Auto-sign: $(git config --get commit.gpgsign)"
echo "  User name: $(git config --get user.name || echo 'NOT SET')"
echo "  User email: $(git config --get user.email || echo 'NOT SET')"
