#!/usr/bin/env bash
# tox-ansible commands_pre: system deps, then ade install (mirrors tox-ansible plugin).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

# shellcheck source=/dev/null
source "${repo_root}/scripts/ci/setup-automation-hub.sh"

bash "${repo_root}/scripts/ci/install-tox-system-deps.sh"

env_name="${TOX_ENV_NAME:?TOX_ENV_NAME is required}"
env_dir="${TOX_ENV_DIR:?TOX_ENV_DIR is required}"

if [[ "${env_name}" == "galaxy" ]]; then
  exit 0
fi

test_type="${env_name%%-*}"
rest="${env_name#*-}"
python_ver="${rest%%-*}"
ansible_ver="${rest#*-}"

if [[ "${ansible_ver}" == "devel" || "${ansible_ver}" == "milestone" ]]; then
  acv="${ansible_ver}"
else
  acv="stable-${ansible_ver}"
fi

if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
  echo "::group::Install collection with ade"
fi

editable_args=()
if [[ "${test_type}" != "sanity" ]]; then
  editable_args=(-e)
fi

export PATH="${env_dir}/bin:${PATH}"

max_attempts=3
attempt=1
rc=1
while (( attempt <= max_attempts )); do
  set +e
  ade install "${editable_args[@]}" --venv "${env_dir}" --acv "${acv}" --no-seed --im none .
  rc=$?
  set -e
  if [[ "${rc}" -eq 0 || "${rc}" -eq 2 ]]; then
    break
  fi
  if (( attempt < max_attempts )); then
    echo "WARN: ade install failed with exit ${rc} (attempt ${attempt}/${max_attempts}); retrying in 15s..." >&2
    sleep 15
  fi
  (( attempt++ ))
done
if [[ "${rc}" -ne 0 && "${rc}" -ne 2 ]]; then
  exit "${rc}"
fi

if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
  echo "::endgroup::"
fi

if [[ "${test_type}" == "sanity" ]]; then
  py_ver="${python_ver#py}"
  site_packages="${env_dir}/lib/python${py_ver}/site-packages"
  if [[ ! -d "${site_packages}" ]]; then
    site_packages="${env_dir}/lib64/python${py_ver}/site-packages"
  fi
  galaxy_file="${repo_root}/galaxy.yml"
  collection_namespace="$(grep '^namespace:' "${galaxy_file}" | awk -F: '{print $2}' | xargs)"
  collection_name="$(grep '^name:' "${galaxy_file}" | awk -F: '{print $2}' | xargs)"
  if [[ -z "${collection_namespace}" || -z "${collection_name}" ]]; then
    echo "ERROR: could not read namespace and name from ${galaxy_file}" >&2
    exit 1
  fi
  collection_path="${site_packages}/ansible_collections/${collection_namespace}/${collection_name}"
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    echo "::group::Initialize the collection to avoid ansible #68499"
  fi
  (
    cd "${collection_path}"
    git config --global init.defaultBranch main
    git init .
  )
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    echo "::endgroup::"
  fi
fi
