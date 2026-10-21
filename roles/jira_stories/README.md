# Role: infra.automation_development_office.jira_stories

Jira Stories automation role. Primary tasks include: Jira | Normalize legacy and CLI vars; Jira | Validate required vars; Jira | Build list of template files for selected track.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `jira_stories_story_issuetype` | Role input variable used to configure automation behavior. |
| `jira_stories_subtask_issuetype` | Role input variable used to configure automation behavior. |
| `jira_stories_create_subtasks` | Role input variable used to configure automation behavior. |
| `jira_stories_templates_dir` | Role input variable used to configure automation behavior. |
| `jira_stories_feature_key` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: ADO | Create Jira Stories
  hosts: localhost
  gather_facts: false
  vars:
    component: jira
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
  roles:
    - role: infra.automation_development_office.jira_stories
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Jira | Normalize legacy and CLI vars
- Jira | Validate required vars
- Jira | Build list of template files for selected track
- Jira | Process templates for track

```bash
cd roles/jira_stories
molecule test
```

## 📁 Role Structure

```text
roles/jira_stories/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
