# Role: infra.automation_development_office.ocp_gitlab_runner

Ocp Gitlab Runner automation role. Primary tasks include: Create service account; Create/ensure ClusterRole for GitLab Runner; Bind ClusterRole to the runner ServiceAccount (namespaced binding name).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_gitlab_runner_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_gitlab_runner
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_gitlab_runner
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create service account
- Create/ensure ClusterRole for GitLab Runner
- Bind ClusterRole to the runner ServiceAccount (namespaced binding name)
- Deploy GitLab Runner to OpenShift

```bash
cd roles/ocp_gitlab_runner
molecule test
```

## 📁 Role Structure

```text
roles/ocp_gitlab_runner/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
