.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.ado/edit/main/roles/vm_image_management/meta/argument_specs.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.24.0

.. Anchors

.. _ansible_collections.infra.ado.vm_image_management_role:

.. Title

infra.ado.vm_image_management role -- Create a qcow2 virtual machine image from an existing base image.
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This role is part of the `infra.ado collection <https://galaxy.ansible.com/ui/repo/published/infra/ado/>`_ (version 1.0.0).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it use: :code:`ansible\-galaxy collection install infra.ado`.

    To use it in a playbook, specify: :code:`infra.ado.vm_image_management`.

.. contents::
   :local:
   :depth: 2

.. _ansible_collections.infra.ado.vm_image_management_role__entrypoint-main:

.. Entry point title

Entry point ``main`` -- Create a qcow2 virtual machine image from an existing base image.
-----------------------------------------------------------------------------------------

.. version_added


.. Deprecated


Synopsis
^^^^^^^^

.. Description

- This Ansible role creates a qcow2 virtual machine image from an existing base image.
  It runs prerequisite setup, validates paths, inspects the base image with qemu\-img info,
  and creates the output image with qemu\-img convert.

.. Requirements


.. Options

Parameters
^^^^^^^^^^

.. tabularcolumns:: \X{1}{3}\X{2}{3}

.. list-table::
  :width: 100%
  :widths: auto
  :header-rows: 1
  :class: longtable ansible-option-table

  * - Parameter
    - Comments

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_action"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_action:

      .. rst-class:: ansible-option-title

      **vm_image_management_action**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_action" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Action selector used by the prerequisite and assertion tasks. The active workflow expects 'create'.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_backing"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_backing:

      .. rst-class:: ansible-option-title

      **vm_image_management_backing**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_backing" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Legacy variable from the earlier workflow. Not used by the current task flow.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry:`false`
      - :ansible-option-choices-entry-default:`true` :ansible-option-choices-default-mark:`← (default)`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_base_name"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_base_name:

      .. rst-class:: ansible-option-title

      **vm_image_management_base_name**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_base_name" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Base image file name appended to vm\_image\_base\_path in prerequisites.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_base_path"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_base_path:

      .. rst-class:: ansible-option-title

      **vm_image_management_base_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_base_path" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Base image directory input. In prerequisites, this is expanded to the final base image path by appending vm\_image\_base\_name.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_dest_name"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_dest_name:

      .. rst-class:: ansible-option-title

      **vm_image_management_dest_name**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_dest_name" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Output image file name appended to vm\_image\_dest\_path in prerequisites.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_dest_path"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_dest_path:

      .. rst-class:: ansible-option-title

      **vm_image_management_dest_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_dest_path" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Destination path for the output image. In prerequisites, this is expanded to the final output image path by appending vm\_image\_dest\_name.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_download"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_download:

      .. rst-class:: ansible-option-title

      **vm_image_management_download**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_download" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      When false, the current create workflow runs. Download flow remains present but commented out in main.yml.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry-default:`false` :ansible-option-choices-default-mark:`← (default)`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_force"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_force:

      .. rst-class:: ansible-option-title

      **vm_image_management_force**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_force" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Reserved for future replacement behavior. Not used by the current task flow.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry-default:`false` :ansible-option-choices-default-mark:`← (default)`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_format"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_format:

      .. rst-class:: ansible-option-title

      **vm_image_management_format**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_format" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Output image format passed to qemu\-img convert \-O.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"qcow2"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_path"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_path:

      .. rst-class:: ansible-option-title

      **vm_image_management_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_path" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Reserved default variable for a full destination path. It is defined in defaults but is not used by the current task flow.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_resize"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_resize:

      .. rst-class:: ansible-option-title

      **vm_image_management_resize**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_resize" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Reserved for a future post\-create resize workflow. main.yml currently includes a TODO for this feature.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry-default:`false` :ansible-option-choices-default-mark:`← (default)`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--vm_image_management_size"></div>

      .. _ansible_collections.infra.ado.vm_image_management_role__parameter-main__vm_image_management_size:

      .. rst-class:: ansible-option-title

      **vm_image_management_size**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--vm_image_management_size" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Reserved for future image sizing workflows. Not used by the current task flow.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso





.. Extra links

Collection links
~~~~~~~~~~~~~~~~

.. ansible-links::

  - title: "Issue Tracker"
    url: "http://example.com/issue/tracker"
    external: true
  - title: "Homepage"
    url: "http://example.com"
    external: true
  - title: "Repository (Sources)"
    url: "http://example.com/repository"
    external: true
  - title: "Report an issue"
    url: "https://github.com/ansible-collections/infra.ado/issues/new/choose"
    external: true


.. Parsing errors
