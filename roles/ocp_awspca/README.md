# Role: `ocp_awspca`

Manage an AWS PCA-backed `AWSPCAClusterIssuer` and its credentials Secret in OpenShift/Kubernetes.

This role supports `present` and `absent` state flows and can optionally wait for issuer readiness.

## Role Author

Chad Elliott

## ✅ Role Requirements

- OpenShift/Kubernetes API access.
- `kubernetes.core` collection installed.
- AWS PCA issuer CRDs installed before running the role.
- AWS credentials available by role variables or environment variables.

## 📦 Role Variables

| Variable | Description | Required | Default |
| -------- | ----------- | -------- | ------- |
| `state` | Desired state for resources. Supported values: `present`, `absent`. | Yes | N/A |
| `ocp_awspca_namespace` | Namespace where the AWS credentials Secret exists. | No | `cert-manager` |
| `ocp_awspca_secret_name` | Secret name that stores AWS credentials. | No | `awspca-creds` |
| `ocp_awspca_issuer_name` | Name of the `AWSPCAClusterIssuer` resource. | No | `awspca-clusterissuer` |
| `ocp_awspca_region` | AWS region used by the issuer. | No | `us-gov-west-1` |
| `ocp_awspca_pca_arn` | Private CA ARN used by `AWSPCAClusterIssuer`. | Yes (`state: present`) | `""` |
| `ocp_awspca_access_key_id` | Explicit AWS access key ID. Falls back to `AWS_ACCESS_KEY_ID` env var when empty. | No | `""` |
| `ocp_awspca_secret_access_key` | Explicit AWS secret access key. Falls back to `AWS_SECRET_ACCESS_KEY` env var when empty. | No | `""` |
| `ocp_awspca_secret_key_id_field` | Secret key field name for access key ID in Kubernetes Secret `stringData`. | No | `AWS_ACCESS_KEY_ID` |
| `ocp_awspca_secret_secret_key_field` | Secret key field name for secret access key in Kubernetes Secret `stringData`. | No | `AWS_SECRET_ACCESS_KEY` |
| `ocp_awspca_wait_ready` | Wait for issuer Ready condition after creation. | No | `true` |
| `ocp_awspca_wait_retries` | Retry count for readiness polling. | No | `30` |
| `ocp_awspca_wait_delay` | Delay (seconds) between readiness polling attempts. | No | `10` |
| `ocp_awspca_no_log` | Hide sensitive values in task output. | No | `true` |

## Bootstrap playbook credentials

When run through the generated bootstrap playbook
``playbooks/cert-manager/ado-install-and-configure-awspca-bootstrap.yml``,
AWS account credentials are loaded from the shared bootstrap vault file
``group_vars/all/<env>/vault_aws.yml`` (``vault_aws_access_key_id``,
``vault_aws_secret_access_key``). A playbook pre-task maps those values to
``ocp_awspca_access_key_id`` and ``ocp_awspca_secret_access_key`` before this
role runs.

### Migrating from legacy vault layout

Bootstrap used to scaffold ``ocp_awspca_access_key_id`` /
``ocp_awspca_secret_access_key`` in generated ``vault_openshift.yml`` or
``vault_cert_manager.yml``. Those keys are no longer emitted by bootstrap
templates. For existing environments:

1. Move PCA account credentials into ``vault_aws.yml`` using the
   ``vault_aws_*`` key names (see
   ``infra.automation_development_office.bootstrap_generate_env_vars`` README, *Shared AWS credentials*).
2. Keep PCA issuer settings (region, PCA ARN, namespace, etc.) in
   ``vars_cert_manager.yml``.
3. Sync the updated awspca bootstrap playbook from the collection.

If you have not migrated yet, credentials left only in
``vault_cert_manager.yml`` as ``ocp_awspca_*`` still work until you move them
to ``vault_aws.yml``.

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.ocp_awspca
      vars:
        state: present
        ocp_awspca_namespace: cert-manager
        ocp_awspca_secret_name: awspca-creds
        ocp_awspca_issuer_name: awspca-clusterissuer
        ocp_awspca_region: us-gov-west-1
        ocp_awspca_pca_arn: arn:aws-us-gov:acm-pca:region:account:certificate-authority/example
```

## 🧪 Role Molecule Testing

This role includes a Molecule scenario under `molecule/default/`.

Run from the role directory:

```bash
molecule test -s default
```

## 📁 Role Structure

```text
ocp_awspca/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml
├── molecule/
│   └── default/
│       ├── converge.yml
│       ├── destroy.yml
│       ├── molecule.yml
│       ├── README.md
│       ├── TEST.md
│       └── verify.yml
├── README.md
├── tasks/
│   └── main.yml
├── tests/
│   └── inventory
└── vars/
    └── main.yml
```
