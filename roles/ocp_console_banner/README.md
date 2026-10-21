# Role: `ocp_console_banner`

Manage OpenShift console notification banners using `ConsoleNotification` resources.

## Role Author

Chad Elliott

## ✅ Role Requirements

- OpenShift/Kubernetes API access.
- `kubernetes.core` collection installed.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `state` | Desired state. Use `add`, `update`, or `delete`; legacy `present`, `new`, and `absent` are also accepted. | No | `present` |
| `ocp_console_banner_text` | Banner text content. | Yes* | N/A |
| `ocp_console_banner_name` | Fixed banner name used by the `new` workflow. | No | `ado-banner` |
| `ocp_console_banner_name_prefix` | Prefix used to identify ADO-managed banners. | No | `ado-banner` |
| `ocp_console_banner_location` | Banner location in the console UI. | No | `BannerTop` |
| `ocp_console_banner_background_color` | Banner background color. | No | `#1f7a1f` |
| `ocp_console_banner_text_color` | Banner text color. | No | `#ffffff` |

> **Notes:**
> \* Required when `state` is `add`, `update`, `present`, or `new`.

## 🚀 Role Usage

```yaml
- name: ADO | Configure OpenShift console banner
  hosts: localhost
  gather_facts: false
  vars:
    component: common
    console_banner_text: Hello! RHLAB OpenShift | Production
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_{{ component }}.yml
    - group_vars/all/{{ env }}/vars_{{ component }}.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  pre_tasks:
    - name: ADO | Resolve vars for component from framework defaults + env overrides
      ansible.builtin.include_role:
        name: infra.automation_development_office.bootstrap_resolve_component
    - name: ADO | Resolve_component | Debug key winners
      ansible.builtin.debug:
        msg:
          - console_banner_text (final) = {{ console_banner_text | default('UNDEF') }}
          - bootstrap_resolve_component_selected.console_banner_text = {{ bootstrap_resolve_component_selected.console_banner_text | default('UNDEF') }}
  roles:
    - role: infra.automation_development_office.ocp_console_banner
```

## Behavior Notes

- The `add`/`present` path creates a deterministic per-message banner if one does not already exist.
- The `update`/`new` path deletes existing ADO-managed banners before creating a single replacement banner.
- The `delete`/`absent` path only removes ADO-managed banners matched by label or prefix.

## 🧪 Role Molecule Testing

This role has two Molecule paths:

- Role-local scenario at `roles/ocp_console_banner/molecule/default`.
- Extension-level scenario at `extensions/molecule/integration_ocp_console_banner`
  using shared playbooks in `extensions/molecule/utils/playbooks`.

Run the extension scenario from `extensions/molecule`:

```bash
molecule test -s integration_ocp_console_banner
```

## 📁 Role Structure

```text
ocp_console_banner/
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
│   └── inventory
└── vars/
    └── main.yml
```

## License

GPL-3.0-or-later
