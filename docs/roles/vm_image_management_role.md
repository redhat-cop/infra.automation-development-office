# infra.ado.vm_image_management

This Ansible role creates a qcow2 virtual machine image from an existing base image.
It runs prerequisite setup, validates paths, inspects the base image with qemu-img info,
and creates the output image with qemu-img convert.

## Role Information

| Property                | Value                         |
| ----------------------- | ----------------------------- |
| Author                  | Automation Development Office |
| License                 | GPL-3.0-or-later              |
| Minimum Ansible Version | 2.14                          |

## Options

### `vm_image_management_action` (str) (required)

Action selector used by the prerequisite and assertion tasks. The active workflow expects 'create'.

### `vm_image_management_dest_path` (str) (required)

Destination path for the output image. In prerequisites, this is expanded to the final output image path by appending vm_image_management_dest_name.

### `vm_image_management_dest_name` (str) (required)

Output image file name appended to vm_image_management_dest_path in prerequisites.

### `vm_image_management_base_path` (str) (required)

Base image directory input. In prerequisites, this is expanded to the final base image path by appending vm_image_management_base_name.

### `vm_image_management_base_name` (str) (required)

Base image file name appended to vm_image_management_base_path in prerequisites.

### `vm_image_management_format` (str)

Output image format passed to qemu-img convert -O.

**Default:** `qcow2`

### `vm_image_management_download` (bool)

When false, the current create workflow runs. Download flow remains present but commented out in main.yml.

**Default:** `False`

### `vm_image_management_path` (str)

Reserved default variable for a full destination path. It is defined in defaults but is not used by the current task flow.

### `vm_image_management_size` (str)

Reserved for future image sizing workflows. Not used by the current task flow.

### `vm_image_management_force` (bool)

Reserved for future replacement behavior. Not used by the current task flow.

**Default:** `False`

### `vm_image_management_resize` (bool)

Reserved for a future post-create resize workflow. main.yml currently includes a TODO for this feature.

**Default:** `False`

### `vm_image_management_backing` (bool)

Legacy variable from the earlier workflow. Not used by the current task flow.

**Default:** `True`

## See Also

See the role [README.md](https://github.com/redhat-cop/infra.automation-development-office/blob/main/roles/vm_image_management/README.md) for more details.
