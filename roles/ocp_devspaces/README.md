# Role: infra.ado.ocp_devspaces

Ocp Devspaces automation role. Primary tasks include: Delete Devspaces instance using Operator; Resolve DevSpaces namespaces; Wait for Dev Spaces CSV to reach 'Succeeded.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_devspaces_state` | Desired state used by role tasks when supported. |
| `ocp_devspaces_disable_default_samples` | When true, replace stock getting-started samples with ``custom_samples`` (or empty). |
| `ocp_devspaces_custom_samples` | List of sample objects (``displayName``, ``description``, ``tags``, ``url``, optional ``icon``). |
| `ocp_devspaces_custom_sample_icon_source` | ``bundled`` (role ``files/ado-sample-icon.png``) or ``upload`` (icon already in sample). |
| `ocp_devspaces_default_devfile_url` | Optional single sample URL when custom_samples is empty. |
| `ocp_devspaces_default_workspace_image` | Optional default workspace container image. |
| `ocp_devspaces_status_exporter_enabled` | When true (default), deploy DevWorkspace phase/reason metrics exporter for Grafana (``dw_*`` labels) and scrape VS Code extensions (``devworkspace_vscode_extension``; needs ``pods`` + ``pods/exec``). |
| `ocp_devspaces_status_exporter_namespace` | Namespace for the exporter (default: operator namespace). |

## 🚀 Role Usage

```yaml
- name: Run ocp_devspaces
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_devspaces
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Delete Devspaces instance using Operator
- Resolve DevSpaces namespaces
- Wait for Dev Spaces CSV to reach 'Succeeded
- Ensure DevSpaces app namespace exists

```bash
cd roles/ocp_devspaces
molecule test
```

## 📁 Role Structure

```text
roles/ocp_devspaces/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
