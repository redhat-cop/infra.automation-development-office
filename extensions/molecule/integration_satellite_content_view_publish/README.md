# Molecule scenario: integration_satellite_content_view_publish

This scenario validates the `infra.automation_development_office.satellite_content_view` role **publish**
action using the extension-level Molecule layout.

## Playbook mapping

- `prepare`: `satellite_content_view_prepare_publish.yml`
- `converge`: `satellite_content_view_converge_publish.yml`
- `verify`: `satellite_content_view_verify.yml`
- `destroy`: `noop.yml`

## Run

From `extensions/molecule`:

```bash
ln -sfn . molecule
molecule test -s integration_satellite_content_view_publish
```

Run `integration_satellite_content_view_create` first so the test Content View
exists.

For full integration against Satellite, install `redhat.satellite` from Red Hat
Automation Hub (see `roles/satellite_content_view/README.md` Role Requirements),
export the same `SATELLITE_*` variables documented in
`integration_satellite_content_view_create/README.md`, then run
`molecule prepare`, `molecule converge`, and `molecule verify` for this scenario.
