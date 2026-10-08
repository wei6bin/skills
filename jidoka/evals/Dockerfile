# syntax=docker/dockerfile:1
# Runner image for `make eval-claude`: Claude Code plus what its Linux Bash
# sandbox needs (bubblewrap, socat) and what a story's checks reach for (git,
# Node, curl, and the .NET SDK the greenfield scaffold builds with).
# Running the eval here keeps it off the host, so the host's Docker credential
# store and any other machine state cannot block or leak into it.
#
# The build has no context (the Makefile pipes this file on stdin), and a
# TLS-inspecting proxy's CA comes in as the optional `ca` secret, so nothing
# machine-specific is baked into the image.
FROM node:22-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends bubblewrap socat git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ARG CLAUDE_CODE_VERSION=latest
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca; fi \
 && npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force

# .NET SDK for line-greenfield-scaffold, whose backend is ASP.NET Core. libicu
# is its globalization dependency. A TLS-inspecting proxy's CA reaches the
# installer's curl through CURL_CA_BUNDLE, as it reaches npm above.
ARG DOTNET_CHANNEL=10.0
RUN --mount=type=secret,id=ca,required=false \
    apt-get update \
 && apt-get install -y --no-install-recommends libicu72 \
 && rm -rf /var/lib/apt/lists/* \
 && if [ -f /run/secrets/ca ]; then cat /etc/ssl/certs/ca-certificates.crt /run/secrets/ca > /tmp/ca.pem; export CURL_CA_BUNDLE=/tmp/ca.pem; fi \
 && curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
 && bash /tmp/dotnet-install.sh --channel "$DOTNET_CHANNEL" --install-dir /usr/share/dotnet \
 && ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
 && rm -f /tmp/dotnet-install.sh /tmp/ca.pem
ENV DOTNET_ROOT=/usr/share/dotnet DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

# Node reads an extra CA from NODE_EXTRA_CA_CERTS, but .NET only trusts the
# system store. When the run mounts one at /etc/ssl/extra-ca.pem (the Makefile
# does for EXTRA_CA), add it to the store before the eval starts, so the image
# itself stays free of machine-specific certificates.
RUN printf '%s\n' '#!/bin/sh' \
      'if [ -f /etc/ssl/extra-ca.pem ]; then' \
      '  cp /etc/ssl/extra-ca.pem /usr/local/share/ca-certificates/extra-ca.crt' \
      '  update-ca-certificates >/dev/null 2>&1' \
      'fi' \
      'exec "$@"' > /usr/local/bin/trust-extra-ca \
 && chmod +x /usr/local/bin/trust-extra-ca
ENTRYPOINT ["trust-extra-ca"]

WORKDIR /repo
