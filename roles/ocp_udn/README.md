# Role: infra.ado.ocp_udn

Create or delete UserDefinedNetwork (UDN), ClusterUserDefinedNetwork (CUDN),
and NetworkAttachmentDefinition (NAD) resources for OpenShift
OVN-Kubernetes networking.

Each item in `ocp_udn_networks` is dispatched by its `resource_type` to a
dedicated task file, so one invocation can mix namespace-scoped and
cluster-scoped networks.

## Supported combinations

Not every topology is valid for every resource type. Unsupported pairs build
no spec and will fail or reuse a previous network's spec — check this table
before adding a network.

| `resource_type` | Scope | Layer2 | Layer3 | Localnet | Bridge |
|---|---|---|---|---|---|
| `UserDefinedNetwork` | namespace | ✅ | ✅ | ❌ | ❌ |
| `ClusterUserDefinedNetwork` | cluster | ✅ | ✅ | ✅ | ❌ |
| `NetworkAttachmentDefinition` | namespace | ❌ | ❌ | ✅ | ✅ |

`role` is `Primary` or `Secondary` (default `Secondary`). A cluster may have
only one Primary network per namespace, and namespaces attached to a Primary
UDN must carry the `k8s.ovn.org/primary-user-defined-network` label **from
the moment they are created** — see
[`ocp_networking`](../ocp_networking/README.md) for the namespace handling
that enforces this.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift cluster using the **OVN-Kubernetes** network provider. UDN and
  CUDN are OVN-K specific APIs and do not exist on other providers.
- `kubernetes.core` collection.
- Target namespaces must already exist for `UserDefinedNetwork` and
  `NetworkAttachmentDefinition`. This role does not create them.
- Cluster-admin credentials for `ClusterUserDefinedNetwork` (cluster-scoped).
- `Localnet` topologies require the named physical network to exist on the
  nodes — normally an OVS bridge mapping created by
  [`ocp_nmstate_install`](../ocp_nmstate_install/README.md).

## 📦 Role Variables

| Variable | Default | Description |
|---|---|---|
| `ocp_udn_networks` | `[]` | List of network definitions |
| `ocp_udn_state` | `present` | `present` or `absent`, applied to every item |

### Network definition keys

| Key | Applies to | Description |
|---|---|---|
| `name` | all | Resource name |
| `scope` | all | `namespace` or `cluster`, informational |
| `resource_type` | all | `UserDefinedNetwork`, `ClusterUserDefinedNetwork`, or `NetworkAttachmentDefinition`. Items with any other value are skipped silently. |
| `role` | UDN, CUDN | `Primary` or `Secondary` (default `Secondary`) |
| `topology` | all | `Layer2` (default), `Layer3`, `Localnet`, or `Bridge` |
| `namespaces` | UDN, NAD | List of namespace names; the resource is created once per entry |
| `namespace_selector` | CUDN | `{matchLabels: {...}}` selecting which namespaces attach |
| `subnets` | all | List of `{cidr: ...}` |
| `ipam` | UDN, CUDN, NAD Bridge | `{lifecycle: Persistent \| Disabled}` |
| `physical_network` | Localnet, Bridge | OVS bridge / physical network name. Bridge NADs default to `br1`. |
| `join_subnets` | Layer3 | Accepted by the schema; not currently rendered into the spec |

### Subnet handling differs by topology

- **Layer2 and Localnet** — only the `cidr` value is used; subnets are
  flattened to a list of plain CIDR strings.
- **Layer3** — the `subnets` list is passed to the API **verbatim**, so each
  entry must already use API field names (`cidr`, `hostSubnet`). A
  `host_subnet` key will not be translated.

### IPAM lifecycle and live migration

`ipam.lifecycle` defaults to `Persistent` for Layer2 UDN and CUDN. Persistent
IPAM is what lets a virtual machine keep its IP address across a live
migration. Set it to `Disabled` only for networks where addresses are
assigned externally.

## 🚀 Role Usage

Namespace-scoped secondary network:

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_udn
      vars:
        ocp_udn_networks:
          - name: app-network
            scope: namespace
            resource_type: UserDefinedNetwork
            role: Secondary
            topology: Layer2
            namespaces:
              - my-namespace
            subnets:
              - cidr: "10.200.0.0/16"
```

Cluster-scoped primary network for VM workloads, selected by namespace label:

```yaml
ocp_udn_networks:
  - name: vm-primary
    scope: cluster
    resource_type: ClusterUserDefinedNetwork
    role: Primary
    topology: Layer2
    namespace_selector:
      matchLabels:
        tenant: finance
    subnets:
      - cidr: "10.100.10.0/24"
    ipam:
      lifecycle: Persistent
```

Localnet network bridged to a physical VLAN:

```yaml
ocp_udn_networks:
  - name: vlan-200
    scope: cluster
    resource_type: ClusterUserDefinedNetwork
    role: Secondary
    topology: Localnet
    physical_network: datacenter-vlan
    namespace_selector:
      matchLabels:
        tenant: finance
    subnets:
      - cidr: "192.0.2.0/24"
```

Removing networks:

```yaml
- role: infra.ado.ocp_udn
  vars:
    ocp_udn_state: absent
    ocp_udn_networks: "{{ previously_created_networks }}"
```

## 🧪 Role Molecule Testing

No Molecule scenario exists for this role yet. UDN and CUDN are OVN-Kubernetes
CRDs, so coverage needs a live cluster rather than the default PR container
matrix — `extensions/molecule/pr_exclude.txt` excludes all `ocp_*` scenarios
from PR runs.

When a scenario is added as `extensions/molecule/ocp_udn/`, run it against a
reachable cluster with:

```bash
cd extensions/molecule && ln -sfn . molecule
molecule test -s ocp_udn
```

## 📁 Role Structure

```
roles/ocp_udn/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── tasks/
│   ├── main.yml                               # dispatch by resource_type
│   ├── create_userdefinednetwork.yml          # Layer2 / Layer3
│   ├── create_clusteruserdefinednetwork.yml   # Layer2 / Layer3 / Localnet
│   └── create_networkattachmentdefinition.yml # Localnet / Bridge
└── README.md
```
