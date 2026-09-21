# ADO-LAB Reset

`ADO-LAB Reset` is the phrase used to reload the working model for Chad's ADO lab.
The phrase itself is the checklist; do not ask the user to repaste it.

## 1. Re-establish repository boundaries

```text
/home/chelliot/openshift/git/github-ado/ado
  -> actual infra.ado product/bootstrap repo

/home/chelliot/openshift/git/github-ado/ado-preflight-ui
  -> actual preflight form/runner repo

/home/chelliot/openshift/git/github-ado/bootstrap-sample
  -> generated bootstrap output / Controller SCM

/home/chelliot/openshift/git/github-ado/ado-cluster-portal
  -> lab-only homepage / VPN self-service front door

/home/chelliot/openshift/git/lab-tools-dont-delete
  -> separate lab-only day-2 Ansible repo
```

Mental model:

```text
portal.rhlabchad.com -> where do I click?
ado-preflight-ui     -> configure & bootstrap
ado / infra.ado      -> portable automation that makes it real
bootstrap-sample     -> what Controller runs for apps
lab-tools-dont-delete-> lab user/VPN/host/virt + selected lab operations
```

## 2. Reload agent instructions

Read every open repository's nearest `AGENTS.md`.

If present, also read local uncommitted rules under:

```text
/home/chelliot/openshift/git/github-ado/.cursor/rules/local/
<repo>/.cursor/rules/local/
```

Those local rules are operational context only and must remain uncommitted.

## 3. Reload desired state / credentials without repasting secrets

When relevant, use the newest matching local preflight export under:

```text
~/Downloads/ado-preflight-*.json
```

Use established local vault/credential sources. Do not ask the user to repaste passwords/tokens when a known local source exists.
Never expose or commit secret values.

## 4. Reassert product priority

For ADO product work:

1. `ado` / bootstrap behavior first
2. `ado-preflight-ui` second
3. regenerated `bootstrap-sample` output third

Everything reusable must be environment agnostic, repeatable/idempotent, and compatible with disconnected operation unless explicitly designed otherwise.

Do not fix product bugs only by patching Controller, OpenShift, or `bootstrap-sample`.

## 5. Preflight runtime reality

Preflight uses the baked `collections/infra-ado-*.tar.gz`, not merely the neighboring live `ado` checkout.
After an `ado` collection change that must be tested through Preflight:

```bash
cd /home/chelliot/openshift/git/github-ado/ado
ansible-galaxy collection build -o /tmp
cp /tmp/infra-ado-*.tar.gz /home/chelliot/openshift/git/github-ado/ado-preflight-ui/collections/
```

Then use the normal local Preflight redeploy/restart/import/bootstrap flow, followed by Controller project sync/relaunch as appropriate.

## 6. Quality gates for ADO source changes

Before declaring `infra.ado` work complete:

- run `yamllint` on changed YAML;
- run `ansible-lint` with repository dependencies;
- add/update meaningful Molecule coverage for behavior changes;
- run the relevant Molecule scenario(s) when available;
- run applicable changelog and README verification;
- run applicable sanity/unit/build checks or explicitly state why they were not run;
- report exact commands and PASS/FAIL/NOT RUN status.

Pipeline behavior and `.github/Developers _Guide.md` are authoritative.

## 7. Lab-only work

Portal and `lab-tools-dont-delete` stay separate from product ADO.
They may contain lab-specific values because they are lab repos; do not leak those assumptions into reusable `infra.ado` behavior.
