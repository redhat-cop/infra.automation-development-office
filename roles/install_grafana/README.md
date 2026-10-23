# Role: infra.automation_development_office.install_grafana

Install **standalone Grafana** on RHEL via the official Grafana RPM repository
or an offline RPM.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible 2.16+
- Target: RHEL 8/9 (or compatible) with `become`
- Online: outbound HTTPS to `rpm.grafana.com`, **or**
- Airgap: `install_grafana_rpm_path` (Contoller path) / `install_grafana_rpm_url`

## 📦 Role Variables

See `defaults/main.yml`. Common overrides:

| Variable | Description |
|----------|-------------|
| `install_grafana_hostname` | Grafana `server.domain` / public hostname |
| `install_grafana_http_port` | HTTP listen port (default `3000`) |
| `install_grafana_admin_user` | Local admin username |
| `install_grafana_admin_password` | Local admin password |
| `install_grafana_skip_packages` | Skip package install when true |
| `install_grafana_rpm_path` / `install_grafana_rpm_url` | Offline RPM path or URL |

Contoller / bootstrap:

- Playbook seed:
  `bootstrap_generate_playbook_repo/files/playbooks/grafana/ado-install-grafana-standalone-bootstrap.yml`
- JT seed:
  `bootstrap_controller/files/job_templates/ado-install-grafana-standalone-bootstrap.jt.yml`
- Component keys: `grafana` (includes OpenShift operator JTs) and
  `grafana_standalone` (this role only)
- Prefer inventory host for the Grafana VM with a machine credential

## 🚀 Role Usage

```yaml
- hosts: grafana_ado
  become: true
  roles:
    - role: infra.automation_development_office.install_grafana
      vars:
        install_grafana_hostname: grafana-ado.server.lab
        install_grafana_http_port: 3000
        install_grafana_admin_user: admin
        install_grafana_admin_password: "{{ vault_grafana_admin_password }}"
        # Airgap:
        # install_grafana_rpm_path: /var/tmp/grafana-*.rpm
```

The role writes `[server]` / `[security]` into `grafana.ini`, enables the
`grafana-server` systemd unit, and resets the admin password with
`grafana-cli` when available.

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via the standalone
Grafana bootstrap JT after env generation.

## 📁 Role Structure

```text
roles/install_grafana/
  README.md
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
```
