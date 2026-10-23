# Role: `infra.automation_development_office.aap_configuration`

Collect user-provided AAP configuration files and dispatch them to the upstream `infra.aap_configuration.dispatch` role for processing.

This role provides a lightweight wrapper that centralizes configuration files under the role path and sets the expected `aap_configuration_config_path` when calling the dispatcher.

## Role Author

- Chad Elliott
- Automation Development Office

## ✅ Role Requirements

- Ansible >= 2.16.0 (declared in `meta/main.yml`)
- No role dependencies are declared in `meta/main.yml`
- The upstream `infra.aap_configuration.dispatch` role must be available on the controller or in `ANSIBLE_ROLES_PATH` / `ANSIBLE_COLLECTIONS_PATHS` at runtime
- Configuration input is supplied as one or more `*.yml` files in a `configs` directory alongside your playbook

### Required collections

Install the following Ansible Galaxy collections before using this role:

```yaml
collections:
  - name: ansible.platform
  - name: ansible.hub
  - name: ansible.controller
    version: ">=4.6.0"
  - name: ansible.eda
  - name: infra.aap_configuration
```

Install with the Ansible Galaxy CLI:

```bash
ansible-galaxy collection install -r requirements.yml
```

Or install individually, for example:

```bash
ansible-galaxy collection install ansible.controller:>=4.6.0
```

### Extends collection

This role extends the `infra.aap_configuration` collection and delegates configuration processing to that collection's dispatcher. For full documentation of available features, variables, examples, and advanced usage, refer to the collection README:

https://galaxy.ansible.com/ui/repo/published/infra/aap_configuration/

## 📦 Role Variables

This role does not define role-specific defaults. Configuration is supplied through YAML files copied from `{{ playbook_dir }}/configs` into `{{ role_path }}/configs` and loaded with `include_vars`.

| Variable | Description |
|---------|-------------|
| `aap_configuration_config_path` | Path passed to `infra.aap_configuration.dispatch`. Set automatically to `{{ role_path }}/configs` when the dispatcher role is invoked. |
| Config file variables | Keys defined in one or more `*.yml` files placed in a `configs` directory next to your playbook. Files matching `*.yml` are copied into the role's `configs` directory and loaded before dispatch runs. |

To customize behavior, provide properly named keys in your config YAML files or wrap this role in a controlling playbook that sets additional variables.

## 🚀 Role Usage

Create a `configs` directory next to your playbook and add one or more `*.yml` files (for example `configs/aap.example.yml`). Then call the role in a playbook.

When the role runs it will:

- Create `roles/aap_configuration/configs` if missing
- Copy `configs/*.yml` from the playbook tree into the role-local `configs` directory
- Include variables from those files and invoke `infra.aap_configuration.dispatch` with the copied config path

### Basic usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_configuration
```

### Example with a config file

Place configuration in `configs/aap.example.yml` next to your playbook:

```yaml
# configs/aap.example.yml
# Add keys expected by infra.aap_configuration.dispatch
```

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_configuration
```

### Behavior notes

- Copies YAML files from `{{ playbook_dir }}/configs` into `{{ role_path }}/configs`
- Loads all variables from the copied config files using `include_vars`
- Calls the upstream dispatcher role using `include_role`:
  - role: `infra.aap_configuration.dispatch`
  - sets `aap_configuration_config_path` to `{{ role_path }}/configs`
- This role is intentionally lightweight: it acts as a coordinator that delegates the heavy lifting to `infra.aap_configuration.dispatch`. To debug behavior, inspect the copied files under `roles/aap_configuration/configs` and the logs from the upstream dispatcher role.

Key implementation files:

- `tasks/main.yml`: entrypoint that imports `dispatch.yml`
- `tasks/dispatch.yml`: gathers and copies config files, loads them, and calls the upstream dispatcher

## 🧪 Role Molecule Testing

Use the extension integration scenario at
`extensions/molecule/integration_aap_configuration`.

Install the collection and dependencies before running locally:

```bash
cd /path/to/your/git/checkout/ado
ansible-galaxy collection install . --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:${ANSIBLE_COLLECTIONS_PATH:-}"
```

Run the integration scenario:

```bash
cd extensions/molecule
molecule test -s integration_aap_configuration
```

By default the scenario uses a mock `infra.aap_configuration.dispatch` role.
Set `AAP_CONFIGURATION_ENABLE_LIVE_CHECKS=true` to run against a real
`infra.aap_configuration` installation.

## 📁 Role Structure

```text
roles/
└─ aap_configuration/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ handlers/
   │  └─ main.yml
   ├─ meta/
   │  └─ main.yml
   ├─ tasks/
   │  ├─ dispatch.yml
   │  └─ main.yml
   ├─ tests/
   │  └─ inventory
   └─ vars/
      └─ main.yml
```

**License:** GPL-3.0-or-later (see `meta/main.yml`)

Open issues or PRs to add configuration examples, expand documentation, or add integration tests. Follow the repository contribution guidelines.
