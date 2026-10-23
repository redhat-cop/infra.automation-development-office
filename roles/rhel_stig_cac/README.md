# Role: infra.automation_development_office.rhel_stig_cac

Apply DISA STIG Compliance-as-Code (CaC) on RHEL 8, 9, and 10 hosts using
`scap-security-guide` and OpenSCAP.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core 2.16 or later
- Target host: RHEL 8, 9, or 10 with `become: true`
- Network access to install RPMs (`scap-security-guide`, `openscap-scanner`,
  `openscap-utils`) from enabled repositories
- Sufficient privileges to apply STIG remediations when
  `rhel_stig_cac_remediate` is `true`

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `rhel_stig_cac_remediate` | When `true`, run OpenSCAP with `--remediate`. When `false`, evaluate only. | No | `true` |
| `rhel_stig_cac_profile_label` | Preflight/JT label such as `RHEL 9 STIG` used to pick content when OS major is not forced. | No | `""` |
| `rhel_stig_cac_os_major` | Force content major version (`8`, `9`, or `10`). Empty uses label map or host facts. | No | `""` |
| `rhel_stig_cac_xccdf_profile` | XCCDF profile ID from scap-security-guide. | No | `xccdf_org.ssgproject.content_profile_stig` |
| `rhel_stig_cac_packages` | RPM packages providing CaC content and OpenSCAP. | No | see `defaults/main.yml` |
| `rhel_stig_cac_results_dir` | Directory for XML results and HTML reports. | No | `/var/log/ado-stig-cac` |

## 🚀 Role Usage

Use with the STIG hardening bootstrap playbook and set `stig_engine: cac`:

```yaml
- name: Apply RHEL STIG hardening with DISA CaC
  hosts: rhel_servers
  become: true
  gather_facts: true
  vars:
    stig_engine: cac
    stig_profile: RHEL 9 STIG
    rhel_stig_cac_remediate: true
  roles:
    - role: infra.automation_development_office.rhel_stig_cac
      vars:
        rhel_stig_cac_profile_label: "{{ stig_profile }}"
```

Scan-only example:

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: infra.automation_development_office.rhel_stig_cac
      vars:
        rhel_stig_cac_profile_label: RHEL 10 STIG
        rhel_stig_cac_remediate: false
```

## Behavior Notes

- OpenSCAP exit codes `0` and `2` are treated as success (`2` indicates findings).
- CaC content paths are resolved from RHEL major version:
  - Datastream: `/usr/share/xml/scap/ssg/content/ssg-rhel{N}-ds.xml`
  - Ansible playbook (reference): `/usr/share/scap-security-guide/ansible/rhel{N}-playbook-stig.yml`
- For RHEL System Roles STIG instead of CaC, use `stig_engine: system_role` with
  `infra.automation_development_office.rhel_ext_system_roles`.

## 🧪 Role Molecule Testing

Discuss Molecule coverage with the ADO team before adding a scenario. For local
validation, run against a lab RHEL host with scan-only mode first:

```bash
ansible-playbook -i inventory playbooks/rhel/ado-stig-hardening-bootstrap.yml \
  -e stig_engine=cac -e rhel_stig_cac_remediate=false
```

## 📁 Role Structure

```text
rhel_stig_cac/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── README.md
├── tasks/
│   └── main.yml
└── vars/
    └── main.yml
```
