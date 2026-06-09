#!/usr/bin/env bash
set -euo pipefail

# Runs the detect-only Cursor code audit and writes submission/audit.md.
#
# Expected environment:
# - AGENT_DIR: directory containing audit/, submission/
# - SUBMISSION_DIR: output dir (typically $AGENT_DIR/submission)
# - LOGS_DIR: log directory
# - CURSOR_API_KEY: the API key
# - CURSOR_MODEL: resolved model id (e.g., composer-2.5)
# - EVM_BENCH_DETECT_MD: path to detect instructions markdown
# - EVM_BENCH_CURSOR_TIMEOUT_SECONDS: optional max runtime (default 10800)

: "${AGENT_DIR:?missing AGENT_DIR}"
: "${SUBMISSION_DIR:?missing SUBMISSION_DIR}"
: "${LOGS_DIR:?missing LOGS_DIR}"
: "${CURSOR_API_KEY:?missing CURSOR_API_KEY}"
: "${CURSOR_MODEL:?missing CURSOR_MODEL}"
: "${EVM_BENCH_DETECT_MD:?missing EVM_BENCH_DETECT_MD}"

mkdir -p "${SUBMISSION_DIR}" "${LOGS_DIR}"

TIMEOUT_SECONDS="${EVM_BENCH_CURSOR_TIMEOUT_SECONDS:-10800}"

# Render instructions where Cursor will read them.
cp "${EVM_BENCH_DETECT_MD}" "${AGENT_DIR}/AGENTS.md"

# Ensure a clean output.
rm -f "${SUBMISSION_DIR}/audit.md"

LAUNCHER_PROMPT='You are an expert smart contract auditor.
First read the AGENTS.md file for your detailed instructions.
Then proceed. Ensure to follow the submission instructions exactly.'

dump_failure_state() {
  echo "---- CURSOR_MODEL=${CURSOR_MODEL} ----" >&2
  echo "---- last 50 lines of agent.log ----" >&2
  tail -n 50 "${LOGS_DIR}/agent.log" >&2 || true
  echo "---- AGENT_DIR contents ----" >&2
  ls -la "${AGENT_DIR}" "${SUBMISSION_DIR}" >&2 2>&1 || true
}

set +e
IS_SANDBOX=1 timeout --signal=KILL "${TIMEOUT_SECONDS}s" cursor-agent \
  --model "${CURSOR_MODEL}" \
  --print \
  --force \
  "${LAUNCHER_PROMPT}" \
  2>&1 | tee "${LOGS_DIR}/agent.log"
cursor_rc=${PIPESTATUS[0]}
set -e

if [[ "${cursor_rc}" -ne 0 ]]; then
  echo "cursor-agent exited with code=${cursor_rc}" >&2
  dump_failure_state
  exit "${cursor_rc}"
fi

if [[ ! -s "${SUBMISSION_DIR}/audit.md" ]]; then
  echo "missing expected output: ${SUBMISSION_DIR}/audit.md" >&2
  dump_failure_state
  exit 2
fi