#! /bin/bash

# Set up the development environment

# Install poetry dependencies
poetry lock && poetry sync

# Install pre-commit and pre-commit hooks
pre-commit install
pre-commit install-hooks

# Configure Git

# Check current configuration before changing anything
echo "Current Git configuration:"
echo "  Format: $(git config --get gpg.format || echo 'NOT SET (defaults to GPG)')"
echo "  Signing key: $(git config --get user.signingkey | cut -c1-50)..."
echo "  Sign commits: $(git config --get commit.gpgsign || echo 'NOT SET')"
echo "  Sign tags: $(git config --get tag.gpgsign || echo 'NOT SET')"
echo "  User name: $(git config --get user.name || echo 'NOT SET')"
echo "  User email: $(git config --get user.email || echo 'NOT SET')"

# Configure Git authentication

# Check if SSH agent is available in the container (VSCode should forward it through)
if [ -z "$SSH_AUTH_SOCK" ]; then
    echo "Warning: SSH agent not available in devcontainer. SSH authentication will not work."
    echo "If you need SSH authentication, configure SSH agent forwarding in VSCode."
    # See: https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials#_using-ssh-keys
    SSH_AVAILABLE=false
else
    echo "SSH agent is available. Checking for loaded keys."

    # Check if there are SSH keys loaded in ssh-agent
    if ! ssh-add -L >/dev/null 2>&1; then
        echo "Warning: No SSH keys loaded in ssh-agent. SSH authentication will not work."
        echo "If you need SSH authentication, make sure your auth key is added to SSH agent on the host system."
        SSH_AVAILABLE=false
    else
        echo "Found at least one key loaded. Assuming this is the correct key for Git auth."
        SSH_AVAILABLE=true
    fi
fi

# Verify that git can access your auth credentials
if [ "$SSH_AVAILABLE" = "true" ]; then
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo "Successfully authenticated with GitHub via SSH."
    else
        echo "SSH agent available but GitHub SSH authentication failed."
    fi
else
    echo "SSH authentication not available. Using HTTPS authentication."
    echo "You will need to authenticate either by forwarding your HTTP credentials through (should happen automatically) or by using the gh CLI."
fi

# Configure Git commit signing

# Override signing settings using environment vars
if [ "$COMMIT_GPGSIGN" ]; then
    git config commit.gpgsign $COMMIT_GPGSIGN
fi

if [ "$TAG_GPGSIGN" ]; then
    git config tag.gpgsign $TAG_GPGSIGN
fi

# If format for signing is SSH, exit early and inform that we can't use SSH keys for signing
# If you want to sign commits, you must set up GPG keys, which can be accessed from inside the devcontainer
if { [ "$COMMIT_GPGSIGN" = "true" ] || [ "$TAG_GPGSIGN" = "true" ]; } && [ "$(git config --get gpg.format)" = "ssh" ]; then
    echo "You've requested SSH key signing but only GPG is supported for signing commits inside this devcontainer. Commits will not be signed."
    # SSH key signing seems to require physically mounting the .ssh directory into the devcontainer, while GPG keys can be passed through without a mount
    # This is some VSCode magic because for auth, the SSH agent can be forwarded through. It just doesn't seem to work for signing
    exit 1  # This is an error because the user requested SSH-based commit signing but we can't support it
fi

# If signing is requested, ensure the key is available in the container
if { [ "$COMMIT_GPGSIGN" = "true" ] || [ "$TAG_GPGSIGN" = "true" ]; } && [ -n "$(git config --get user.signingkey)" ]; then
    SIGNING_KEY=$(git config --get user.signingkey)
    if ! gpg --list-keys "$SIGNING_KEY" >/dev/null 2>&1; then
        echo "Warning: The signing key '$SIGNING_KEY' is not available in GPG keyring."
        echo "Commits/tags may fail to sign."
    else
        echo "Configured GPG signing key '$SIGNING_KEY' is available."
    fi
fi

# Display final configuration
echo "Final Git configuration:"
echo "  Format: $(git config --get gpg.format || echo 'NOT SET (defaults to GPG)')"
echo "  Signing key: $(git config --get user.signingkey | cut -c1-50)..."
echo "  Sign commits: $(git config --get commit.gpgsign || echo 'NOT SET')"
echo "  Sign tags: $(git config --get tag.gpgsign || echo 'NOT SET')"
echo "  User name: $(git config --get user.name || echo 'NOT SET')"
echo "  User email: $(git config --get user.email || echo 'NOT SET')"