#!/usr/bin/env bash
# Regenerate antsibull RST under docs/collections/ from the current collection.
# This tree is the source of truth for antsibull indexes — do not hand-edit it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${TMPDIR:-/tmp}/ado-antsibull-docs.$$"
COLL_PATH="${WORKDIR}/collections"
OUT_DIR="${WORKDIR}/out"

cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

mkdir -p "${COLL_PATH}" "${OUT_DIR}"
python3 -m venv "${WORKDIR}/venv"
# shellcheck disable=SC1091
source "${WORKDIR}/venv/bin/activate"
pip install -q "antsibull-docs" "ansible-core>=2.17"

# Install this collection (and galaxy.yml deps when network allows).
ansible-galaxy collection install "${ROOT}" --force --no-deps -p "${COLL_PATH}"
if [[ -f "${ROOT}/collections/requirements.yml" ]]; then
  ansible-galaxy collection install -r "${ROOT}/collections/requirements.yml" \
    -p "${COLL_PATH}" || true
fi

export ANSIBLE_COLLECTIONS_PATH="${COLL_PATH}"
export HOME="${WORKDIR}/home"
mkdir -p "${HOME}"

antsibull-docs collection \
  --dest-dir "${OUT_DIR}" \
  --use-current \
  infra.automation_development_office

rm -rf "${ROOT}/docs/collections"
mkdir -p "${ROOT}/docs"
cp -a "${OUT_DIR}/collections" "${ROOT}/docs/collections"
echo "Regenerated ${ROOT}/docs/collections"
