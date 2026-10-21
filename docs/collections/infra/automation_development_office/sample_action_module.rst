.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.ado/edit/main/plugins/modules/sample_action.py?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.24.0

.. Anchors

.. _ansible_collections.infra.ado.sample_action_module:

.. Anchors: short name for ansible.builtin

.. Title

infra.ado.sample_action module -- A custom action plugin for Ansible.
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This module is part of the `infra.ado collection <https://galaxy.ansible.com/ui/repo/published/infra/ado/>`_ (version 1.0.0).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.ado`.

    To use it in a playbook, specify: :code:`infra.ado.sample_action`.

.. version_added

.. rst-class:: ansible-version-added

New in infra.ado 1.0.0

.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- This is a custom action plugin to provide action functionality.

.. note::
    This module has a corresponding :ref:`action plugin <action_plugins>`.

.. Aliases


.. Requirements






.. Options

Parameters
----------

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
        <div class="ansibleOptionAnchor" id="parameter-msg"></div>

      .. _ansible_collections.infra.ado.sample_action_module__parameter-msg:

      .. rst-class:: ansible-option-title

      **msg**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-msg" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      The message to display in the output.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-prefix"></div>

      .. _ansible_collections.infra.ado.sample_action_module__parameter-prefix:

      .. rst-class:: ansible-option-title

      **prefix**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-prefix" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      A string that is added as a prefix to the message passed to the module.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-with_prefix"></div>

      .. _ansible_collections.infra.ado.sample_action_module__parameter-with_prefix:

      .. rst-class:: ansible-option-title

      **with_prefix**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-with_prefix" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      A boolean flag indicating whether to include the prefix in the message.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry:`false`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>


.. Attributes


.. Notes

Notes
-----

.. note::
   - This is a scaffold template. Customize the plugin to fit your needs.

.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    - name: Example Action Plugin
      hosts: localhost
      tasks:
        - name: Example sample_action plugin
          with_prefix:
            prefix: "Hello, World"
            msg: "Ansible!"



.. Facts


.. Return values


..  Status (Presently only deprecated)


.. Authors

Authors
~~~~~~~

- Your Name (@username)


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
