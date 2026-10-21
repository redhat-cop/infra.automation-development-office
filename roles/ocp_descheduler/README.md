# Role: infra.automation_development_office.ocp_descheduler

Ocp Descheduler automation role. Primary tasks include: Create/Delete Kube Descheduler Instance; Kube descheduler task.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | Playbook install/remove choice (`present` or `absent`). |
| `instance_name` | KubeDescheduler CR name (default `cluster`). |
| `name_space` | Operator namespace (default `openshift-kube-descheduler-operator`). |
| `scheduling_interval` | Descheduling interval in seconds (default `3600`). |
| `descheduler_profiles` | List of descheduler profiles applied to the CR. |

## 🚀 Role Usage

```yaml
- name: Run ocp_descheduler
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_descheduler
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Create/Delete Kube Descheduler Instance
- Kube descheduler task

```bash
cd roles/ocp_descheduler
molecule test
```

## 📁 Role Structure

```text
roles/ocp_descheduler/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
