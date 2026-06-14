#!/usr/bin/env bash

# Edit this file, or override values from env before running bin/launch-herd.

WORKSPACE_LABEL=${WORKSPACE_LABEL:-pr-review-loop}
JAI_REPO=${JAI_REPO:-$PWD}

AGENTS_GIT_URL=${AGENTS_GIT_URL:-https://github.com/ashleysmart-japanai/agents.git}
AGENTS_REPO=${AGENTS_REPO:-$HOME/agents}
SKIP_AGENTS_SYNC=${SKIP_AGENTS_SYNC:-0}

AGENT_BIN=${AGENT_BIN:-claude}
AGENT_ARGS=${AGENT_ARGS:---permission-mode auto}
POLL_SECONDS=${POLL_SECONDS:-120}

PARENT_PR=${PARENT_PR:-}
PR_NUMBERS=${PR_NUMBERS:-}
CHILD_PRS=${CHILD_PRS:-}
PARENT_BRANCH=${PARENT_BRANCH:-}

REVIEW_DIR=${REVIEW_DIR:-$PWD/.herdr-pr-loop}
FEEDBACK_MD=${FEEDBACK_MD:-$REVIEW_DIR/feedback.md}
FEEDBACK_LOCK_MD=${FEEDBACK_LOCK_MD:-$REVIEW_DIR/feedback.lock.md}
REVIEW_MD=${REVIEW_MD:-$REVIEW_DIR/review.md}
