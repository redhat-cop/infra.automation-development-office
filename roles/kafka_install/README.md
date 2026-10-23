# Role: infra.automation_development_office.kafka_install

Kafka Install automation role. Primary tasks include: Kafka Install Set derived vars; Kafka Install Lookup currentCSV for channel when operator_starting_csv not provided; Kafka Install Derive effective starting CSV (safe).

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible Core
- Required collections listed in `collections/requirements.yml`
- Inventory or extra variables appropriate for the target platform

### Auth via environment

Set Kubernetes authentication through the standard `K8S_AUTH_*` environment
variables before running the role or the Molecule verify scenario.

```bash
export K8S_AUTH_HOST=https://api.example.com:6443
export K8S_AUTH_API_KEY=<token>
export K8S_AUTH_VERIFY_SSL=false
```

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `kafka_install_state` | Desired state used by role tasks when supported. |

## 🚀 Role Usage

```yaml
- name: Run kafka_install
  hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.kafka_install
```

## 🧪 Role Molecule Testing

Run Molecule scenarios from the role directory when a scenario is available.

This role runs tasks such as:

- Kafka Install Set derived vars
- Kafka Install Lookup currentCSV for channel when operator_starting_csv not provided
- Kafka Install Derive effective starting CSV (safe)
- Kafka Install Set kafka_install_operator_starting_csv_effective from provided startingCSV

```bash
cd roles/kafka_install
molecule test
```

## 📁 Role Structure

```text
roles/kafka_install/
  README.md
  defaults/
  handlers/
  meta/
  tasks/
  tests/
  vars/
```
