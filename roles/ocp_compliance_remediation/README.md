# Role: `ocp_compliance_remediation`

Trigger an ACS remediation request by calling the ACS API when remediation is
enabled.

## Role Author

Chad Elliott

## ✅ Role Requirements

- Network access from the automation controller to the ACS API endpoint.
- A valid ACS bearer token.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `ocp_compliance_remediation_enabled` | Boolean toggle. When `true`, the API call is made. | No | `false` |
| `ocp_compliance_remediation_acs_api_url` | ACS API host or endpoint used to build the remediation URL. | Yes* | `""` |
| `ocp_compliance_remediation_acs_token` | Bearer token used for ACS authentication. | Yes* | `""` |
| `ocp_compliance_remediation_profile` | Compliance profile value sent in the request body. | Yes* | `""` |
| `ocp_compliance_remediation_scan_id` | Scan identifier sent in the request body. | Yes* | `""` |

> **Notes:**
> \* Required when `ocp_compliance_remediation_enabled` is `true`.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_compliance_remediation
      vars:
        ocp_compliance_remediation_enabled: true
        ocp_compliance_remediation_acs_api_url: acs.example.com
        ocp_compliance_remediation_acs_token: "{{ vault_acs_token }}"
        ocp_compliance_remediation_profile: ocp4-cis
        ocp_compliance_remediation_scan_id: latest-scan
```

## Behavior Notes

- Uses `ansible.builtin.uri` to post to the ACS remediation endpoint.
- When `ocp_compliance_remediation_enabled` is `false`, the role performs no API
  change.

## 🧪 Role Molecule Testing

Extension-level Molecule scenario coverage is provided under
`extensions/molecule/integration_ocp_compliance_remediation`.

From `extensions/molecule`:

```bash
molecule test -s integration_ocp_compliance_remediation
```

## 📁 Role Structure

```text
ocp_compliance_remediation/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   └── main.yml
├── tests/
│   ├── inventory
│   └── test.yml
└── vars/
    └── main.yml
```
