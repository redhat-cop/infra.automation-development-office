<!-- cspell: ignore SSOT CMDB -->
# AGENTS.md — infra.ado

`ado` is the source repository for the `infra.ado` Ansible collection and the primary source of truth for portable ADO bootstrap behavior.

Also follow the practices in the upstream ansible-creator agent guidance referenced by the original repository AGENTS file:
https://raw.githubusercontent.com/ansible/ansible-creator/refs/heads/main/docs/agents.md

## Read first

Before changing collection behavior, read:

- `docs/ADO_DEVELOPMENT_MODEL.md`
- `.github/Developers _Guide.md`
- `docs/templates/role_readme_format_template.md` when a role README is affected
- the nearest role/module/playbook implementation and its Molecule scenario
- `changelogs/config.yaml` when a user-visible change is made

## Highest-priority architecture rule

**ADO/bootstrap behavior comes first.**

For product capabilities, implement the portable, repeatable behavior in `infra.ado` before adding UI-only convenience or editing generated output. `ado-preflight-ui` must invoke/describe this behavior, not replace it.

## Portable + repeatable

Every reusable ADO change must be:

- **environment agnostic** — no Chad-lab-specific hosts, routes, credentials, namespaces, storage classes, cluster names, AAP orgs, SCM URLs, or domain names in reusable defaults/tasks/templates;
- **repeatable/idempotent** — reruns converge and do not depend on manual cleanup or one-time mutation;
- **parameterized** through established vars/preflight schema patterns;
- **safe for disconnected operation** unless an external dependency is explicit and documented;
- **compatible with generated bootstrap repos** and Controller/AAP execution patterns already used by the collection.

Lab-specific values belong in generated environment vars/vaults or lab repos, never reusable collection logic.

## Change boundaries

Change `infra.ado` when changing:

- Ansible role/module logic
- preflight JSON -> generated vars/vault/playbook behavior
- generated Controller/AAP organization, credential, project, JT, workflow content
- reusable app install/configuration behavior
- Molecule behavior or integration coverage

Do not put product bootstrap semantics only in `ado-preflight-ui/server.js` or `src/App.jsx`.
Do not "fix" `bootstrap-sample` by hand when the generator is wrong.

## Mandatory quality gates

A behavior change is not complete until relevant quality gates are satisfied.

### Always for Ansible/YAML changes

1. Run `yamllint` on changed YAML paths/files.
2. Run `ansible-lint --offline` using the repository dependency setup.
3. Validate syntax/build as applicable.

Typical local dependency/lint pattern from the development model:

```bash
ansible-galaxy collection install -r collections/requirements.yml -p .ansible/collections
ANSIBLE_COLLECTIONS_PATH=.ansible/collections ansible-lint --offline
```

### Molecule is required for behavior changes

- Every new role or integration-visible behavior change must add or update meaningful Molecule coverage unless there is a documented technical reason it cannot.
- Inspect `extensions/molecule/` for the closest existing scenario before creating a new one.
- PR CI discovers scenarios from `extensions/molecule/*/molecule.yml` and applies exclusions from `extensions/molecule/pr_exclude.txt`.
- Run relevant scenarios locally when possible:

```bash
ansible-galaxy collection install . --force --no-deps -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix community.general containers.podman --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
cd extensions/molecule
ln -sfn . molecule
molecule test -s <scenario_name>
```

When a scenario has `requirements.yml`, honor those dependencies rather than inventing a parallel setup.

### Mirror repository CI, do not invent a substitute

The repo's pipelines and developer guide are authoritative. Relevant checks include:

- changelog validation
- `ansible-lint`
- README format verification
- Molecule discovery + matrix
- Ansible sanity tests
- unit tests
- collection build/import checks
- applicable security/data-exposure scans

Use existing scripts under `scripts/` and `scripts/ci/` where they apply, including:

```text
scripts/validate_changelog.py
scripts/verify_readme.py
scripts/security_checks.py
scripts/security_data_exposure_scan.py
scripts/ci/*
```

Do not replace repository CI behavior with an improvised test command just because it is easier.

## Documentation + changelog

For role behavior/variables:

- update the role README;
- conform to `docs/templates/role_readme_format_template.md`;
- add/update Molecule coverage;
- add a changelog fragment under `changelogs/fragments/` when required;
- do not hand-edit `CHANGELOG.rst` in normal feature/fix PRs.

Validate where applicable:

```bash
python3 scripts/validate_changelog.py --ref main
python3 scripts/verify_readme.py roles/<role>/README.md --template docs/templates/role_readme_format_template.md
```

## Agent completion report

Before saying a change is finished, report exact commands and results in this form:

```text
PASS     yamllint <paths>
PASS     ansible-lint --offline
PASS     molecule test -s <scenario>
PASS     changelog validation
PASS     README verification
PASS     collection/sanity/unit check <command>
NOT RUN  <check> - <specific reason>
```

Never say "tests should pass" or "CI should be fine" as a substitute for execution.

## ADO-LAB Reset

When the user says `ADO-LAB Reset`, read `docs/ADO-LAB-RESET.md` and follow it. Never commit secrets, local preflight exports, or `.cursor/` local rules.
