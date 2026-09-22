# Disconnected Pega bootstrap

Pega is deployed with Helm, not an OLM Operator. No runtime Internet access is
required by the ADO role. Artifacts still need to be obtained before installation.
If the installation site has no Internet access, a connected staging system or
an approved media delivery must provide the licensed software. ADO does not fetch
licensed Pega content on behalf of the user.

## Prepare the offline bundle

1. Choose your licensed Pega version and compatible Pega/Backing Services charts.
   Select compatible database and search versions using Pega's support matrix.
2. On an approved staging system, obtain the application, installer, SRS, database,
   OpenSearch, Kafka and utility/init-container images required by those charts.
   This list is chart-dependent: use `helm template` with the final values to
   inventory actual images, including Jobs and hooks. Do not rely on three Pega
   image archives being the complete dependency set.
3. Package the charts with all subcharts already present. Do not leave chart
   dependency resolution to the disconnected installation.
4. Transfer archives through the approved offline-media process. Import images
   into an internal registry and rewrite every image reference in chart values.
   Supply pull secrets and trusted registry CAs as required.
5. Bake Helm, Python/PyYAML and kubernetes.core into the Controller execution
   environment. Stage the local chart and protected values files at the absolute
   paths entered in Preflight. The UI does not upload or mount these files.
6. Keep JDBC drivers inside the Pega image or an internal artifact service.
   Review chart configuration for other downloads, license checks and external
   dependencies; image validation alone cannot prove absence of network egress.

## New database (default)

Supply a local database chart and values file. The database chart must create the
service, credentials and persistent storage referenced by the Pega values file.
Use a fresh release/namespace and suitable storage. Supply the matching Pega
installer image and installation credentials/settings in the Pega values file.

The role provisions database, optional OpenSearch, optional Backing Services, then
Pega. It uses `install-deploy` for the first Pega release. Normal subsequent runs
use `deploy`. A failed/pending Pega release stops for inspection rather than
repeating initialization. Deleting the Pega release is not a retry strategy: the
database may already contain data and must be inspected before another install.

## Existing database

Select existing database mode and provide an initialized Pega database through
Pega chart values. The database chart is skipped; Pega uses `deploy`. The role
does not perform database migrations, upgrades or destructive cleanup.

## Packaging size

Prefer a separate offline image bundle/internal registry over embedding Pega
archives in the Preflight image. The latter increases every Preflight image
transfer and does not make those images available to Kubernetes automatically.
The charts, configuration and Ansible code are small relative to container images.
Measure the exact archives rather than estimating from Pega's application image:

```bash
du -ch /path/to/offline-bundle/*.tar /path/to/offline-bundle/*.tgz
```

That measures local files, not the final OCI compressed-layer size. Image format,
compression, shared layers and all supporting services affect the final size.
No actual Pega image-size total has been verified in this workspace.

## Validation and delivery

Preflight writes `component_config.pega`; the environment generator emits
`ocp_pega_*` variables. The existing `ADO | Deploy Pega` JT and OpenShift workflow
consume the generated playbook, which invokes `infra.ado.ocp_pega`.

Before cluster changes, the role renders all configured charts and rejects public
or unpinned image references. `ocp_pega_validate_only: true` performs this validation
without cluster access. Live validation requires the real licensed images, charts,
registry, database values and OpenShift environment; synthetic chart tests do not
establish that a specific Pega release is operational.
