# Role: infra.ado.ocp_egress

Apply or remove OpenShift egress resources — EgressIP (cluster-scoped) and
EgressFirewall (namespace-scoped). Both are OVN-Kubernetes CRDs served by
`k8s.ovn.org/v1`.

The role takes a flat list and selects resources by `kind`, so a single
invocation can cover both. Callers supply fully formed `spec` blocks;
template expansion happens upstream in
[`ocp_networking`](../ocp_networking/README.md).

## Supported kinds

| Kind | apiVersion | Scope | Notes |
|---|---|---|---|
| `EgressIP` | `k8s.ovn.org/v1` | cluster | Selects namespaces and/or pods by label |
| `EgressFirewall` | `k8s.ovn.org/v1` | namespaced | One per namespace, must be named `default` |

Items whose `kind` is neither value are ignored — the role filters with
`selectattr` rather than validating, so a typo produces no resource and no
error.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift cluster using the **OVN-Kubernetes** network provider.
- `kubernetes.core` collection.
- Cluster-admin credentials for EgressIP.
- Target namespaces must already exist for EgressFirewall.

### EgressIP node prerequisites

EgressIP needs at least one node labeled as egress-assignable:

```bash
oc label node <node> k8s.ovn.org/egress-assignable=""
```

The egress IP addresses must be routable on the node subnet and must not
collide with DHCP ranges or other allocations. This role does not verify
either condition — an unassignable EgressIP is created successfully and stays
unassigned.

### EgressFirewall behavior

- Rules are evaluated **in order**; the first match wins. A `Deny` to
  `0.0.0.0/0` therefore belongs last.
- The policy applies to traffic leaving the cluster network. It does not
  filter pod-to-pod traffic inside the cluster — use NetworkPolicy for that.
- DNS-based rules (`dnsName`) resolve periodically. Short-TTL or
  round-robin names can behave inconsistently.

## 📦 Role Variables

| Variable | Default | Description |
|---|---|---|
| `ocp_egress_resources` | `[]` | List of egress resources to apply |
| `ocp_egress_state` | `present` | `present` or `absent`, applied to every item |

### Resource item keys

| Key | Required | Description |
|---|---|---|
| `kind` | yes | `EgressIP` or `EgressFirewall` |
| `name` | yes | Resource name. Use `default` for EgressFirewall. |
| `spec` | yes | Passed to the API verbatim |
| `namespace` | EgressFirewall only | Target namespace |

## 🚀 Role Usage

Restrict egress from a namespace to one internal range, denying the rest:

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_egress
      vars:
        ocp_egress_resources:
          - kind: EgressFirewall
            name: default
            namespace: my-namespace
            spec:
              egress:
                - type: Allow
                  to:
                    cidrSelector: 10.0.0.0/8
                - type: Deny
                  to:
                    cidrSelector: 0.0.0.0/0
```

Pin a namespace's outbound traffic to fixed source addresses:

```yaml
ocp_egress_resources:
  - kind: EgressIP
    name: finance-egressip
    spec:
      egressIPs:
        - 10.100.0.50
        - 10.100.0.51
      namespaceSelector:
        matchLabels:
          tenant: finance
```

> The `namespaceSelector` matches labels you must apply yourself. When this
> role is driven by `ocp_networking`, the selector defaults to
> `{tenant: <tenant_name>}` — set that label through the tenant's
> `namespaces[].labels` or the EgressIP will select nothing.

Allow a specific hostname and port, then deny everything else:

```yaml
ocp_egress_resources:
  - kind: EgressFirewall
    name: default
    namespace: my-namespace
    spec:
      egress:
        - type: Allow
          to:
            dnsName: registry.redhat.io
          ports:
            - protocol: TCP
              port: 443
        - type: Deny
          to:
            cidrSelector: 0.0.0.0/0
```

## 🧪 Role Molecule Testing

No Molecule scenario exists for this role yet. EgressIP and EgressFirewall are
OVN-Kubernetes CRDs, so coverage needs a live cluster rather than the default
PR container matrix — `extensions/molecule/pr_exclude.txt` excludes all
`ocp_*` scenarios from PR runs.

When a scenario is added as `extensions/molecule/ocp_egress/`, run it against
a reachable cluster with:

```bash
cd extensions/molecule && ln -sfn . molecule
molecule test -s ocp_egress
```

## 📁 Role Structure

```
roles/ocp_egress/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── tasks/
│   └── main.yml   # apply EgressIP, then EgressFirewall
└── README.md
```
