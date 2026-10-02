# Role: infra.ado.gitlab_install

Install and configure GitLab on OpenShift using the GitLab Operator and Custom Resource (CR).

- Creates Kubernetes Secrets for TLS, root password, and Postgres credentials
- Deploys the GitLab Operator CR with required references and settings
- Supports idempotent updates and safe deletion
- Uses **Ansible Vault** for storing sensitive secrets (root and DB passwords)

---

## Role Author

- Chad Elliott (<chelliot@redhat.com>)
- Automation Development Office

---

## ✅ Role Requirements

- OpenShift API reachable with auth (`K8S_AUTH_*` env vars or module params)
- Collections:
  - `kubernetes.core`
- GitLab Operator installed and CRDs available in the target cluster
- Secrets managed with Ansible Vault
- Optional CLIs for verification: `oc`, `kubectl`, `jq`

---

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `state` | Desired state (`present` to install, `absent` to remove). Default: `present`. |
| `name_space` | Namespace to deploy GitLab and all resources. **Required.** |
| `gitlab_install_validate_certs` | TLS verification for k8s modules. Default: `false`. |
| `gitlab_install_hostname` | Hostname for GitLab (used in Route/service). **Required when `state` is `present`.** |
| `gitlab_install_storage_size` | Size for GitLab persistent volume. **Required when `state` is `present`.** |
| `gitlab_install_storage_class` | StorageClass for GitLab persistent volume. **Required when `state` is `present`.** |
| `gitlab_install_tls_crt` | TLS certificate for HTTPS endpoint. **Required when `state` is `present`.** |
| `gitlab_install_tls_key` | TLS private key for HTTPS endpoint. **Required when `state` is `present`.** |
| `gitlab_install_admin_user` | GitLab DB/Postgres admin username. Default: `admin`. |
| `gitlab_install_admin_password` | GitLab DB/Postgres admin password. **Required when `state` is `present`.** |
| `gitlab_install_root_password` | GitLab root (web UI) password. **Required when `state` is `present`.** |
| `gitlab_install_chart_version` | GitLab chart version for the operator CR. Default: `9.4.0`. |

### Auth via environment (optional)

Set kube auth via environment before running Molecule or playbooks:

```bash
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="…"
export K8S_AUTH_VERIFY_SSL="no"
```

> **Notes**
> - Passwords should be stored in Ansible Vault (`group_vars/all/vault.yml` or similar)
> - TLS data should be provided as variables or loaded from files

---

## 🚀 Role Usage

### Minimal install

```yaml
- hosts: localhost
  gather_facts: false
  vars_files:
    - group_vars/all/vault.yml
  vars:
    name_space: gitlab
    gitlab_install_hostname: "gitlab.apps.example.com"
    gitlab_install_storage_size: "20Gi"
    gitlab_install_storage_class: "gp2-csi"
    gitlab_install_tls_crt: "{{ lookup('file', 'files/gitlab.crt') }}"
    gitlab_install_tls_key: "{{ lookup('file', 'files/gitlab.key') }}"
  roles:
    - role: infra.ado.gitlab_install
```

### Vaulted secrets

```yaml
# group_vars/all/vault.yml (encrypted with ansible-vault)
gitlab_install_admin_user: admin
gitlab_install_admin_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...encrypted data...
gitlab_install_root_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...encrypted data...
```

### Uninstall

```yaml
- hosts: localhost
  gather_facts: false
  vars:
    name_space: gitlab
    state: absent
  roles:
    - role: infra.ado.gitlab_install
```

---

### Behavior Notes

- All referenced secrets and config are created before the Custom Resource.
- The chart version defaults to a supported version (`9.4.0`). Override with `gitlab_install_chart_version` if needed.
- The operator CR is updated if settings change.
- Passwords are **never logged** (`no_log: true`).
- For deletion, the role removes the GitLab CR, PostgreSQL resources, and secrets.

---

## 🧪 Role Molecule Testing

The Molecule scenario lives at `extensions/molecule/gitlab_install`.

CI runs the `verify` stage to validate this README and role layout. Full cluster
integration (converge, idempotence, destroy) requires OpenShift credentials via
`K8S_AUTH_*` environment variables.

Run from the extensions Molecule directory:

```bash
cd extensions/molecule
ln -sfn . molecule
molecule test -s gitlab_install
```

For full integration against a cluster:

```bash
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="..."
export K8S_AUTH_VERIFY_SSL="no"
molecule converge -s gitlab_install
molecule idempotence -s gitlab_install
molecule verify -s gitlab_install
molecule destroy -s gitlab_install
```

---

## 📁 Role Structure

```text
gitlab_install/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   ├── argument_specs.yml
│   └── main.yml
├── README.md
├── tasks/
│   ├── delete-gitlab-operator.yml
│   ├── install-gitlab-operator.yml
│   └── main.yml
├── tests/
│   ├── inventory
│   └── test.yml
└── vars/
    └── main.yml
```

The default chart is 10.3.2. Match `gitlab_install_chart_version` to a version supported by the installed GitLab Operator; existing explicit chart selections remain authoritative.
