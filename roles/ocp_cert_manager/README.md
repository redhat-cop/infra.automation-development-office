# Role: infra.automation_development_office.ocp_cert_manager

Ocp Cert Manager automation role. Primary tasks include: AWS PCA | Prepare intermediate CA material (key/csr/cert) when enabled; Create root CA secret; Create ClusterIssuer or Issuer.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `ocp_cert_manager_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run ocp_cert_manager
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_cert_manager
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- AWS PCA | Prepare intermediate CA material (key/csr/cert) when enabled
- Create root CA secret
- Create ClusterIssuer or Issuer
- Install cert-manager

```bash
cd roles/ocp_cert_manager
molecule test
```

## 📁 Role Structure

```text
roles/ocp_cert_manager/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
