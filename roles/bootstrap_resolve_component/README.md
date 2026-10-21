# Role: infra.automation_development_office.bootstrap_resolve_component

Resolve one bootstrap component into the effective variable set used by its
generated playbook.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- `component` set to a key in the bootstrap component registry
- Optional `components_env` and `components_override` dictionaries for
  environment-specific or runtime overrides
- Component registry data from `files/components_defaults.yml`

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `component` | Component key to resolve from the registry. |
| `components_env` | Environment-level component overrides merged after registry defaults. |
| `components_override` | Runtime overrides merged after `components_env`. |
| `bootstrap_resolve_component_debug` | Dumps the registry, override, and selected values when true. |
| `bootstrap_resolve_component_selected` | Fact containing the merged component configuration. |
| `bootstrap_resolve_component_aliases` | Alias map loaded from the component registry. |

## 🚀 Role Usage

```yaml
- name: Resolve Grafana bootstrap component
  hosts: localhost
  gather_facts: false
  vars:
    component: grafana
    components_env:
      grafana:
        namespace: grafana
  roles:
    - role: infra.automation_development_office.bootstrap_resolve_component
```

## 🧪 Role Molecule Testing

Validate with a known component name and assert that expected component facts
are exported without clobbering higher-precedence variables.

```bash
ansible-lint --offline roles/bootstrap_resolve_component
yamllint roles/bootstrap_resolve_component/tasks
```

## 📁 Role Structure

```text
roles/bootstrap_resolve_component/
  defaults/main.yml
  files/components_defaults.yml
  tasks/main.yml
  vars/main.yml
  README.md
```
