# Role: infra.ado.terraform

Run Terraform or OpenTofu init, plan, apply, or destroy for a bootstrap stack.

## Role Author

- Automation Development Office

## ✅ Role Requirements

- Ansible >= 2.16
- `terraform` or `tofu` on PATH of the target host or execution environment
- A Terraform root module (one or more `*.tf` files) in the stack directory
- A remote backend for `apply` and `destroy` when this role runs from Ansible
  Automation Platform (execution environments are ephemeral)

The default ADO execution environment does not yet include a Terraform binary.
Install it in `ado-ee` (or a custom EE) before running Contoller job templates.

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `terraform_bin` | Executable name or path. Default `terraform` (use `tofu` for OpenTofu). |
| `terraform_action` | Subcommand after init: `init`, `validate`, `plan`, `apply`, or `destroy`. Default `plan`. |
| `terraform_stack` | Stack name under `terraform/stacks/` when `terraform_stack_dir` is empty. Default `example`. |
| `terraform_stack_dir` | Path to the Terraform root module. Empty uses `playbook_dir/../../terraform/stacks/<terraform_stack>`. |
| `terraform_workspace` | Optional workspace to select or create. Empty keeps the current workspace. |
| `terraform_extra_args` | Extra CLI arguments appended to the selected action. Default `[]`. |
| `terraform_var_file` | Optional `-var-file=` path relative to the stack directory. |
| `terraform_backend_config` | Dict of `-backend-config=key=value` entries for `terraform init`. Do not store secrets here. |
| `terraform_backend_configured` | Set true when the stack already declares a remote backend in `*.tf`. Default `false`. |
| `terraform_require_remote_backend` | Fail `apply`/`destroy` when no remote backend is configured. Default `true`. |
| `terraform_init_upgrade` | Pass `-upgrade` to `terraform init`. Default `false`. |
| `terraform_init_reconfigure` | Pass `-reconfigure` to `terraform init`. Default `false`. |
| `terraform_environment` | Extra environment variables merged into the Terraform process. Default `{}`. |
| `vault_aws_access_key_id` | Optional AWS access key exported as `AWS_ACCESS_KEY_ID`. |
| `vault_aws_secret_access_key` | Optional AWS secret key exported as `AWS_SECRET_ACCESS_KEY`. |
| `vault_aws_session_token` | Optional AWS session token exported as `AWS_SESSION_TOKEN`. |
| `aws_default_region` | Optional AWS region exported as `AWS_DEFAULT_REGION`. |
| `aws_profile` | Optional AWS shared-credentials profile exported as `AWS_PROFILE`. |
| `vault_terraform_cloud_token` | Optional Terraform Cloud token exported as `TF_TOKEN_app_terraform_io`. |
| `vault_terraform_http_username` | Optional HTTP backend username exported as `TF_HTTP_USERNAME`. |
| `vault_terraform_http_password` | Optional HTTP backend password exported as `TF_HTTP_PASSWORD`. |

Keep cloud and backend secrets in Ansible Vault (or AAP credentials mapped into
those vault variables). Do not pass secrets as `-var` or `-backend-config`.

## 🚀 Role Usage

```yaml
- name: Plan a Terraform stack from the generated bootstrap repo
  hosts: localhost
  gather_facts: false
  vars:
    terraform_action: plan
    terraform_stack: example
  roles:
    - role: infra.ado.terraform
```

```yaml
- name: Apply a stack with a remote backend and shared AWS vault
  hosts: localhost
  gather_facts: false
  vars:
    terraform_action: apply
    terraform_stack: aws-rhel-vm
    terraform_backend_configured: true
    vault_aws_access_key_id: "{{ vault_aws_access_key_id }}"
    vault_aws_secret_access_key: "{{ vault_aws_secret_access_key }}"
    aws_default_region: us-east-1
  roles:
    - role: infra.ado.terraform
```

Bootstrap wiring:

- Playbooks: `playbooks/terraform/ado-terraform-plan-bootstrap.yml` and
  `ado-terraform-apply-bootstrap.yml`
- Job templates: `ado-terraform-plan-bootstrap.jt.yml` and
  `ado-terraform-apply-bootstrap.jt.yml`
- Customer stacks live in the generated repo under `terraform/stacks/`

Preflight JSON is the source of intent. Select terraform from CLI with the
same payload the UI will eventually emit:

```json
{
  "components": ["terraform"],
  "component_apps": {
    "terraform": ["terraform"]
  },
  "component_config": {
    "terraform": {
      "bin": "terraform",
      "stack": "example"
    }
  }
}
```

Pass that file as `-e preflight_json=…` on the scaffolding playbook. Add the
preflight-ui checkbox in a follow-up so the form writes this JSON.

## 🧪 Role Molecule Testing

There is no live Terraform cloud scenario in this collection. Bootstrap
generation (playbooks, vars, and job templates) is covered by
`extensions/molecule/integration_bootstrap_terraform`.

```bash
cd /path/to/your/git/checkout/infra.ado
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
cd extensions/molecule
ln -sfn . molecule
molecule test -s integration_bootstrap_terraform
```

## 📁 Role Structure

```text
roles/
└─ terraform/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ meta/
   │  ├─ main.yml
   │  └─ argument_specs.yml
   └─ tasks/
      └─ main.yml
```
