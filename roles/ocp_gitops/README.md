# Role: infra.automation_development_office.ocp_gitops

Ocp Gitops automation role. Primary tasks include: Apply ArgoCD instance; Wait for ArgoCD pods to be running; Enforce ArgoCD route if requested.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_gitops_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_gitops
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_gitops
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Apply ArgoCD instance
- Wait for ArgoCD pods to be running
- Enforce ArgoCD route if requested
- Get ArgoCD route

```bash
cd roles/ocp_gitops
molecule test
```

## 📁 Role Structure

```text
roles/ocp_gitops/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
