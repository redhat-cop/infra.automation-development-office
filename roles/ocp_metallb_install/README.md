# Role: infra.ado.ocp_metallb_install

Install the MetalLB Operator, create the MetalLB instance, and configure
IPAddressPools, L2Advertisements, BGPPeers, and BGPAdvertisements so that
`Service` objects of type `LoadBalancer` receive real addresses on clusters
with no cloud load balancer.

Without MetalLB (or an equivalent), a `LoadBalancer` service on bare metal
stays in `<pending>` forever.

## What gets created

| Step | Resource | Notes |
|---|---|---|
| 1 | Subscription + OperatorGroup | Via `ocp_operator_subscription` in `ocp_metallb_namespace` |
| 2 | Operator readiness wait | Via `ocp_wait_operator` |
| 3 | `MetalLB` instance | Singleton CR, waited on until `Available` |
| 4 | `IPAddressPool` | One per `address_pools` entry |
| 5 | `L2Advertisement` | One per `l2_advertisements` entry |
| 6 | `BGPPeer` / `BGPAdvertisement` | Only when the corresponding lists are non-empty |

A pool is only reachable once something advertises it. An `IPAddressPool`
with no matching L2Advertisement or BGPAdvertisement allocates addresses that
nothing on the network can route to.

## Role Author

Automation Development Office

## ✅ Role Requirements

- OpenShift cluster on bare metal, or any platform without a cloud load
  balancer integration.
- Cluster-admin credentials.
- `kubernetes.core` collection.
- `infra.ado` collection — `ocp_operator_subscription`, `ocp_wait_operator`.
- Operator catalog reachable at `ocp_metallb_operator_source`
  (`redhat-operators` by default). Point this at a mirrored catalog in a
  disconnected cluster.
- Address pools that are **routable on the node network and excluded from
  DHCP**. Overlapping a DHCP scope causes intermittent, hard-to-trace address
  conflicts.
- For BGP mode, a peer router already configured to accept the session.

## 📦 Role Variables

| Variable | Default | Description |
|---|---|---|
| `ocp_metallb_namespace` | `metallb-system` | Operator namespace |
| `ocp_metallb_operator_name` | `metallb-operator` | Operator package |
| `ocp_metallb_operator_channel` | `stable` | OLM channel |
| `ocp_metallb_operator_source` | `redhat-operators` | Catalog source |
| `ocp_metallb_operator_source_namespace` | `openshift-marketplace` | Catalog source namespace |
| `ocp_metallb_instance_name` | `metallb` | MetalLB CR name |
| `ocp_metallb_config.enabled` | `false` | Consumed by callers, not by this role — see below |
| `ocp_metallb_config.address_pools` | `[]` | IPAddressPool definitions |
| `ocp_metallb_config.l2_advertisements` | `[]` | L2Advertisement definitions |
| `ocp_metallb_config.bgp_peers` | `[]` | BGPPeer definitions |
| `ocp_metallb_config.bgp_advertisements` | `[]` | BGPAdvertisement definitions |
| `ocp_metallb_wait_timeout` | `300` | Declared default; the readiness wait currently uses fixed retries |

> **`enabled` does not gate this role.** The tasks never read
> `ocp_metallb_config.enabled`; the check lives in the caller
> ([`ocp_networking`](../ocp_networking/README.md) phase 1). Including this
> role directly with `enabled: false` still installs the operator.

### Configuration keys

| Key | Applies to | Description |
|---|---|---|
| `name` | all | Resource name |
| `addresses` | address pool | List of ranges or CIDRs, for example `192.0.2.10-192.0.2.50` |
| `auto_assign` | address pool | Default `true`. Set `false` for a pool reserved for explicit requests. |
| `ip_address_pools` | advertisements | Pool names this advertisement covers |
| `node_selectors` | L2 advertisement | Restrict which nodes may announce |
| `interfaces` | L2 advertisement | Restrict which interfaces announce |
| `my_asn` / `peer_asn` | BGP peer | Local and remote AS numbers |
| `peer_address` | BGP peer | Router address |
| `password` | BGP peer | Optional MD5 session password |
| `communities` | BGP advertisement | Optional BGP communities |
| `aggregation_length` | BGP advertisement | Optional prefix aggregation length |

## 🚀 Role Usage

Layer 2 mode — the common bare-metal and lab setup:

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.ado.ocp_metallb_install
      vars:
        ocp_metallb_config:
          enabled: true
          address_pools:
            - name: external-pool
              addresses:
                - 192.0.2.200-192.0.2.250
          l2_advertisements:
            - name: external-l2
              ip_address_pools:
                - external-pool
```

BGP mode with a peer router:

```yaml
ocp_metallb_config:
  enabled: true
  address_pools:
    - name: bgp-pool
      addresses:
        - 198.51.100.0/24
      auto_assign: false
  bgp_peers:
    - name: edge-router
      my_asn: 64512
      peer_asn: 64513
      peer_address: 192.0.2.1
  bgp_advertisements:
    - name: bgp-advert
      ip_address_pools:
        - bgp-pool
      aggregation_length: 32
```

### Verifying

```bash
oc get pods -n metallb-system
oc get ipaddresspool,l2advertisement -n metallb-system
oc get svc -A --field-selector spec.type=LoadBalancer
```

## 🧪 Role Molecule Testing

No Molecule scenario exists for this role yet. The role installs an operator
and allocates addresses on the node network, so coverage needs a live cluster
rather than the default PR container matrix —
`extensions/molecule/pr_exclude.txt` excludes all `ocp_*` scenarios from PR
runs.

When a scenario is added as `extensions/molecule/ocp_metallb_install/`, run it
against a reachable cluster with:

```bash
cd extensions/molecule && ln -sfn . molecule
molecule test -s ocp_metallb_install
```

## 📁 Role Structure

```
roles/ocp_metallb_install/
├── defaults/
│   └── main.yml
├── meta/
│   └── main.yml
├── tasks/
│   └── main.yml   # operator, instance, pools, L2/BGP advertisements
└── README.md
```
