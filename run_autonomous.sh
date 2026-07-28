#!/usr/bin/env bash
set -euo pipefail

# Default command placeholders (can be overridden via environment variables or CLI args)
DEPS_CMD="npm ci"
START_CMD="node server.js"
TEST_CMD="npm test"
VERIFY_CMD="curl -s -X POST http://localhost:3000/api/notifications -H \"Content-Type: application/json\" -d '{\"recipient\":\"test@example.com\",\"subject\":\"Test\",\"body\":\"Hello\",\"priority\":\"high\"}' | grep -q \"id\""
SETUP_CMD=""

# Parse CLI arguments (optional)
while [[ $# -gt 0 ]]; do
  case $1 in
    --deps) DEPS_CMD="$2"; shift;;
    --start) START_CMD="$2"; shift;;
    --test) TEST_CMD="$2"; shift;;
    --verify) VERIFY_CMD="$2"; shift;;
    --setup) SETUP_CMD="$2"; shift;;
    *) echo "Unknown argument: $1"; exit 1;;
  esac
  shift
done

# Export variables for envsubst
export DEPS_CMD START_CMD TEST_CMD VERIFY_CMD SETUP_CMD

# Generate the full runbook by substituting placeholders
envsubst < /Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/runbook_template.yaml > /tmp/autonomous_runbook.yaml

# Execute the generated runbook step-by-step
echo "=== Autonomous Workflow Started ==="

# 1. Setup (optional)
if [[ -n "$SETUP_CMD" ]]; then
  echo "Running setup: $SETUP_CMD"
  eval "$SETUP_CMD"
fi

# 2. Install dependencies
echo "Installing dependencies: $DEPS_CMD"
eval "$DEPS_CMD"

# 3. Start application (background)
echo "Starting application: $START_CMD"
eval "$START_CMD" &
SERVER_PID=$!
echo "Server started with PID $SERVER_PID"

# Give the server time to initialize
sleep 3

# 4. Run tests
echo "Running tests: $TEST_CMD"
eval "$TEST_CMD"

# 5. Verify functionality
echo "Verifying endpoint: $VERIFY_CMD"
eval "$VERIFY_CMD"

# 6. Stop application
echo "Stopping application (PID $SERVER_PID)"
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true

echo "=== Workflow completed successfully ==="