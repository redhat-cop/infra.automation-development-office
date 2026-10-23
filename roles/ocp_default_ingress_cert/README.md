# Role: infra.automation_development_office.ocp_default_ingress_cert

Replace the OpenShift default IngressController TLS certificate (router
wildcard for `*.apps.<domain>`) and optionally trust the issuing CA
cluster-wide via `Proxy/cluster` `trustedCA`.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift API access (`kubernetes.core`)
- PEM certificate and private key for the wildcard (or SAN) cert

## 📦 Role Variables

| Variable | Description |
|----------|-------------|
| `tls_crt` / `tls_key` | Router wildcard certificate and key (PEM) |
| `ca_crt` | Optional issuing CA / chain PEM |
| `ocp_default_ingress_trust_ca_clusterwide` | When true, ConfigMap + Proxy trustedCA |

## 🚀 Role Usage

```yaml
- hosts: localhost
  roles:
    - role: infra.automation_development_office.ocp_default_ingress_cert
```

## 🧪 Role Molecule Testing

No Molecule scenario ships with this role yet. Validate via the OpenShift
**Update Default Ingress Certificate** JT after bootstrap.

## 📁 Role Structure

```text
roles/ocp_default_ingress_cert/
  README.md
  defaults/main.yml
  meta/main.yml
  tasks/main.yml
```
