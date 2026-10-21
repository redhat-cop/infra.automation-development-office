# Role: infra.automation_development_office.jira

Jira automation role. Primary tasks include: Jira | Validate required vars; Jira | Build list of template files for selected track; Jira | Process templates for track.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `jira_story_issuetype` | Role input variable used to configure automation behavior. |
| `jira_subtask_issuetype` | Role input variable used to configure automation behavior. |
| `jira_create_subtasks` | Role input variable used to configure automation behavior. |
| `jira_templates_dir` | Role input variable used to configure automation behavior. |
| `jira_feature_key` | Role input variable used to configure automation behavior. |

## 🚀 Role Usage

```yaml
- name: Run jira
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.jira
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Jira | Validate required vars
- Jira | Build list of template files for selected track
- Jira | Process templates for track
- Jira Set section for this template batch

```bash
cd roles/jira
molecule test
```

## 📁 Role Structure

```text
roles/jira/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
