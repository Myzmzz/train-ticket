#!/bin/bash
# Parallel Docker build and push script for train-ticket services
# Uses xargs -P to run multiple builds concurrently

set -e

REGISTRY="1.94.151.57:85/train-ticket"
TAG="1.0.0"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARALLEL_JOBS="${1:-4}"  # Default 4 parallel jobs, override with first argument
LOG_DIR="${PROJECT_DIR}/build-logs"

mkdir -p "$LOG_DIR"

echo "=== Building and pushing Docker images ==="
echo "Registry: $REGISTRY"
echo "Tag: $TAG"
echo "Parallel jobs: $PARALLEL_JOBS"
echo ""

# Generate list of services to build (exclude ts-common, ts-traceenv-test)
build_one() {
    local dir="$1"
    local svc_name="$(basename "$dir")"
    local log_file="${LOG_DIR}/${svc_name}.log"
    local image="${REGISTRY}/${svc_name}:${TAG}"

    echo "[START] ${svc_name}"

    # Build
    if docker build --platform linux/amd64 -t "$image" "$dir" > "$log_file" 2>&1; then
        echo "[BUILD OK] ${svc_name}"
    else
        echo "[BUILD FAIL] ${svc_name} - see ${log_file}"
        return 1
    fi

    # Push
    if docker push "$image" >> "$log_file" 2>&1; then
        echo "[PUSH OK] ${svc_name}"
    else
        echo "[PUSH FAIL] ${svc_name} - see ${log_file}"
        return 1
    fi

    echo "[DONE] ${svc_name}"
}

export -f build_one
export REGISTRY TAG LOG_DIR

# Find all service directories with Dockerfiles, excluding ts-common and ts-traceenv-test
find "$PROJECT_DIR" -maxdepth 1 -type d -name 'ts-*' \
    ! -name 'ts-common' \
    ! -name 'ts-traceenv-test' \
    -exec test -f '{}/Dockerfile' \; \
    -print | sort | xargs -P "$PARALLEL_JOBS" -I {} bash -c 'build_one "$@"' _ {}

echo ""
echo "=== All builds complete ==="
echo "Build logs are in: $LOG_DIR"
