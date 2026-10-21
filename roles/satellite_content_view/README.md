# Role: satellite_content_view

Manages Red Hat Satellite Content Views with three actions: `create`, `publish`,
and `promote`.

---

## Role Author

- Jeff Radabaugh
- Chris Kirk

---

## ✅ Role Requirements

- Ansible 2.9 or newer
- **`redhat.satellite` collection** — provides `content_view` and
  `content_view_version` modules (install from
  [Red Hat Automation Hub](https://console.redhat.com/ansible/automation-hub))
- Connectivity from controller to Satellite API
- Valid Satellite credentials with permissions for Content View operations

Install the collection (Automation Hub access required):

```bash
ansible-galaxy collection install redhat.satellite
```

Role entrypoint `tasks/main.yml` dispatches by `sat_content_view_action`:

1. `create` -> imports `tasks/create_content_view.yml`
2. `publish` -> imports `tasks/publish_content_view.yml`
3. `promote` -> imports `tasks/promote_content_view.yml`

No task file runs unless both `content_view` and `sat_content_view_action` are
defined.

---

## 📦 Role Variables

| Variable | Description | Required For |
| --- | --- | --- |
| `sat_content_view_action` | Action selector. Supported values: `create`, `publish`, `promote`. | All |
| `satellite_url` | URL of the Satellite server. | All |
| `satellite_username` | Satellite username. | All |
| `satellite_password` | Satellite password. | All |
| `organization` | Satellite organization name. | All |
| `content_view` | Name of the Satellite Content View. | All |
| `lifecycle_environments` | Target lifecycle environment(s). | Promote |
| `published_content_view` | Compatibility variable currently validated in promote flow. | Promote |
| `published_content_view_version` | Content View version to promote. | Promote |

### Returned runtime variables

- `satellite_content_view_create_result` (create action)
- `satellite_content_view_publish_result` (publish action)
- `satellite_content_view_promote_result` (promote action)

---

## 🚀 Role Usage

### Bootstrap Usage

```yaml
- name: ADO | Manage Satellite content views
  hosts: all
  gather_facts: true
  roles:
    - role: infra.automation_development_office.satellite_content_view
```

### Create Content View

```yaml
- name: Create Satellite Content View
  hosts: localhost
  gather_facts: false
  roles:
    - role: satellite_content_view
      sat_content_view_action: create
      satellite_url: "https://satellite.example.com"
      satellite_username: "admin"
      satellite_password: "password"
      organization: "MyOrg"
      content_view: "RHEL8_Base"
```

### Publish Content View

```yaml
- name: Publish Satellite Content View
  hosts: localhost
  gather_facts: false
  roles:
    - role: satellite_content_view
      sat_content_view_action: publish
      satellite_url: "https://satellite.example.com"
      satellite_username: "admin"
      satellite_password: "password"
      organization: "MyOrg"
      content_view: "RHEL8_Base"
```

### Promote Content View

```yaml
- name: Promote Satellite Content View
  hosts: localhost
  gather_facts: false
  roles:
    - role: satellite_content_view
      sat_content_view_action: promote
      satellite_url: "https://satellite.example.com"
      satellite_username: "admin"
      satellite_password: "password"
      organization: "MyOrg"
      content_view: "RHEL8_Base"
      lifecycle_environments:
        - "Library"
        - "Dev"
      published_content_view: "RHEL8_Base"
      published_content_view_version: "1.0"
```

---

## 🧪 Role Molecule Testing

Extension-level Molecule scenarios under `extensions/molecule/`:

| Scenario | Action | Command |
| --- | --- | --- |
| `integration_satellite_content_view_create` | create | `molecule test -s integration_satellite_content_view_create` |
| `integration_satellite_content_view_publish` | publish | `molecule test -s integration_satellite_content_view_publish` |
| `integration_satellite_content_view_promote` | promote | `molecule test -s integration_satellite_content_view_promote` |

Playbooks live in `extensions/molecule/utils/playbooks/` (`satellite_content_view_*`).

Pull requests run all extension scenarios automatically. To run only these
scenarios from the **Ansible Collection CI/CD** workflow dispatch UI, enable:

- `Run integration_satellite_content_view_create`
- `Run integration_satellite_content_view_publish`
- `Run integration_satellite_content_view_promote`

Export Satellite credentials before running full integration (prepare/converge/destroy):

```bash
export SATELLITE_URL="https://satellite.example.com"
export SATELLITE_USERNAME="admin"
export SATELLITE_PASSWORD="your-password"
export SATELLITE_ORGANIZATION="MyOrg"
export SATELLITE_CONTENT_VIEW="molecule-satellite-content-view"
```

Run from the collection `extensions/molecule` directory:

```bash
cd extensions/molecule
ln -sfn . molecule
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections"
export ANSIBLE_ROLES_PATH="/path/to/ado/roles"
molecule test -s integration_satellite_content_view_create
```

For full integration against Satellite (install `redhat.satellite` from Red Hat Automation Hub first):

```bash
ansible-galaxy collection install redhat.satellite
export SATELLITE_URL="https://satellite.example.com"
export SATELLITE_USERNAME="admin"
export SATELLITE_PASSWORD="your-password"
export SATELLITE_ORGANIZATION="MyOrg"
molecule prepare -s integration_satellite_content_view_create
molecule converge -s integration_satellite_content_view_create
molecule idempotence -s integration_satellite_content_view_create
molecule verify -s integration_satellite_content_view_create
molecule destroy -s integration_satellite_content_view_create
```

The destroy playbook skips automatically when `SATELLITE_*` credentials are not
set, so CI verify-only runs do not require `redhat.satellite`.

See `extensions/molecule/integration_satellite_content_view_create/README.md`
and `TEST.md` for details.

---

## 📁 Role Structure

```text
roles/satellite_content_view/
  README.md
  defaults/main.yml
  handlers/main.yml
  meta/main.yml
  tasks/main.yml
  tasks/create_content_view.yml
  tasks/publish_content_view.yml
  tasks/promote_content_view.yml
  tests/inventory
  vars/main.yml

extensions/molecule/
  integration_satellite_content_view_create/
  integration_satellite_content_view_publish/
  integration_satellite_content_view_promote/
  utils/playbooks/satellite_content_view_*.yml
```

---

## License

GPL-3.0-or-later
