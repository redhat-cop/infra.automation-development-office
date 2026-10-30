# RHEL system roles outside Controller

Each selected role has its own playbook under this directory. The playbook
calls `redhat.rhel_system_roles.<role>` and reads settings from
`group_vars/all/<env>/vars_rhel_system_roles.yml`.

Controller job templates and the RHEL workflow are optional. This playbook
does not require an organization, inventory, project, or job template.

```bash
ansible-playbook \
  playbooks/rhel_system_roles/ado-system-role-firewall-bootstrap.yml \
  -e env=prod
```

Replace `firewall` with the role name and `prod` with the generated
environment. The host group is `rhel_servers`. Install the
`redhat.rhel_system_roles` collection on the machine that runs the
playbook.

Settings for a role live under `rhel_system_roles.<role>` in
`vars_rhel_system_roles.yml`. An empty mapping uses that role's own
defaults. Required keys are the ones documented by
`redhat.rhel_system_roles.<role>`, not a second schema in ADO.
