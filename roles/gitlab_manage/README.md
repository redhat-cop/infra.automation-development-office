# Role: infra.automation_development_office.gitlab_manage

Manage GitLab issues, branches, users, and project membership through the
GitLab REST API (`ansible.builtin.uri`).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible 2.14+
- Network access to the GitLab API
- A GitLab personal/project access token with scopes appropriate to the action
  (`api`, and admin rights for user create/block)

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `gitlab_manage_api_url` | GitLab base URL (no `/api/v4` suffix). **Required.** |
| `gitlab_manage_api_token` | API token. **Required.** |
| `gitlab_manage_action` | One of `issue_create`, `issue_update`, `issue_close`, `branch_create`, `branch_delete`, `user_create`, `user_absent`, `user_blocked`, `member_present`, `member_absent`. **Required.** |
| `gitlab_manage_project` | Project path (`group/project`) or ID. Required for issue/branch/member actions. |
| `gitlab_manage_validate_certs` | Verify TLS (default `true`). |
| `gitlab_manage_issue_title` | Issue title (create/update/close-by-title). |
| `gitlab_manage_issue_description` | Issue body (create/update). |
| `gitlab_manage_issue_iid` | Issue IID when closing a known issue. |
| `gitlab_manage_branch_name` | Branch name. |
| `gitlab_manage_ref_branch` | Source branch for create (default `main`). |
| `gitlab_manage_user_username` / `_name` / `_email` / `_password` | User fields. |
| `gitlab_manage_member_username` | Username for project membership. |
| `gitlab_manage_member_access_level` | `guest`, `reporter`, `developer`, `maintainer`, or `owner`. |

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.gitlab_manage
      vars:
        gitlab_manage_api_url: https://gitlab.example.test
        gitlab_manage_api_token: "{{ vault_gitlab_api_token }}"
        gitlab_manage_action: issue_create
        gitlab_manage_project: group/project
        gitlab_manage_issue_title: Follow up on bootstrap
        gitlab_manage_issue_description: Created by ADO Contoller
```

Contoller job templates:

- `ADO | GitLab Manage Issue`
- `ADO | GitLab Manage Branch`
- `ADO | GitLab Manage User`
- `ADO | GitLab Manage Project Member`

## 🧪 Role Molecule Testing

No dedicated Molecule scenario yet. Validate with Contoller survey launches or a
local playbook against a disposable GitLab project.

## 📁 Role Structure

```text
roles/gitlab_manage/
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
  tasks/issue.yml
  tasks/issue_close.yml
  tasks/branch.yml
  tasks/user.yml
  tasks/member.yml
  README.md
```
