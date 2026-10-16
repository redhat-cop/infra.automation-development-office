# Role: infra.ado.ocp_networking

Centralized OpenShift networking orchestration. Translates administrator
networking intent (typically produced by PreFlight) into supported OpenShift
resources: tenant networks (UDN/CUDN/NAD), security policies (NetworkPolicy,
MultiNetworkPolicy, AdminNetworkPolicy, BaselineAdminNetworkPolicy,
EgressFirewall), physical node networking (NMState/NNCP), load balancing
(MetalLB), and egress (EgressIP).

This role is an orchestrator: it owns phase ordering and schema translation,
then delegates resource creation to subordinate roles. It does not require
OpenShift Virtualization to be selected.

## Execution order

Phases run in dependency order. Each is gated by a boolean flag so callers can
re-run a subset during incremental passes.

| Phase | Action | Delegates to | Gate |
|---|---|---|---|
| 0 | Assert the cluster uses OVN-Kubernetes | — | `ocp_networking_validate_provider` |
| 1 | Install NMState operator and apply NNCPs | `ocp_nmstate_install` | any physical network with `managed_by_nmstate: true` |
| 1 | Install MetalLB operator and pools | `ocp_metallb_install` | `load_balancing.metallb.enabled` |
| 2 | Create tenant namespaces with labels | `ocp_namespace` | `ocp_networking_create_namespaces` |
| 3 | Create UDN / CUDN / NAD per tenant network | `ocp_udn` | `ocp_networking_apply_network_resources` |
| 4 | Apply cluster ANP/BANP, then tenant NP/MNP/EgressFirewall | `ocp_network_policy` | `ocp_networking_apply_security_policies` |
| 5 | Apply EgressIP per tenant | `ocp_egress` | `ocp_networking_apply_egress_resources` |

Namespaces are created before network resources on purpose — see
[Primary UDN namespaces](#primary-udn-namespaces-must-be-labeled-at-creation).

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift cluster using the **OVN-Kubernetes** network provider. The role
  asserts this and fails fast otherwise.
- `kubernetes.core` collection.
- `infra.ado` collection — subordinate roles `ocp_namespace`, `ocp_udn`,
  `ocp_network_policy`, `ocp_egress`, `ocp_nmstate_install`,
  `ocp_metallb_install`.
- Cluster-admin level credentials. The role creates cluster-scoped resources
  (CUDN, ANP/BANP, EgressIP) and installs operators.

### Prerequisites this role does not configure

- **MultiNetworkPolicy support.** MultiNetworkPolicy resources are only
  enforced when the cluster Network CR has
  `spec.useMultiNetworkPolicy: true`. No role in this collection sets it. If
  it is off, MNP resources apply successfully and silently do nothing.
- **Namespace `tenant` labels.** The default EgressIP `namespaceSelector` is
  `{tenant: <tenant_name>}`. Nothing applies that label automatically — set it
  yourself through `namespaces[].labels`, or override
  `connectivity.egress_ip.namespace_selector`.

## 📦 Role Variables

| Variable | Default | Description |
|---|---|---|
| `ocp_networking_enabled` | `false` | Master enable for networking |
| `ocp_networking_ocp_version` | `"4.18"` | Target OpenShift version |
| `ocp_networking_network_provider` | `"OVNKubernetes"` | Cluster network provider |
| `ocp_networking_tenants` | `[]` | Tenant definitions (see below) |
| `ocp_networking_cluster_security` | `{}` | Cluster-level admin policies |
| `ocp_networking_physical_networks` | `[]` | Physical network definitions |
| `ocp_networking_ingress` | `{}` | Ingress configuration |
| `ocp_networking_load_balancing` | `{}` | MetalLB configuration |
| `ocp_networking_validate_provider` | `true` | Assert OVN-Kubernetes before running |
| `ocp_networking_create_namespaces` | `true` | Run phase 2 (namespaces) |
| `ocp_networking_apply_network_resources` | `true` | Run phase 3 (UDN/CUDN/NAD) |
| `ocp_networking_apply_security_policies` | `true` | Run phase 4 (policies) |
| `ocp_networking_apply_egress_resources` | `true` | Run phase 5 (EgressIP) |

### Tenant schema

Each item in `ocp_networking_tenants`:

| Key | Description |
|---|---|
| `tenant_name` | Required. Used as the prefix for every generated policy name. |
| `namespaces` | List of `{name, create, labels}`. `create: false` skips creation but still targets the namespace. |
| `networks` | List of network definitions, passed to `ocp_udn`. See [`ocp_udn`](../ocp_udn/README.md). |
| `security` | Nested object — `network_policy`, `multi_network_policy`, `egress_firewall`. |
| `connectivity` | Nested object — currently `egress_ip`. |

> **Schema note.** This role consumes the **nested** PreFlight tenant shape
> (`tenant.security.network_policy.enabled`). It does not consume the
> flattened output of the UI's `generateAnsibleVars()`
> (`tenant.security.network_policy_enabled`), which exists only for the YAML
> preview. The bootstrap template passes raw tenant JSON through unchanged.

### Security templates

`security.network_policy.template` accepts:

| Template | Generates |
|---|---|
| `default-deny-ingress` | One deny-all policy, `policyTypes: [Ingress]` |
| `default-deny-all` | One deny-all policy, `policyTypes: [Ingress, Egress]` |
| `allow-within-tenant` | One policy allowing ingress from every namespace in the tenant |
| `allow-from-namespaces` | Default-deny plus an allow rule for `allowed_namespace_selector` |
| `custom` | Rules built from `custom_rules` (see `build_custom_np.yml`) |

`security.multi_network_policy.template` accepts the same values except that
`allow-within-tenant` is spelled **`allow-same-tenant`**. MultiNetworkPolicy
resources are annotated with `k8s.v1.cni.cncf.io/policy-for` pointing at the
tenant's first secondary network.

`security.egress_firewall` takes `{enabled, rules}`, where each rule is
`{type, to_type, cidr_selector | dns_name, ports}`:

- `type` — `Allow` or `Deny` (default `Allow`)
- `to_type` — `cidr` (default) or `dns`
- `ports` — list of `{protocol, port}`; omitted when empty

### Cluster security schema

`ocp_networking_cluster_security` accepts:

- `admin_network_policies` — list of `{name, spec}` applied as
  AdminNetworkPolicy
- `baseline_admin_network_policy` — single `{name, spec}` applied as
  BaselineAdminNetworkPolicy

## 🚀 Role Usage

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_networking
      vars:
        ocp_networking_enabled: true
        ocp_networking_tenants:
          - tenant_name: finance
            namespaces:
              - name: finance-apps
                create: true
                labels:
                  tenant: finance
            networks:
              - name: finance-network
                scope: cluster
                resource_type: ClusterUserDefinedNetwork
                role: Primary
                topology: Layer2
                subnets:
                  - cidr: "10.100.10.0/24"
                ipam:
                  lifecycle: Persistent
                namespace_selector:
                  matchLabels:
                    tenant: finance
            security:
              network_policy:
                enabled: true
                template: default-deny-ingress
              egress_firewall:
                enabled: true
                rules:
                  - type: Allow
                    to_type: dns
                    dns_name: registry.redhat.io
                  - type: Deny
                    to_type: cidr
                    cidr_selector: 0.0.0.0/0
            connectivity:
              egress_ip:
                enabled: true
                addresses:
                  - 10.100.0.50
```

### Running a single phase

```yaml
- role: infra.ado.ocp_networking
  vars:
    ocp_networking_create_namespaces: false
    ocp_networking_apply_network_resources: false
    ocp_networking_apply_egress_resources: false
    # leaves only cluster + tenant security policies
```

## Operational notes

### Primary UDN namespaces must be labeled at creation

When a tenant has at least one network with `role: Primary`, OVN-Kubernetes
requires the label `k8s.ovn.org/primary-user-defined-network` on each of the
tenant's namespaces. A ValidatingAdmissionPolicy **rejects adding the label
after the namespace exists**, so phase 2 merges it in at creation time.

For namespaces that already exist without the label, delete and recreate them
or move the workload — the label cannot be patched in.

### Re-runs

Subordinate roles call `kubernetes.core.k8s` with `force: true`, which
replaces rather than strategic-merge-patches. Removing a rule from
`custom_rules` therefore removes it from the cluster on the next run.

## 🧪 Role Molecule Testing

No Molecule scenario exists for this role yet. It provisions cluster-scoped
resources and requires a live OVN-Kubernetes cluster, so it cannot run in the
default PR container matrix — `extensions/molecule/pr_exclude.txt` already
excludes all `ocp_*` scenarios from PR runs.

When a scenario is added as `extensions/molecule/ocp_networking/`, run it
against a reachable cluster with:

```bash
cd extensions/molecule && ln -sfn . molecule
molecule test -s ocp_networking
```

## 📁 Role Structure

```
roles/ocp_networking/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── tasks/
│   ├── main.yml                     # phase orchestration
│   ├── create_tenant_namespaces.yml # phase 2, primary-UDN labeling
│   ├── tenant_network.yml           # phase 3, delegates to ocp_udn
│   ├── cluster_security.yml         # phase 4, ANP / BANP
│   ├── tenant_security.yml          # phase 4, NP / MNP / EgressFirewall
│   ├── build_custom_np.yml          # custom rule -> policy spec
│   └── tenant_egress.yml            # phase 5, EgressIP
└── README.md
```
