FROM python:3.13-slim
ARG TARGETPLATFORM
USER root

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

# Install basic development tools and iptables/ipset
RUN apt update && apt install -y less \
  git \
  procps \
  sudo \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  curl \
  wget \
  vim \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install conda
ENV CONDA_DIR=/root/.local/conda
RUN <<EOF
set -ex
if [ "$TARGETPLATFORM" = "linux/arm64" ] || [ "$TARGETPLATFORM" = "linux/aarch64" ]; then ARCH="aarch64"; else ARCH="x86_64"; fi
CONDA_INSTALL_SCRIPT=Miniconda3-latest-Linux-$ARCH.sh
wget -q https://repo.anaconda.com/miniconda/$CONDA_INSTALL_SCRIPT
bash $CONDA_INSTALL_SCRIPT -b -p $CONDA_DIR
rm $CONDA_INSTALL_SCRIPT
export PATH="$CONDA_DIR/bin:$PATH"
conda tos accept
conda config --add channels conda-forge
conda config --set channel_priority strict
conda config --set auto_activate_base false
echo "export CONDA_DIR=$CONDA_DIR" >> /root/.zshrc
echo ". $CONDA_DIR/etc/profile.d/conda.sh" >> /root/.zshrc
EOF
# Add Conda bin dir to the end of the PATH
ENV PATH="$PATH:$CONDA_DIR/bin"

# Create config directory and set permissions
RUN mkdir -p /root/.claude

# Install Claude
RUN npm install -g @anthropic-ai/claude-code

# Set the default shell to zsh rather than sh
ENV SHELL=/bin/zsh

# Default Powerlevel10k theme
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.2.0/zsh-in-docker.sh)" -- \
  -p git \
  -p colorize \
  - python \
  - uv \
  -p https://github.com/zsh-users/zsh-autosuggestions \
  -p https://github.com/zsh-users/zsh-completions \
  -x

# Copy and set up dev environment script
COPY setup-dev-environment.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup-dev-environment.sh

# Copy CLAUDE.md and settings to Claude config directory
COPY CLAUDE.md /root/.claude/
