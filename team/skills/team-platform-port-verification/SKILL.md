---
name: team-platform-port-verification
description: "Use for platform work involving port verification in an approved engineering team task."
---

# Platform — Local Runtime & Tooling: Port Verification

## Inputs
Approved task and acceptance criteria, relevant repository files, current role/worktree, and applicable user preferences. Read the relevant role definition when ownership is unclear.

## Procedure
Choose an available port, bind HTTP servers to 127.0.0.1 (0.0.0.0 only when WSL or another system must reach them, and say so), check curl responses and distinguish verified URLs from advertised addresses.

## Evidence and output
Health evidence and localhost/WSL URLs.
Provide concrete file or command references and distinguish observed outcomes from assumptions. Validate at the smallest meaningful layer; do not claim checks that were not run.

## Failure handling
Report missing inputs or failed checks to Chief with evidence and the next recoverable action. Do not bypass Validator, broaden scope, or invent successful results.
