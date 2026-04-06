#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-entropyhunt-ros2:humble}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-${ROOT_DIR}/docker/ros2-humble.Dockerfile}"

build_image() {
  printf '==> building ROS 2 validation image: %s\n' "${IMAGE_TAG}"
  docker build -t "${IMAGE_TAG}" -f "${DOCKERFILE_PATH}" "${ROOT_DIR}"
}

run_validation() {
  printf '==> running ROS 2 validation in container\n'
  docker run --rm -it \
    -e ROS_DISTRO_OVERRIDE="${ROS_DISTRO_OVERRIDE:-humble}" \
    -e COUNT="${COUNT:-5}" \
    -e GRID="${GRID:-10}" \
    -e TARGET_X="${TARGET_X:-7}" \
    -e TARGET_Y="${TARGET_Y:-3}" \
    -e FAIL_DRONE="${FAIL_DRONE:-drone_2}" \
    -e FAIL_AT="${FAIL_AT:-60}" \
    -e SNAPSHOT_PATH="${SNAPSHOT_PATH:-/tmp/entropyhunt_ros_snapshot.json}" \
    -e SNAPSHOT_HOST="${SNAPSHOT_HOST:-127.0.0.1}" \
    -e SNAPSHOT_PORT="${SNAPSHOT_PORT:-8776}" \
    -e LAUNCH_WAIT_SECONDS="${LAUNCH_WAIT_SECONDS:-6}" \
    -v "${ROOT_DIR}:/workspace" \
    -w /workspace \
    "${IMAGE_TAG}" \
    /bin/bash -lc "./scripts/ros2_phase3_validate.sh"
}

build_image
run_validation
