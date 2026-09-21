# TEST: integration_rhel_repos_rhsm

## Purpose

Manual-only scenario for exercising `infra.ado.rhel_repos` with the
`rhsm_repository` method on a registered RHEL host.

This scenario is excluded from pull request CI. See
[`extensions/molecule/pr_exclude.txt`](https://github.com/redhat-cop/infra.automation-development-office/blob/main/extensions/molecule/pr_exclude.txt).

## Requirements

- A registered RHEL system with working `subscription-manager` access
- Repository IDs valid for the target host (for example,
  `rhel-9-for-x86_64-baseos-rpms`)
- Not suitable for unregistered UBI Podman containers

## Sequence

- `prepare`
- `converge`
- `idempotence`
- `verify`

## Notes

- Playbooks are placeholders today; run against a real registered host inventory
  when validating RHSM behavior.
- For automated container testing, use `integration_rhel_repos_default` instead.

## Run

```bash
cd extensions/molecule
molecule test -s integration_rhel_repos_rhsm
```

Or trigger via GitHub Actions `workflow_dispatch` with
`run_rhel_repos_rhsm: true`.
