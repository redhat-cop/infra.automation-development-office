# Role: `ocp_compliance_install`

Validate that Compliance Operator pods are present and at least one pod reaches
the Running phase.

## Role Author

Chad Elliott

## ✅ Role Requirements

- OpenShift/Kubernetes API access.
- `kubernetes.core` collection installed.
- Compliance Operator already deployed in the target namespace.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `ocp_compliance_install_operator_namespace` | Namespace to inspect for Compliance Operator pods. | No | `openshift-compliance` |

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_compliance_install
      vars:
        ocp_compliance_install_operator_namespace: openshift-compliance
```

## 🧪 Role Molecule Testing

This role includes a role-local Molecule scenario under `molecule/default/`.
Extension-level Molecule scenario coverage is provided under
`extensions/molecule/integration_ocp_compliance_install`.

## 📁 Role Structure

```text
ocp_compliance_install/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── molecule/
│   └── default/
│       ├── converge.yml
│       ├── destroy.yml
│       ├── molecule.yml
│       ├── README.md
│       ├── TEST.md
│       └── verify.yml
├── README.md
├── tasks/
│   └── main.yml
├── tests/
│   ├── inventory
│   └── roles/
│       └── ocp_compliance_install -> ../..
└── vars/
    └── main.yml
```
