# Role: infra.automation_development_office.ocp_secret_replicator

Ocp Secret Replicator automation role. Primary tasks include: Set Secret Data for Hashicorp Vault Push; Validate Vault KV Version for Push; Show effective Vault write settings.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_secret_replicator_cluster_replication` | Sensitive credential value used by this role. |
| `ocp_secret_replicator_namespace_replication` | OpenShift namespace value used by this role. |
| `ocp_secret_replicator_vault_push` | Sensitive credential value used by this role. |

## 🚀 Role Usage

```yaml
- name: Run ocp_secret_replicator
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_secret_replicator
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Set Secret Data for Hashicorp Vault Push
- Validate Vault KV Version for Push
- Show effective Vault write settings
- Push source secret to Hashicorp Vault KV v1

```bash
cd roles/ocp_secret_replicator
molecule test
```

## 📁 Role Structure

```text
roles/ocp_secret_replicator/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
