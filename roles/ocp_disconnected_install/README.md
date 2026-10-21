# Role: infra.automation_development_office.ocp_disconnected_install

Validate an exported disconnected OpenShift agent-install bundle and record a durable run directory. Milestone 1A does not mirror images, build boot media, or contact a cluster.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core 2.16 or newer
- An installation bundle exported by ado-preflight-ui (or an equivalent directory)
- A jump host that is not a node of the cluster being installed
- No OpenShift API, AAP, or Node process

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_disconnected_install_bundle_dir` | Absolute path of the exported bundle. Required. |
| `ocp_disconnected_install_run_id` | Attempt id under `runs/`. Empty generates a new id. Reuse it to rerun the same attempt. |

The role reads `manifest.yaml`, checks SHA-256 checksums, and refuses `registry.mode: offline`. `registry.mode: direct` requires `registry.url`. It copies `install-config.yaml`, `agent-config.yaml`, and `manifests/` into `runs/<run-id>/install-dir/` and does not modify the exported files.

## 🚀 Role Usage

```yaml
- name: Validate a disconnected install bundle
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_disconnected_install
      vars:
        ocp_disconnected_install_bundle_dir: /var/tmp/example-install-bundle
```

```bash
ansible-playbook -i localhost, -c local \
  playbooks/openshift/ado-validate-disconnected-install-bundle.yml \
  -e ocp_disconnected_install_bundle_dir=/var/tmp/example-install-bundle
```

Each attempt writes:

```text
runs/<run-id>/status.json
runs/<run-id>/ansible.log
runs/<run-id>/install-dir/
```

`status.json` is published with `mv` after a temporary file is written. The log records the stage only. It does not copy pull secrets or registry credentials.

## 🧪 Role Molecule Testing

Scenario `disconnected_install_bundle` uses a fixture bundle with a fake pull secret.

```bash
cd extensions/molecule
molecule test -s disconnected_install_bundle
```

## 📁 Role Structure

```text
roles/ocp_disconnected_install/
├── defaults/main.yml
├── meta/main.yml
├── README.md
└── tasks/
    ├── main.yml
    └── validate_bundle.yml
```
