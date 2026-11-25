.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/filter/ocp_absent_cleanup_cleanup_refused.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_cleanup_refused_filter:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.ocp_absent_cleanup_cleanup_refused filter -- Return whether ocp\_absent\_cleanup must not touch a namespace
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This filter plugin is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.ocp_absent_cleanup_cleanup_refused`.

.. version_added


.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- Return :literal:`true` when the built\-in control\-plane denylist, :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:guard.extra\_blocked`\ , or :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:guard.extra\_prefixes` matches :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:name`.
- Names other than :literal:`openshift\-operators` are allowed through this check once they pass the denylist.
- :literal:`openshift\-operators` is refused when :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:guard.mode` is not :literal:`check` and a sweep or unfiltered delete is authorized without a CSV name match.
- :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:guard` keys are :literal:`mode`\ , :literal:`sweep\_olm`\ , :literal:`csv\_name\_match`\ , :literal:`authorize\_unfiltered\_csv\_delete`\ , :literal:`delete\_copied\_csvs`\ , and :literal:`sweep\_workloads`.
- :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:guard` also accepts :literal:`authorize\_unfiltered\_workloads`\ , :literal:`extra\_blocked`\ , and :literal:`extra\_prefixes`.


.. Aliases


.. Requirements






.. Options

Keyword parameters
------------------

This describes keyword parameters of the filter plugin. These are the values ``key1=value1``, ``key2=value2`` and so on in the following
example: ``input | infra.automation_development_office.ocp_absent_cleanup_cleanup_refused(key1=value1, key2=value2, ...)``

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
        <div class="ansibleOptionAnchor" id="parameter-guard"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_cleanup_refused_filter__parameter-guard:

      .. rst-class:: ansible-option-title

      **guard**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-guard" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`dictionary`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Cleanup authorization for this run.

      Omitted or empty means only the built\-in denylist applies.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`{}`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-name"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_cleanup_refused_filter__parameter-name:

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

      Namespace name the cleanup run would touch.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    {{ 'kube-system' | infra.automation_development_office.ocp_absent_cleanup_cleanup_refused }}
    # true

    {{ 'openshift-operators' | infra.automation_development_office.ocp_absent_cleanup_cleanup_refused({'mode': 'check'}) }}
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

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_cleanup_refused_filter__return-_value:

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

      Whether ocp\_absent\_cleanup must not touch :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_cleanup\_refused#filter:name`.


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
