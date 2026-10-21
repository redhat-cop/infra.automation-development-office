# Molecule scenario: integration_satellite_content_view_promote

This scenario validates the `infra.automation_development_office.satellite_content_view` role **promote**
action using the extension-level Molecule layout.

## Playbook mapping

- `prepare`: `satellite_content_view_prepare_promote.yml`
- `converge`: `satellite_content_view_converge_promote.yml`
- `verify`: `satellite_content_view_verify.yml`
- `destroy`: `noop.yml`

## Additional environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `SATELLITE_LIFECYCLE_ENVIRONMENTS` | No | Comma-separated lifecycle environments (default: `Library`) |
| `SATELLITE_CONTENT_VIEW_VERSION` | No | Version to promote (default: `1.0`) |

## Run

From `extensions/molecule`:

```bash
ln -sfn . molecule
molecule test -s integration_satellite_content_view_promote
```

Run the create and publish scenarios first so a published version exists to
promote.

For full integration, install `redhat.satellite` from Red Hat Automation Hub
(see `roles/satellite_content_view/README.md` Role Requirements) and follow the
environment variable guidance in
`integration_satellite_content_view_create/README.md`.
