# Role: infra.ado.ocp_pega

Deploy Pega and optional OpenSearch/Backing Services from local Helm artifacts.

## Role Author

Automation Development Office.

## ✅ Role Requirements

A reachable OpenShift cluster, `kubernetes.core`, Python PyYAML, and preinstalled
Helm on the execution host. Supply Kubernetes authentication through `K8S_AUTH_*`
or kubeconfig. Local charts and all chart dependencies must already be available
in the Controller execution environment; bootstrap generation does not copy files
from a workstation into an EE. This is a Helm deployment, not an OLM Operator.

Use chart versions compatible with your licensed Pega images. Mirror every image,
including init containers, hooks, utility images, database/search and Kafka
services. Pin tags or digests. This role validates rendered image registry hosts
before cluster changes; it does not mirror images or prove registry availability.
A private registry may need pull secrets, CA trust and permissions configured in
values files/cluster. Bake the JDBC driver into the Pega image or supply an internal
artifact URL. Chart values and templates must not depend on public downloads.

By default, `ocp_pega_database_mode: new` deploys a supplied local database chart
and initializes Pega with `install-deploy` only when the Pega Helm release does not
yet exist. Subsequent runs use `deploy`. Failed/pending releases require operator
inspection before retrying. Existing mode requires an initialized Pega database
and always uses `deploy`. No automatic database upgrades are performed.
The old ad-hoc role's unconditional `install-deploy`, public Helm repositories,
privileged SCC grants and lab-specific passwords are deliberately not copied.
Configure matching database credentials, service names and schema names in the
database and Pega values files. The installer image must match your licensed release. Kafka and optional external services
must also be ready. No existing database or service is deleted by this role.

## 📦 Role Variables

| Variable | Description |
| --- | --- |
| `ocp_pega_database_mode` | `new` (default) or `existing` initialized database. |
| `ocp_pega_database_chart_path` / `ocp_pega_database_values_file` | Required local database chart and values in new mode. |
| `ocp_pega_namespace` | Namespace, default `pega`. |
| `ocp_pega_release_name` | Release, default `pega`. |
| `ocp_pega_chart_path` | Required absolute local chart directory or archive. |
| `ocp_pega_values_file` | Required absolute values path in the EE. |
| `ocp_pega_allowed_registries` | Required list of exact disconnected registry hosts, including ports. |
| `ocp_pega_opensearch_chart_path` / `ocp_pega_opensearch_values_file` | Optional local OpenSearch chart and values. |
| `ocp_pega_backingservices_chart_path` / `ocp_pega_backingservices_values_file` | Optional local Pega Backing Services chart and values. |
| `ocp_pega_helm_binary` | Preinstalled binary, default `helm`. |
| `ocp_pega_timeout` | Helm readiness timeout, default `20m0s`. |
| `ocp_pega_validate_only` | Render/validate without cluster access, default false. |

Keep passwords out of committed values files. Prefer existing Secret references
supported by the chosen chart, or mount a protected values file into the EE.
Rendered manifests are private temporary files removed even on failure.
Helm output is suppressed because values/manifests can contain secrets.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_pega
      ocp_pega_database_mode: existing
      ocp_pega_chart_path: /artifacts/charts/pega.tgz
      ocp_pega_values_file: /artifacts/values/pega.yaml
      ocp_pega_allowed_registries: [registry.example.test]
```

Preflight uses `component_config.pega` fields matching role suffixes, for example
`chart_path`, `values_file`, `namespace`, and `allowed_registries`. Registry hosts
may be a JSON list or a comma-separated UI string. The environment generator emits
`ocp_pega_*` variables in `vars_pega.yml`; the existing `ADO | Deploy Pega` template
and OpenShift workflow invoke the generated Pega playbook.

All releases are rendered and checked before the first cluster mutation. Apply
order is database (new mode), OpenSearch, Backing Services, Pega. Helm waits for readiness; reruns use
Helm's existing release state without forcing a database install.

## 🧪 Role Molecule Testing

`extensions/molecule/integration_ocp_pega_offline` exercises local chart rendering,
repeated validation, and rejection of a public image without cluster access.
Run `molecule test -s integration_ocp_pega_offline` from `extensions/molecule`
using the repository's documented collection setup. Live installation additionally
requires licensed Pega images, version-matched charts, database and cluster access.

## 📁 Role Structure

```text
ocp_pega/
  defaults/main.yml
  tasks/main.yml
  tasks/validate_release.yml
  files/validate_images.py
  meta/main.yml
```
