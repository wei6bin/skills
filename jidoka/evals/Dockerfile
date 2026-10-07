# syntax=docker/dockerfile:1
# Runner image for `make eval-claude`: Claude Code plus what its Linux Bash
# sandbox needs (bubblewrap, socat) and what a story's checks reach for (git,
# Node, curl).
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

WORKDIR /repo
