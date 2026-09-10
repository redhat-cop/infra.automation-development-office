# ADO Development Model (Cursor-friendly "how we build" guide)

This document is a **copyable model** for how to develop, lint, test, and document changes in this repo.
It is written so you can hand it to another engineer and keep the dev workflow consistent.

Use it like a checklist every time you touch:

- `infra.ado` roles/modules (Ansible collection code)
- `ado-preflight-ui` (the containerized web UI)
- shared generated bootstrap repo artifacts
- any documentation that affects maintainers/operators

---
## 1) Big Picture: what "ADO" means in this repo

In practice, there are three layers:

1. **`ado-preflight-ui`** (UI + container entrypoint)
   - Collects operator answers via a web form
   - Normalizes them into a **preflight JSON payload**
   - Starts an Ansible run inside a container

2. **`infra.ado`** (Ansible collection: roles/modules)
   - Implements bootstrap logic:
     - generate `group_vars/` and vault files
     - scaffold a generated bootstrap repo structure
     - generate controller objects (AAP: org/creds/projects/JTs/workflows)
     - optionally apply to AAP/Hub during bootstrap

3. **Generated "bootstrap repo"** (the output repo you commit/push)
   - Contains the content that day-1/day-2 automation runs later
   - Usually includes:
     - `group_vars/all/<env>/...`
     - `playbooks/<component>/...`
     - `configs/controller/...`
     - `configs/job_templates/...`
     - `configs/workflows/...`
     - `templates/` (Grafana dashboard seeds)
     - `terraform/stacks/` (optional Terraform/OpenTofu roots; seed is always
       copied, playbooks and job templates are emitted when `terraform` is
       selected in preflight JSON)

---
## 2) System Boundaries (what you should change where)

### Change `infra.ado` when…

- You're changing Ansible logic, generated variables, controller object generation, or playbook content.
- You're changing how the UI's preflight JSON gets turned into a working bootstrap repository.
- You're changing Molecule scenarios / role behavior.

Typical paths:

- `ansible_collections/infra/ado/roles/<role_name>/...`
- `ansible_collections/infra/ado/plugins/...`
- `extensions/molecule/<scenario>/...`
- `changelogs/fragments/...` (user-visible changes)

### Change `ado-preflight-ui` when…

- You're changing the questionnaire, payload normalization, JSON download/import, or API endpoints.
- You're changing how UI state maps into preflight JSON.
- You're changing UI help text or run-log UX.

Typical paths:

- `ado-preflight-ui/src/App.jsx`
- `ado-preflight-ui/server.js`
- `ado-preflight-ui/docker/*` (overlays applied into the runtime container)
- `.changeset/*` (UI-visible changes)

---
## 3) Repository Layout (dev view)

This is the "mental model" tree people should keep in mind when developing:

```text
github-ado/
  ado/                              # infra.ado repo content + docs
    roles/                          # sometimes mirrored role sources
    docs/                           # dev model docs + templates
    changelogs/fragments/          # infra.ado user-visible change entries
    .github/Developers _Guide.md    # CI/molecule dev workflow guide
    extensions/molecule/           # integration scenarios (molecule)
    ansible_collections/infra/ado/  # built collection source layout

  ado-preflight-ui/                 # web UI that runs Ansible in a container
    src/                            # React app
    server.js                       # API + preflight payload normalization
    docker/                         # overlays (applied into runtime container)
    collections/                    # baked collection tarballs used at runtime
    .changeset/                     # changesets fragments for UI changelog
```

---
## 4) The "Bootstrap Works" model (first principles)

Use this flow when explaining ADO to someone new:

### Step A: preflight JSON is the single source of intent

- UI input → preflight JSON (the UI is **only a form**; see `.cursor/rules/bootstrap-ui-cli-parity.mdc`)
- CLI uses the **same JSON** via `-e preflight_json=…` on `run-ado-scaffolding.yml` - behavior must match the UI run
- New optional components (for example `terraform`) must work from that JSON
  even before a preflight-ui checkbox exists. Add the UI selection in a follow-up
  so CLI and UI stay on the same payload.

Core fields typically include:

- `env`, `domain`, `additional_environments`
- `components` and/or `component_apps`
- `component_config` and `component_options`
- `aap.enabled`, AAP hostname/org/project naming/credentials intent
- `git` settings (URL/branch/token/auto-push)

### Step B: Ansible generates a repo on disk (in a container workspace)

The container runs the ADO bootstrap scaffolding playbook (one of):

- `run-ado-scaffolding.yml`
- `00-controller-bootstrap.yml` (controller configs)

In `infra.ado`, the important roles are:

1. `infra.ado.bootstrap_generate_env_vars`
   - writes:
     - `group_vars/all/<env>/vars_*.yml`
     - `group_vars/all/<env>/vault_*.yml`

2. `infra.ado.bootstrap_generate_playbook_repo`
   - scaffolds:
     - `playbooks/<component>/...`
     - `configs/controller/...`
     - `configs/job_templates/...`
     - `configs/workflows/...`
     - seed trees such as `templates/` and `terraform/stacks/`

3. `infra.ado.bootstrap_controller`
   - applies controller objects to AAP when "Using AAP" is enabled
   - optionally uploads/publishes collection content to Hub/EE when enabled

### Step C: the generated repo is committed/pushed (optional)

- `git.auto_push` controls whether to commit and push from the container.
- Git authentication differs per SCM (`gitlab`, `bitbucket`, `github`, `other`).

---
## 5) The "ADO Preflight UI Works" model

When another engineer asks "why is this so complicated?", answer with:

1. **UI → backend**: UI sends a preflight payload to `/api/bootstrap`
2. **backend → ansible-playbook**: server writes preflight JSON to the container workspace and runs Ansible
3. **ansible roles → repo**: roles generate the output repo structure
4. **optional apply**: if AAP is enabled, controller objects are applied directly during bootstrap

Implementation notes to remember:

- `server.js` contains preflight payload normalization, including special cases like **Hub-only**.
- `src/App.jsx` contains payload building and export (download JSON).
- `ado-preflight-ui/docker/*.yml` overlays into the runtime collection before the Ansible run.

---
## 6) Development Workflow Model (step-by-step)

Follow this exact sequence for every PR:

### 0. Identify the change surface

Label what you changed:

- `infra.ado` role/module behavior
- `ado-preflight-ui` payload normalization or UI state
- generated bootstrap artifacts expectations

This determines which lint/tests/docs you must run.

### 1. Update code

Make the smallest correct change.

Rules of thumb:

- Keep variable naming consistent with existing roles.
- Prefer updating the "source" role file rather than trying to patch artifacts.
- If you must adjust preflight payload schema mapping, update both server + UI payload building.

### 2. Update documentation (README format + developer notes)

If you changed a role's behavior/variables:

- Update `roles/<role>/README.md` (for that role)
- Ensure it matches the role README template (format verification is CI-backed)

### 3. Add changelog entry (format matters)

This repo uses **two different changelog systems**, depending on where you changed:

#### infra.ado changelog: fragments

Add a file under:

`ado/changelogs/fragments/<some-name>.yml`

Use sections defined in:

`ado/changelogs/config.yaml`

Example fragment format:

```yaml
---
bugfixes:
  - my_role - Fixed handler notification when ``my_var`` is unset.
```

Expected:

- prefix the entry with the affected component (role name / `ci` / FQCN)
- use the section keys from `changelogs/config.yaml`

#### ado-preflight-ui changelog: Changesets

Add a file under:

`.changeset/<name>.md`

Template:

```md
---
"ado-preflight-ui": patch
---
Short description of user-visible behavior change.
```

### 4. Update Molecule scenarios (if behavior is integration-visible)

If the change affects a scenario path in `extensions/molecule/`, update/add:

- `extensions/molecule/<scenario>/molecule.yml`
- `extensions/molecule/<scenario>/...`

Then run:

`molecule test -s <scenario_name>`

### 5. Local validation (must be fast and repeatable)

Run the relevant "local checklist" below.

---
## 7) README Format Model

### Role README template

Role readmes should follow the structure required by:

`ado/docs/templates/role_readme_format_template.md`

This template is intentionally strict so engineers can quickly learn role behavior.

Minimal required sections:

- short description + role author
- ✅ role requirements
- 📦 role variables
- 🚀 role usage examples
- 🧪 role molecule testing
- 📁 role structure

---
## 8) Changelog Format Model

### infra.ado fragment sections

This repo's `changelogs/config.yaml` defines allowed sections such as:

- `minor_changes`
- `bugfixes`
- `security_fixes`
- `doc_changes`

Rules:

- entries are lists
- you should not hand-edit `CHANGELOG.rst` directly in normal PRs
- fragments are compiled into `CHANGELOG.rst` during release pipelines

---
## 9) Linting Model (yamllint + ansible-lint)

### YAML lint (typical)

Run `yamllint` on tasks/defaults for the role you changed:

```bash
yamllint roles/<role_name>/tasks
yamllint roles/<role_name>/defaults
```

### Ansible lint (offline, typical)

Typical local pattern from the repo:

```bash
ansible-galaxy collection install -r collections/requirements.yml \
  -p .ansible/collections

ANSIBLE_COLLECTIONS_PATH=.ansible/collections ansible-lint --offline
```

If you want to lint only a role:

```bash
ansible-lint --offline roles/<role_name>
```

---
## 10) Molecule Testing Model

### Where scenarios live

Molecule scenarios live under:

`extensions/molecule/`

Each scenario folder contains a `molecule.yml`.

### Install local collection and dependencies

From the collection root:

```bash
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix community.general containers.podman \
  --force -p ~/.ansible/collections

export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
```

### Run one scenario

```bash
cd extensions/molecule
ln -sfn . molecule
molecule test -s <scenario_name>
```

### PR CI behavior (important context)

- CI discovers scenarios and runs them in a matrix
- certain `ocp_*` scenarios require OpenShift secrets and are excluded from PR by default

When you want "the same tests CI runs", follow:

`ado/.github/Developers _Guide.md` → "Molecule testing"

---
## 11) Cursor Collaboration Model (how to keep work consistent)

When using Cursor to collaborate with others, keep these conventions:

1. Keep diffs focused:
   - one PR for one concept / subsystem (UI mapping, role logic, lint/tests, docs)
2. Always include:
   - what changed and why
   - what commands you ran locally
   - what scenarios (molecule) you tested
3. If you changed:
   - a role → update the role README + run `yamllint`/`ansible-lint`
   - a user behavior path → add a changelog fragment/changeset
4. If you changed payload schema mapping:
   - update both UI + server normalization logic
   - verify by re-running bootstrap with a saved JSON payload

---
## 12) "First Model" Summary you can paste into chat

If someone asks "how does ADO work?", reply with:

1. **UI** collects answers → writes preflight JSON
2. **backend** writes JSON into the container workspace and runs `ansible-playbook`
3. **infra.ado roles** generate env vars, vault files, playbooks, and AAP controller objects
4. Optionally **hub/galaxy/EE** actions happen during bootstrap
5. Output is a generated bootstrap repository you commit/push (optional)

---
## Appendix: quick pointers

- Role docs: `roles/<role_name>/README.md` + template in `docs/templates/role_readme_format_template.md`
- infra.ado changelog fragments: `changelogs/fragments/*.yml`
- preflight-ui changesets: `.changeset/*.md`
- Molecule: `extensions/molecule/<scenario>/molecule.yml`

