# Role: infra.automation_development_office.gitlab_manage

Manage GitLab issues, branches, users, and project membership through the
GitLab REST API (`ansible.builtin.uri`). Also supports onboard validation,
issue comments, and membership verification for AAP approval workflows.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible 2.14+
- Network access to the GitLab API
- A GitLab personal/project access token with scopes appropriate to the action
  (`api`, and admin rights for user create/block)
- Contoller/bootstrap projects should load shared connection settings from
  `group_vars/all/vars.yml` and `group_vars/all/vault_gitlab_manage.yml`

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `gitlab_manage_api_url` | GitLab base URL (no `/api/v4` suffix). **Required.** |
| `gitlab_manage_api_token` | API token. **Required.** Prefer vault. |
| `gitlab_manage_action` | See actions below. **Required.** |
| `gitlab_manage_project` | Project path (`group/project`) or ID. |
| `gitlab_manage_validate_certs` | Verify TLS (default `true`). |
| `gitlab_manage_issue_title` | Issue title (create/update/close-by-title). Exact match; `issue_create` fails if it already exists, `issue_update` fails if missing. |
| `gitlab_manage_issue_description` | Issue body (create/update). |
| `gitlab_manage_issue_labels` | Optional label list sent on create/update. |
| `gitlab_manage_issue_assignees` | Optional GitLab user ID list (`assignee_ids`) on create/update. |
| `gitlab_manage_issue_comment` | Markdown comment body (`issue_comment`). |
| `gitlab_manage_issue_iid` | Issue IID (close/comment/onboard). |
| `gitlab_manage_branch_name` | Branch name. |
| `gitlab_manage_ref_branch` | Source branch for create (default `main`). |
| `gitlab_manage_user_username` / `_name` / `_email` / `_password` | User fields. |
| `gitlab_manage_member_username` | Username for project membership. |
| `gitlab_manage_member_access_level` | `guest`, `reporter`, `developer`, `maintainer`, or `owner`. |

### Actions

`issue_create`, `issue_update`, `issue_close`, `issue_comment`,
`branch_create`, `branch_delete`, `user_create`, `user_absent`, `user_blocked`,
`member_present`, `member_absent`, `onboard_validate`, `verify_member`

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  vars_files:
    - group_vars/all/vars.yml
    - group_vars/all/vault_gitlab_manage.yml
  roles:
    - role: gitlab_manage
      vars:
        gitlab_manage_action: issue_create
        gitlab_manage_issue_title: Follow up on bootstrap
```

Contoller templates:

- `ADO | GitLab Manage Issue|Branch|User|Project Member`
- `ADO | GitLab Onboard Validate|Comment|Verify|Finalize|Failed`
- Workflow: `ADO | GitLab Onboard Workflow` (native AAP approval node)

## 🧪 Role Molecule Testing

No dedicated Molecule scenario yet. Validate with Contoller workflow launches
against a disposable GitLab project/issue.

## 📁 Role Structure

```text
roles/gitlab_manage/
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
  tasks/issue.yml
  tasks/issue_close.yml
  tasks/issue_comment.yml
  tasks/branch.yml
  tasks/user.yml
  tasks/member.yml
  tasks/onboard_validate.yml
  tasks/verify_member.yml
  README.md
```
