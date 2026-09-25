# Role: `ocp_image_registry`

Optionally enable the OpenShift integrated image registry and validate that it
is operational (management state, ClusterOperator, pod, service, and optional
default route).

## Role Author

Chad Elliott

## ✅ Role Requirements

- OpenShift API access with permission to read/patch
  `configs.imageregistry.operator.openshift.io/cluster`.
- `kubernetes.core` collection installed.
- Usable registry backing storage already configured on the cluster (this role
  does **not** create registry storage and must not depend on NFS CSI).

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `ocp_image_registry_state` | `present` (enable + validate), `report` (status only), or `absent` (no-op / skip). | No | `present` |
| `ocp_image_registry_enabled` | When true with `present`, set `managementState=Managed` if needed. | No | `true` |
| `ocp_image_registry_default_route` | Patch `spec.defaultRoute` to this boolean. | No | `true` |
| `openshift_integrated_registry_enabled` | Alias for `ocp_image_registry_enabled`. | No | same |
| `openshift_integrated_registry_default_route` | Alias for `ocp_image_registry_default_route`. | No | same |
| `ocp_image_registry_report_only` | When true, never patch; only report status. | No | `false` |
| `ocp_image_registry_wait_retries` | Retries waiting for ClusterOperator Available. | No | `36` |
| `ocp_image_registry_wait_delay` | Seconds between readiness polls. | No | `10` |

## 🚀 Role Usage

```yaml
- name: ADO | Enable OpenShift integrated image registry
  hosts: localhost
  gather_facts: false
  vars:
    ocp_image_registry_enabled: true
    ocp_image_registry_default_route: true
  vars_files:
    - group_vars/all/{{ env }}/infra_config_vars.yml
    - group_vars/all/{{ env }}/vault_openshift.yml
    - group_vars/all/{{ env }}/vars_openshift.yml
  environment:
    K8S_AUTH_HOST: '{{ host }}'
    K8S_AUTH_API_KEY: '{{ token }}'
    K8S_AUTH_VERIFY_SSL: '{{ (verify_ssl | bool) | ternary(''yes'',''no'') }}'
  roles:
    - role: infra.ado.ocp_image_registry
```

## Behavior Notes

- Patches **only** `spec.managementState` and `spec.defaultRoute` via merge.
  Existing storage and other Config fields are preserved.
- Does **not** report SUCCESS solely because the Config patch succeeded.
  PASS requires Managed + storage ready + operator Available + ready
  Deployment + Service (+ default Route when requested).
- Do not configure registry PVC storage on `nfs-csi` while using this option to
  recover NFS CSI `ImagePullBackOff` (circular dependency).

## Preflight / bootstrap

Select OpenShift option `integrated_image_registry`. Optional fields:

- `openshift.integrated_registry_default_route` (default true)
- `openshift.install_image_registry_during_bootstrap` (default true)

## 🧪 Role Molecule Testing

Extension scenario `integration_ocp_image_registry` verifies README format and
role packaging offline (no live cluster by default).

```bash
cd extensions/molecule
molecule test -s integration_ocp_image_registry
```

## 📁 Role Structure

```text
roles/ocp_image_registry/
├── defaults/main.yml
├── meta/main.yml
├── README.md
├── tasks/main.yml
└── vars/main.yml
```
