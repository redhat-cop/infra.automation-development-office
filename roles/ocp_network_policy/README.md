# Role: infra.ado.ocp_network_policy

Apply or remove OpenShift network security policy resources. The role takes a
flat list of policy definitions, validates each one, resolves the correct
`apiVersion` per kind, and routes namespace-scoped and cluster-scoped kinds to
separate tasks.

It is a thin applier: callers supply fully formed `spec` blocks. Template
expansion (default-deny, allow-within-tenant, and so on) happens upstream in
[`ocp_networking`](../ocp_networking/README.md).

## Supported kinds

`apiVersion` is resolved automatically and may be overridden per item.

| Kind | apiVersion | Scope |
|---|---|---|
| `NetworkPolicy` | `networking.k8s.io/v1` | namespaced |
| `MultiNetworkPolicy` | `k8s.cni.cncf.io/v1beta1` | namespaced |
| `EgressFirewall` | `k8s.ovn.org/v1` | namespaced |
| `AdminNetworkPolicy` | `policy.networking.k8s.io/v1alpha1` | cluster |
| `BaselineAdminNetworkPolicy` | `policy.networking.k8s.io/v1alpha1` | cluster |

An unrecognized `kind`, or an item missing `kind` or `name`, fails the play at
the validation step before anything is applied.

Routing is driven by whether `namespace` is present on the item, not by the
kind: items **with** a `namespace` go through the namespaced task, items
**without** one are only applied when the kind is `AdminNetworkPolicy` or
`BaselineAdminNetworkPolicy`. A namespaced kind submitted without a
`namespace` is therefore skipped silently.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift cluster using the **OVN-Kubernetes** network provider.
- `kubernetes.core` collection.
- Target namespaces must already exist for namespaced kinds.
- Cluster-admin credentials for `AdminNetworkPolicy` and
  `BaselineAdminNetworkPolicy`.

### Prerequisites this role does not configure

- **MultiNetworkPolicy** is only enforced when the cluster Network CR has
  `spec.useMultiNetworkPolicy: true`. No role in this collection sets it. With
  it off, MNP resources are created successfully and have no effect.
- **MultiNetworkPolicy targeting** requires the annotation
  `k8s.v1.cni.cncf.io/policy-for: <namespace>/<network-name>` naming the
  secondary network the policy applies to. Pass it through `annotations` — a
  MultiNetworkPolicy without it does not attach to any network.
- **EgressFirewall** allows only one resource per namespace, and OpenShift
  requires it to be named `default`.

## 📦 Role Variables

| Variable | Default | Description |
|---|---|---|
| `ocp_network_policy_resources` | `[]` | List of policy resources to apply |
| `ocp_network_policy_state` | `present` | `present` or `absent`, applied to every item |

### Resource item keys

| Key | Required | Description |
|---|---|---|
| `kind` | yes | One of the supported kinds above |
| `name` | yes | Resource name |
| `spec` | yes | Passed to the API verbatim |
| `namespace` | for namespaced kinds | Also selects the namespaced code path |
| `apiVersion` | no | Overrides the resolved default |
| `annotations` | no | Metadata annotations; required for MultiNetworkPolicy |

### Replace semantics

Resources are applied with `force: true`, so each run **replaces** the object
rather than strategic-merge-patching it. Removing a rule from `spec` removes
it from the cluster on the next run, and list fields such as `policyTypes`
shrink correctly. Any field managed outside this role is also overwritten.

## 🚀 Role Usage

Deny all ingress in a namespace:

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_network_policy
      vars:
        ocp_network_policy_resources:
          - kind: NetworkPolicy
            name: deny-all
            namespace: my-namespace
            spec:
              podSelector: {}
              policyTypes:
                - Ingress
                - Egress
```

MultiNetworkPolicy on a secondary network, with the required annotation:

```yaml
ocp_network_policy_resources:
  - kind: MultiNetworkPolicy
    name: mnp-default-deny
    namespace: my-namespace
    annotations:
      k8s.v1.cni.cncf.io/policy-for: my-namespace/vlan-200
    spec:
      podSelector: {}
      policyTypes:
        - Ingress
```

Cluster-scoped baseline, applied with no `namespace` key:

```yaml
ocp_network_policy_resources:
  - kind: BaselineAdminNetworkPolicy
    name: default
    spec:
      subject:
        namespaces: {}
      ingress:
        - name: deny-all
          action: Deny
          from:
            - namespaces: {}
```

Removing policies:

```yaml
- role: infra.ado.ocp_network_policy
  vars:
    ocp_network_policy_state: absent
    ocp_network_policy_resources: "{{ previously_applied_policies }}"
```

## 🧪 Role Molecule Testing

No Molecule scenario exists for this role yet. The policy CRDs it targets are
cluster features, so coverage needs a live OVN-Kubernetes cluster rather than
the default PR container matrix — `extensions/molecule/pr_exclude.txt`
excludes all `ocp_*` scenarios from PR runs.

When a scenario is added as `extensions/molecule/ocp_network_policy/`, run it
against a reachable cluster with:

```bash
cd extensions/molecule && ln -sfn . molecule
molecule test -s ocp_network_policy
```

## 📁 Role Structure

```
roles/ocp_network_policy/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── tasks/
│   └── main.yml   # validate kinds, apply namespaced, apply cluster-scoped
└── README.md
```
