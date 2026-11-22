#  Role: ado.openshift.create_htpass_admin_user

Create, update, or delete an OpenShift **HTPasswd** identity provider and user(s). The role:
- Creates/updates the Secret in `openshift-config` containing bcrypt `htpasswd` entries.
- Adds/updates an HTPasswd IdP in the cluster OAuth **without removing other IdPs**.
- Auto-selects `mappingMethod` (prefers safety):
  - If `update_htpass: true` → use **add**.
  - Else if the IdP already exists → keep its current mapping method.
  - Else if any target username already exists as an OpenShift `User` → use **add**.
  - Otherwise → use **claim**.
- (Optional) grants **cluster-admin** via per-user `ClusterRoleBinding`.
- Delete path removes only this IdP entry, the Secret, and (optionally) the CRBs.

---

## Requirements

- OpenShift API reachable with auth (via `K8S_AUTH_*` env vars or module params)
- Collections:
  - `kubernetes.core`
- Tools on the controller:
  - `htpasswd` (RHEL: `yum install httpd-tools`, Debian/Ubuntu: `apt-get install apache2-utils`)
- Optional CLIs for verification: `oc`, `jq`

---

## Variables

### Top-level

| Variable               | Description |
|-----------------------|-------------|
| `state`               | `present` (default) or `absent`. |
| `validate_certs`      | TLS verification for k8s modules. Default `false`. |
| `grant_admin`         | When `true`, create `ClusterRoleBinding cluster-admin-<user>` per user. Default `true`. |
| `update_htpass`       | When `true`, forces `mappingMethod: add`. Default `false`. |
| `bcrypt_cost`         | Cost factor used by `htpasswd -B -C`. Default `10`. |

### IdP & Secret

| Variable                | Default                 | Meaning |
|-------------------------|-------------------------|---------|
| `htpasswd_idp_name`     | `htpasswd-admin`        | Name of the HTPasswd IdP in OAuth. |
| `htpasswd_secret_name`  | `htpasswd-admin-secret` | Secret name in `openshift-config` containing the `htpasswd` data. |

### User credentials (choose one input style)

| Variable         | Type            | Default | Notes |
|------------------|-----------------|---------|-------|
| `users`          | list of objects | —       | Example: `[{ name: admin, password: <supplied-at-run-time> }]`. |
| `htpasswd_user`  | string          | —       | Single user name (used if `users` not provided). |
| `htpasswd_pass`  | string          | —       | Single user password (used if `users` not provided). |

> **Notes**
> - The Secret data key is `htpasswd`. All entries are **bcrypt** hashes produced by the `htpasswd` tool.
> - The role does **not** delete other IdPs, only merges/replaces the one named by `htpasswd_idp_name`.

---

## Examples

### Minimal

```yaml
- hosts: localhost
  gather_facts: false
  vars:
    htpasswd_user: admin
    htpasswd_pass: "{{ lookup('ansible.builtin.env', 'MOLECULE_HTPASSWD_PASS') }}"
  roles:
    - ado.openshift.create_htpass_admin_user
```

### Force `mappingMethod: add` (avoid collisions)

```yaml
- hosts: localhost
  gather_facts: false
  vars:
    htpasswd_user: admin
    htpasswd_pass: "{{ lookup('ansible.builtin.env', 'MOLECULE_HTPASSWD_PASS') }}"
    update_htpass: true
  roles:
    - ado.openshift.create_htpass_admin_user
```

### Multiple users

```yaml
- hosts: localhost
  gather_facts: false
  vars:
    users:
      - name: admin
        password: newpass
      - name: breakglass-admin
        password: <supplied-at-run-time>
  roles:
    - ado.openshift.create_htpass_admin_user
```

### Delete (absent)

```yaml
- hosts: localhost
  gather_facts: false
  vars:
    state: absent
    htpasswd_idp_name: htpasswd-admin
    htpasswd_secret_name: htpasswd-admin-secret
    grant_admin: true
  roles:
    - ado.openshift.create_htpass_admin_user
```

---

## Outputs

This role does not return structured outputs by default. It applies cluster resources idempotently and **waits** for `ClusterOperator/authentication` to settle (`Progressing=False`, `Degraded=False`).

---

## Behavior Notes

- **OAuth merge**: only the IdP with `name == htpasswd_idp_name` is replaced. All other IdPs are preserved.
- **Secret**: created/updated in `openshift-config` with key `htpasswd`.
- **ClusterRoleBinding**: `cluster-admin-<username>` created when `grant_admin: true`.
- **Operator rollout**: pod restarts are **not required**; the authentication operator reconciles. The role waits for it to settle.
- **CLI logins**: if multiple IdPs are challenge-capable, the OAuth server may not accept `oc -u/-p`. Use the web console and select the HTPasswd provider, or ensure only the HTPasswd IdP is `challenge: true`.

---

## Troubleshooting

- **Operator Degraded=True**: Check for invalid IdPs (e.g., OIDC issuer unresolvable) or missing Secrets referenced by any HTPasswd IdP.
- **Password mismatch**: Verify the Secret's `htpasswd` content and test with `htpasswd -vb`.
- **Username collision**: Use `update_htpass: true` to force `mappingMethod: add`, or choose a unique break-glass username.

---

## Molecule

A default Molecule scenario is provided under `molecule/default` and covers:
- Non-destructive add/merge
- Secret presence and content
- Optional CRB creation
- Proper delete

Set kube auth via env:

```bash
export K8S_AUTH_HOST="https://api.ocp.example:6443"
export K8S_AUTH_API_KEY="…"
export K8S_AUTH_VERIFY_SSL="no"
```

Run:

```bash
molecule converge
molecule idempotence
molecule destroy
```

Your `molecule.yml` wires `converge` and `destroy` to their respective playbooks.

---

## Author
- Chad Elliott (<chelliot@redhat.com>)

---

## Repository layout

```text
.
├── defaults
│   └── main.yml
├── handlers
│   └── main.yml
├── meta
│   └── main.yml
├── molecule
│   └── default
│       ├── converge.yml
│       ├── destroy.yml
│       ├── group_vars
│       │   └── all
│       │       └── vault.yml
│       ├── molecule.yml
│       ├── README.md
└── README.md
```
