# Role: infra.ado.install_gitlab

Install **standalone GitLab CE/EE** on RHEL via official Omnibus packages
(`packages.gitlab.com`) or an offline RPM.

Prefer **gitlab-ce** when no Enterprise license is available. Set
`install_gitlab_edition: ee` (package `gitlab-ee`) only when licensed.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible 2.16+
- Target: RHEL 8/9 (or compatible) with `become`
- Online: outbound HTTPS to `packages.gitlab.com`, **or**
- Airgap: `install_gitlab_rpm_path` (Contoller path) / `install_gitlab_rpm_url`
- Optional TLS: `install_gitlab_tls_crt` / `install_gitlab_tls_key` (PEM)
- Optional RHN: `install_gitlab_rhn_org_id` / `install_gitlab_rhn_activation_key`
  when the VM needs a subscription for URL/deps (skipped if already registered)

Controller / bootstrap wiring:

- Playbook seed:
  `bootstrap_generate_playbook_repo/files/playbooks/gitlab/ado-install-gitlab-standalone-bootstrap.yml`
- JT seed:
  `bootstrap_controller/files/job_templates/ado-install-gitlab-standalone-bootstrap.jt.yml`
- Component keys: `gitlab` (includes OpenShift operator JTs) and
  `gitlab_standalone` (this role only)
- Prefer inventory host for the GitLab VM with a machine credential

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | Desired state (`present` / `absent`). Default `present`. |
| `install_gitlab_hostname` | GitLab hostname. Required — no default. |
| `install_gitlab_http_port` | HTTP port. Default `80`. |
| `install_gitlab_https_port` | HTTPS port. Default `443`. |
| `install_gitlab_root_password` | Initial root password. Default `redhat123`. |
| `install_gitlab_edition` | Package edition (`ce` or `ee`). Default `ce`. |
| `install_gitlab_external_url` | Omnibus `external_url`; derived from hostname/TLS when empty. |
| `install_gitlab_tls_crt` / `install_gitlab_tls_key` | PEM paths for HTTPS nginx. |
| `install_gitlab_rpm_path` / `install_gitlab_rpm_url` | Offline Omnibus RPM (airgap). |
| `install_gitlab_allow_online_repo` | Allow `packages.gitlab.com` when true. Default `false`. |
| `install_gitlab_skip_packages` | Skip package install (pre-staged deps). Default `false`. |
| `install_gitlab_manage_root_password` | Enforce root password after install. Default `true`. |
| `install_gitlab_rhn_org_id` / `install_gitlab_rhn_activation_key` | Optional RHN registration. |

## 🚀 Role Usage

```yaml
- hosts: gitlab_ado
  become: true
  roles:
    - role: infra.ado.install_gitlab
      vars:
        install_gitlab_hostname: gitlab-ado.server.lab
        install_gitlab_external_url: http://gitlab-ado.server.lab
        install_gitlab_root_password: "{{ vault_gitlab_root_password }}"
        # Optional EE:
        # install_gitlab_edition: ee
        # Airgap:
        # install_gitlab_rpm_path: /var/tmp/gitlab-ce-*.rpm
        # Optional TLS:
        # install_gitlab_tls_crt: /path/to/cert.pem
        # install_gitlab_tls_key: /path/to/key.pem
```

Initial root password is written to `/etc/gitlab/gitlab.rb`
(`gitlab_rails['initial_root_password']`), matching the Omnibus
`GITLAB_ROOT_PASSWORD` first-boot pattern. Reconfigure via `gitlab-ctl`.

## 🧪 Role Molecule Testing

No dedicated Molecule scenario. Validate on a lab RHEL VM with the standalone
bootstrap playbook or Controller JT **ADO | Install GitLab Standalone**.

```bash
ansible-playbook playbooks/gitlab/ado-install-gitlab-standalone-bootstrap.yml \
  -e env=prod \
  --vault-password-file .vault_pass
```

## 📁 Role Structure

```text
roles/install_gitlab/
  README.md
  defaults/
  meta/
  tasks/
    main.yml
```
