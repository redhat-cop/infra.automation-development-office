# Molecule: integration_ocp_absent_cleanup

Validates ``infra.ado.ocp_absent_cleanup`` safety gates without a cluster:

- empty namespace list refused
- ``kube-system`` / ``default`` refused
- invalid ``ocp_absent_cleanup_mode`` refused

```bash
cd extensions/molecule
ln -sfn . molecule
molecule test -s integration_ocp_absent_cleanup
```
