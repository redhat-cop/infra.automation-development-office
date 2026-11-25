.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/filter/ocp_absent_cleanup_namespace_name_valid.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid_filter:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid filter -- Return whether a namespace name is one DNS\-1123 label
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This filter plugin is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid`.

.. version_added


.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- Return :literal:`true` when :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_name\_valid#filter:name` is a single DNS\-1123 label of at most 63 characters.
- Leading or trailing space, an empty value, a list, or a wildcard makes the result :literal:`false`.


.. Aliases


.. Requirements






.. Options

Keyword parameters
------------------

This describes keyword parameters of the filter plugin. These are the values ``key1=value1``, ``key2=value2`` and so on in the following
example: ``input | infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid(key1=value1, key2=value2, ...)``

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
        <div class="ansibleOptionAnchor" id="parameter-name"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid_filter__parameter-name:

      .. rst-class:: ansible-option-title

      **name**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-name" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Namespace name to check.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    {{ 'app' | infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid }}
    # true

    {{ 'kube-*' | infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid }}
    # false



.. Facts


.. Return values

Return Value
------------

.. tabularcolumns:: \X{1}{3}\X{2}{3}

.. list-table::
  :width: 100%
  :widths: auto
  :header-rows: 1
  :class: longtable ansible-option-table

  * - Key
    - Description

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-_value"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid_filter__return-_value:

      .. rst-class:: ansible-option-title

      **Return value**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-_value" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Whether :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_name\_valid#filter:name` is one DNS\-1123 label.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` success


      .. raw:: html

        </div>



..  Status (Presently only deprecated)


.. Authors

Authors
~~~~~~~

- Automation Development Office


.. Extra links

Collection links
~~~~~~~~~~~~~~~~

.. ansible-links::

  - title: "Issue Tracker"
    url: "https://github.com/redhat-cop/infra.automation-development-office/issues"
    external: true
  - title: "Repository (Sources)"
    url: "https://github.com/redhat-cop/infra.automation-development-office"
    external: true
  - title: "Report an issue"
    url: "https://github.com/ansible-collections/infra.automation_development_office/issues/new/choose"
    external: true


.. Parsing errors
