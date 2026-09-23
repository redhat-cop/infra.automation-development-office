# Terraform stacks

Copied into generated playbook repos by `infra.ado.bootstrap_generate_playbook_repo`.

Put one Terraform (or OpenTofu) root module per directory under `stacks/`.
Contoller job templates `ADO | Terraform plan` and `ADO | Terraform apply`
run `infra.ado.terraform` against `terraform/stacks/<stack>`.

## Layout

```text
terraform/
  README.md
  stacks/
    example/          # stub root module — replace or add your stacks
      main.tf
```

## Requirements

- A remote backend before `apply` or `destroy` from Ansible Automation Platform.
  Execution environments are ephemeral; local `terraform.tfstate` will not survive
  the job.
- `terraform` or `tofu` on the execution environment (`ado-ee` does not ship
  the binary yet).
- Cloud credentials in `group_vars/all/<env>/vault_aws.yml` (AWS) and/or
  `vault_terraform.yml` (Terraform Cloud / HTTP backend).

## Day-2 split

Use Terraform for cloud (or other) infrastructure customers already manage with
`.tf` modules. Keep Ansible (`infra.ado` roles) for OpenShift operators, RHEL,
Satellite, and IdM.
