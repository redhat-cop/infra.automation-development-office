# Contributor Code of Conduct

## Adoption of the Ansible Community Code of Conduct

Contributors to the **Automation Development Office (ADO)** `infra.ado` Ansible
collection are expected to follow the
[Ansible Community Code of Conduct](https://docs.ansible.com/projects/ansible/devel/community/code_of_conduct.html)
in all project spaces, including GitHub issues and pull requests, code review,
and related discussion.

That document covers how we treat one another: be considerate, patient,
respectful, kind, inquisitive, and helpful; follow the anti-harassment policy;
and report serious violations through Ansible's channels when appropriate (see
the Ansible document for details, including
[codeofconduct@ansible.com](mailto:codeofconduct@ansible.com)).

This file does not replace the Ansible Community Code of Conduct. It adds
**repository-specific expectations** for working in this collection.

## ADO addendum: expectations for this repository

The following expectations apply in addition to the Ansible Community Code of
Conduct when contributing to
[Automation-Development-Office/ado](https://github.com/redhat-cop/infra.automation-development-office).

### Pull requests and issues

- Open **focused** changes with a clear summary, linked issues when applicable
  (for example `Fixes #123`), and an accurate test plan as described in the
  [pull request template](https://github.com/redhat-cop/infra.automation-development-office/blob/main/.github/pull_request_template.md).
- Give and accept review feedback on the **merits of the change**. Maintainers
  may request more tests or documentation; that is normal review, not a
  personal rejection.
- Coordinate with maintainers **before** large design changes, new roles, or
  breaking changes.

### Quality and security

- Run applicable checks before requesting review, such as `ansible-lint`,
  `python scripts/verify_readme.py` for role README changes, Molecule scenarios,
  and the security scripts under `scripts/` when relevant.
- **Never commit secrets** — no passwords, API keys, vault contents, customer
  data, or other sensitive material in issues, pull requests, or the repository.
- Add changelog fragments under `changelogs/fragments/` when required by project
  policy (see the pull request template).

### Project layout and CI

- Prefer normalized conventions: role READMEs per
  `docs/templates/role_readme_format_template.md`, extension-level Molecule
  scenarios under `extensions/molecule/`, and shared playbooks under
  `extensions/molecule/utils/playbooks/`.
- Some scenarios (for example OpenShift `ocp_*` tests) need live infrastructure
  and are excluded from default pull request CI; use documented
  `workflow_dispatch` inputs when running them in GitHub Actions.

### AI-assisted contributions

Follow the
[Ansible Community Policy for AI-Assisted Contributions](https://docs.ansible.com/projects/ansible/devel/community/ai_policy.html)
when using generative tools in this repository. You are responsible for
reviewing, testing, and understanding any code or documentation you submit.

## Reporting concerns for this repository

For behavior related to **this repository** that you do not wish to raise
through Ansible's community channels, contact:

- **Email:** [automation-development-office@redhat.com](mailto:automation-development-office@redhat.com)
- **GitHub:** [open an issue](https://github.com/redhat-cop/infra.automation-development-office/issues)
  for general concerns, or contact repository administrators directly for
  sensitive matters

For harassment or conduct violations in the broader Ansible community context,
use the reporting paths described in the
[Ansible Community Code of Conduct](https://docs.ansible.com/projects/ansible/devel/community/code_of_conduct.html).

## Related guidance

- [CONTRIBUTING](https://github.com/redhat-cop/infra.automation-development-office/blob/main/CONTRIBUTING)
- [Pull request template](https://github.com/redhat-cop/infra.automation-development-office/blob/main/.github/pull_request_template.md)
- [Ansible Community Code of Conduct](https://docs.ansible.com/projects/ansible/devel/community/code_of_conduct.html)
