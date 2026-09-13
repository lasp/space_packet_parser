#! /bin/bash

# Runs on every container start (not just creation) via devcontainer.json's
# postStartCommand, since /etc/hosts is reset each time the container starts.

# Work around an IPv6/IPv4 localhost mismatch that breaks Claude Code's OAuth
# callback server (e.g. `claude mcp login`). Node's `dns.lookup('localhost')`
# prefers the `::1 localhost` entry when both are present in /etc/hosts, so
# Claude Code's callback server (which binds via `server.listen(port,
# 'localhost')`) ends up listening on ::1. VS Code's forwarded port tunnel
# connects via IPv4, so the browser's request never reaches the listener and
# the OAuth flow silently hangs.
# See: https://github.com/anthropics/claude-code/issues/44844
#
# Stripping the line that maps `::1` to `localhost` makes
# `dns.lookup('localhost')` resolve to 127.0.0.1, which the forwarded tunnel
# can actually reach. Other ::1 entries (ip6-localnet, ip6-mcastprefix, etc.)
# are unaffected since the match requires "localhost" on the line.
grep -v '^::1[[:space:]].*localhost' /etc/hosts > /tmp/hosts.fix \
  && cat /tmp/hosts.fix > /etc/hosts \
  && rm /tmp/hosts.fix || true
