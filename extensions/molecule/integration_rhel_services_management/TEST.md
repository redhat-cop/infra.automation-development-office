# Molecule Tests — rhel_services_management (default scenario)

**Test sequence**

dependency → syntax → create → converge → idempotence → destroy → verify


## What these tests cover

1. **Dependency**
   - Installs role/collection deps via `ansible-galaxy`.

2. **Syntax**
   - Runs `ansible-playbook --syntax-check` on scenario playbooks (basic YAML/Jinja sanity).

3. **Create**
   - Prepares the local runner/connection (localhost driver). Ensures the test variables are set.

4. **Converge**
   - Applies the `ado.utilities.rhel_services_management` role with:
     - `rhel_services_management_service_names`: a list of services (with and without `.service`) such as `['sshd', 'crond']` on EL-based systems.
     - `rhel_services_management_service_state`: e.g., `started`, `stopped`, `restarted`, or `reloaded`.
     - Optional `rhel_services_management_service_enabled`: boolean to enable/disable the units.
   - Role gathers `service_facts` and only manages services that actually exist on the host, mapping names without `.service` (e.g., `sshd` → `sshd.service`).

5. **Idempotence**
   - Re-runs converge and expects **`changed=0`** (no re-applies).

6. **Destroy**
   - No teardown is strictly required for service state; step runs as a no-op unless the scenario includes explicit cleanup.

7. **Verify**
   - When Python ≥ 3.7, asserts `ansible_facts.services` is defined and is a mapping.
   - Confirms the role reported no changes on the idempotence run.
   - Checks **README.md** exists and has basic structure (see below).


## README.md checks (verify step)
The verify play performs:

- ✅ **Existence**: `README.md` must be present at the role root.
- ✅ **Heading**: first heading starts with `# Role:`  
  (regex: `(?m)^#\s+Role:`)
- ✅ **Variables table**: contains a header row like `| Variable | Description |`  
  (regex: `\|\s*Variable\s*\|\s*Description\s*\|`)
- ✅ **Example code block**: fenced block like ```yaml … ``` (yaml/yml/ansible/bash)  
  (regex: ```(yaml|yml|ansible|bash)[\s\S]*?```) 


## Python version note
- Managed hosts must have **Python ≥ 3.7**. Python **3.6 and older cannot use `service_facts`**, so the role will no-op (and the scenario marks converge-related checks as **skipped** on those hosts).


## How to run

```bash
# full cycle
molecule test

# or step-by-step
molecule converge
molecule idempotence
molecule destroy
molecule verify
```

## Customizing the tested services
Override via environment or edit `molecule/default/group_vars/all`:

```yaml
rhel_services_management_service_names:
  - sshd
  - crond
rhel_services_management_service_state: started
# rhel_services_management_service_enabled: true
```

## Linting
- **Ansible syntax** runs automatically in the **`syntax`** step.
- **ansible-lint**: recommended to run locally/CI:
  ```bash
  ansible-lint --offline roles/namespace


# full cycle
molecule test

# or step-by-step
molecule converge
molecule idempotence
molecule destroy
molecule verify

Auth/TLS notes
Provide either:

molecule_root_password: "YOURPASSWORD"

Use a placeholder in the committed file and supply the real value at run time. Do not commit real
passwords or a Vault password file (`.vault_pass`, `.vault-pass`). Either:

- pass it as an extra var: `molecule converge -- -e molecule_root_password="$ROOT_PASSWORD"`, or
- keep an Ansible Vault file and a password file outside the repository and export
  `ANSIBLE_VAULT_PASSWORD_FILE=/path/outside/repo/vault-pass`.
