# Role: infra.automation_development_office.ocp_web_terminal

Install and wait for the OpenShift Web Terminal operator.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift API access (`kubernetes.core`)
- OperatorHub catalog access for `web-terminal`

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `name_space` / `operator_namespace` | Operator namespace |
| `operator_name` | Subscription package name |
| `operator_name_substring` | CSV / deployment match string |

## 🚀 Role Usage

```yaml
- hosts: localhost
  roles:
    - role: infra.automation_development_office.ocp_web_terminal
```

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via the OpenShift
**Deploy Web Terminal** JT after bootstrap.

## 📁 Role Structure

```text
roles/ocp_web_terminal/
  README.md
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
```
