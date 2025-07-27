#! /bin/bash

# Set up the development environment

# Install poetry dependencies
poetry install

# Install pre-commit and pre-commit hooks
pre-commit install
pre-commit install-hooks

# Configure Git

# Check current configuration before changing anything
echo "Current Git configuration:"
echo "  Format: $(git config --get gpg.format)"
echo "  Signing key: $(git config --get user.signingkey | cut -c1-50)..."
echo "  Sign commits: $(git config --get commit.gpgsign)"
echo "  Sign tags: $(git config --get tag.gpgsign)"
echo "  User name: $(git config --get user.name || echo 'NOT SET')"
echo "  User email: $(git config --get user.email || echo 'NOT SET')"

# If format for signing is GPG, exit early and inform that we can't use GPG keys
if [ "$(git config --get gpg.format)" ]; then
    echo "You've requested SSH key signing but only GPG is supported for signing commits inside this devcontainer. Commits will not be signed."
    # SSH key signing seems to require physically mounting the .ssh directory into the devcontainer, while GPG keys can be passed through without a mount
    # This is some VSCode magic because for auth, the SSH agent can be forwarded through. It just doesn't seem to work for signing
    exit 0
fi

# Check if SSH agent is available in the container (VSCode should forward it through)
if [ -z "$SSH_AUTH_SOCK" ]; then
    echo "Warning: SSH agent not available in devcontainer. Commits will not be signed. You may need to configure SSH agent forwarding."
    # See: https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials#_using-ssh-keys
    git config commit.gpgsign false
    git config tag.gpgsign false
    exit 0
fi

# Check if there are SSH keys loaded in ssh-agent
if ! ssh-add -L 2>&1 /dev/null ; then
    echo "Warning: No SSH keys loaded in ssh-agent. Commits will not be signed."
    git config commit.gpgsign false
    git config tag.gpgsign false
    exit 0
fi

# Override signing settings using environment vars
if [ "$COMMIT_GPGSIGN" ]; then
    git config commit.gpgsign $COMMIT_GPGSIGN
fi

if [ "$TAG_GPGSIGN" ]; then
    git config tag.gpgsign $TAG_GPGSIGN
fi

# Verify that git can access your auth credentials
ssh -T -v git@github.com

# Temporary - check that git can sign a commit
git checkout -b test-branch
echo "test" > foofile.txt
git add foofile.txt && git commit -m "test commit for signing"
# Delete test commit and branch
git checkout main && git branch -D test-branch
