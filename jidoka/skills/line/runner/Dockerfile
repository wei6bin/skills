# syntax=docker/dockerfile:1
# Runner image for scheduled /jidoka:line runs: scripts/pickup.py starts one
# container from it per story, and run-story.sh (the entrypoint) clones the
# repository and runs the line there. The container is the only place a line
# run skips Claude Code's permission prompts.
#
# It carries what every run needs: Claude Code, git, the az CLI with the
# azure-devops extension, gh, Python for the agreement script, and Node. Add
# your project's own toolchain (the .NET SDK, a browser for Playwright) in an
# image built FROM this one. Build it from this folder:
#
#   docker build -t jidoka-runner .
FROM node:22-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates gnupg python3 \
 && rm -rf /var/lib/apt/lists/*

# az CLI from Microsoft's apt repository, and the azure-devops extension.
RUN curl -fsSL https://aka.ms/InstallAzureCLIDeb | bash \
 && rm -rf /var/lib/apt/lists/*

# gh from GitHub's apt repository.
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force

COPY run-story.sh /usr/local/bin/run-story
RUN chmod 755 /usr/local/bin/run-story

# Claude Code refuses to skip permission prompts as root.
USER node
RUN az extension add --name azure-devops --only-show-errors
WORKDIR /home/node
ENTRYPOINT ["run-story"]
