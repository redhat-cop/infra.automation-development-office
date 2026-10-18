# Role: infra.ado.ocp_nmstate_install

Install the Kubernetes NMState Operator, create the NMState singleton
instance, and optionally apply NodeNetworkConfigurationPolicy (NNCP)
resources that build bridges and bonds on node interfaces.

This is the role that makes `Localnet` networks possible: a CUDN with
`topology: Localnet` needs a physical network present on the nodes, and the
NNCP is what creates it.

> **WARNING:** NNCP changes modify live node network state. An NNCP that
> enslaves the wrong interface can make nodes unreachable, and recovery
> usually means console access. Review the generated desired state on one
> node before rolling it out. Set `ocp_nmstate_apply_nncp: false` to install
> the operator without touching interfaces.

## What gets created

| Step | Resource | Notes |
|---|---|---|
| 1 | Subscription + OperatorGroup | Via `ocp_operator_subscription` in `ocp_nmstate_namespace` |
| 2 | Operator readiness wait | Via `ocp_wait_operator` |
| 3 | `NMState` instance | Singleton CR named `ocp_nmstate_instance_name` |
| 4 | `NodeNetworkConfigurationPolicy` | One per entry in `ocp_nmstate_physical_networks` |
| 5 | Wait for `Available` | Polls each NNCP until the condition is True |

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift cluster with cluster-admin credentials.
- `kubernetes.core` collection.
- `infra.ado` collection — `ocp_operator_subscription`, `ocp_wait_operator`.
- Operator catalog reachable at `ocp_nmstate_operator_source`
  (`redhat-operators` by default). In a disconnected cluster, point this at
  the mirrored catalog source.
- Consistent interface naming across the nodes matched by `node_selector`.
  The NNCP names interfaces literally, so a node where `ens224` is actually
  `eno2` will fail to converge.

## 📦 Role Variables

| Variable | Default | Description |
|---|---|---|
| `ocp_nmstate_namespace` | `openshift-nmstate` | Operator namespace |
| `ocp_nmstate_operator_name` | `kubernetes-nmstate-operator` | Operator package |
| `ocp_nmstate_operator_channel` | `stable` | OLM channel |
| `ocp_nmstate_operator_source` | `redhat-operators` | Catalog source |
| `ocp_nmstate_operator_source_namespace` | `openshift-marketplace` | Catalog source namespace |
| `ocp_nmstate_instance_name` | `nmstate` | NMState CR name |
| `ocp_nmstate_physical_networks` | `[]` | Physical network definitions |
| `ocp_nmstate_apply_nncp` | `true` | Set `false` to install the operator only |
| `ocp_nmstate_nncp_wait_timeout` | `300` | NNCP wait timeout (seconds) |
| `ocp_nmstate_nncp_wait_retries` | `30` | Poll attempts per NNCP |
| `ocp_nmstate_nncp_wait_delay` | `10` | Seconds between poll attempts |

### Physical network definition keys

| Key | Description |
|---|---|
| `name` | NNCP name, and the value referenced as `physical_network` by a Localnet CUDN |
| `bridge` | Name of the linux-bridge to create, for example `br1` |
| `node_selector` | Node label map. Defaults to `{node-role.kubernetes.io/worker: ""}`. |
| `interface_config.type` | `bridge` (default) or `bond` |
| `interface_config.interfaces` | List of interface names to attach |
| `interface_config.bond_mode` | Bond mode when type is `bond`. Default `balance-rr`. |

### Generated desired state

- **`type: bridge`** — one `linux-bridge` named `bridge`, STP disabled, IPv4
  disabled on the bridge itself, with each entry of `interfaces` added as a
  port.
- **`type: bond`** — a bond named `<name>-bond` aggregating `interfaces`
  using `bond_mode`, with the bridge placed on top of the bond.

IPv4 is disabled on the bridge deliberately: these bridges carry tagged
workload traffic for Localnet networks, not node management addresses.

## 🚀 Role Usage

Bridge over a single interface:

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_nmstate_install
      vars:
        ocp_nmstate_physical_networks:
          - name: datacenter-vlan
            bridge: br1
            node_selector:
              node-role.kubernetes.io/worker: ""
            interface_config:
              type: bridge
              interfaces:
                - ens224
```

Bonded pair for redundancy:

```yaml
ocp_nmstate_physical_networks:
  - name: storage-net
    bridge: br-storage
    node_selector:
      node-role.kubernetes.io/worker: ""
    interface_config:
      type: bond
      bond_mode: 802.3ad
      interfaces:
        - ens224
        - ens225
```

Install the operator without modifying any node networking:

```yaml
- role: infra.ado.ocp_nmstate_install
  vars:
    ocp_nmstate_apply_nncp: false
```

### Verifying before and after

```bash
# What NMState currently sees on each node
oc get nodenetworkstate -o yaml

# Rollout status of applied policies
oc get nncp
oc get nnce
```

## 🧪 Role Molecule Testing

No Molecule scenario exists for this role yet. The role installs an operator
and reconfigures physical node interfaces, which cannot be exercised in the
default PR container matrix — `extensions/molecule/pr_exclude.txt` excludes
all `ocp_*` scenarios from PR runs.

When a scenario is added as `extensions/molecule/ocp_nmstate_install/`, run it
against a disposable cluster — never a shared one — with:

```bash
cd extensions/molecule && ln -sfn . molecule
molecule test -s ocp_nmstate_install
```

## 📁 Role Structure

```
roles/ocp_nmstate_install/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── tasks/
│   ├── main.yml        # operator, NMState instance, NNCP loop
│   └── create_nncp.yml # per-network desired state, apply, wait
└── README.md
```
