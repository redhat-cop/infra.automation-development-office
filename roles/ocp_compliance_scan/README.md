# Role: `ocp_compliance_scan`

Create Compliance Operator scan resources for scheduled or immediate scan execution.

## Role Author

Chad Elliott

## ✅ Role Requirements

- OpenShift/Kubernetes API access.
- `kubernetes.core` collection installed.
- Compliance Operator CRDs installed in the target cluster.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `ocp_compliance_scan_schedule_scan` | Boolean toggle to create a `ComplianceScan` resource. | No | `false` |
| `ocp_compliance_scan_run_scan` | Boolean toggle to create a `ComplianceSuite` resource. | No | `false` |
| `ocp_compliance_scan_scan_name` | Name of the `ComplianceScan` resource. | Yes* | `""` |
| `ocp_compliance_scan_suite_name` | Name of the `ComplianceSuite` resource. | Yes** | `""` |
| `ocp_compliance_scan_profile` | Compliance profile referenced by the scan. | Yes* | `""` |
| `ocp_compliance_scan_operator_namespace` | Namespace for Compliance Operator resources. | No | `openshift-compliance` |
| `ocp_compliance_scan_content_image` | Compliance content image used for scans. | No | `quay.io/complianceascode/content:latest` |

> **Notes:**
> \* Required when `ocp_compliance_scan_schedule_scan` is `true`.
> \*\* Required when `ocp_compliance_scan_run_scan` is `true`.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_compliance_scan
      vars:
        ocp_compliance_scan_schedule_scan: true
        ocp_compliance_scan_run_scan: true
        ocp_compliance_scan_scan_name: daily-node-scan
        ocp_compliance_scan_suite_name: daily-suite
        ocp_compliance_scan_profile: ocp4-cis
        ocp_compliance_scan_operator_namespace: openshift-compliance
```

## 🧪 Role Molecule Testing

This role currently includes a local Molecule scenario under `molecule/default/`.
Extension-level Molecule scenario coverage is provided under
`extensions/molecule/integration_ocp_compliance_scan`.

## 📁 Role Structure

```text
ocp_compliance_scan/
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
│   └── test.yml
└── vars/
    └── main.yml
```
