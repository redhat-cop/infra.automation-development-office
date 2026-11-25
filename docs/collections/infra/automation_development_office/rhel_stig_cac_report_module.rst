.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/modules/rhel_stig_cac_report.py?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.rhel_stig_cac_report module -- Build structured STIG findings from OpenSCAP results
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This module is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.rhel_stig_cac_report`.

.. version_added

.. rst-class:: ansible-version-added

New in infra.automation\_development\_office 2.2.0

.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- Parses the XCCDF results file written by :literal:`oscap xccdf eval \-\-results`.
- Joins each rule result with its STIG ID, vulnerability ID, rule ID, SRG, and CAT severity from the SCAP Security Guide data stream.
- Writes a machine\-readable findings file and returns a summary. The summary is what the role uses to pass or fail a run, so a failed control is never hidden behind a successful :literal:`oscap` exit code.
- When :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:selected\_rules` is set, every selected rule appears in the output. A selected rule OpenSCAP did not evaluate has status :literal:`not\_evaluated`.
- Never modifies the system other than writing :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:findings\_dest`.


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
        <div class="ansibleOptionAnchor" id="parameter-context"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-context:

      .. rst-class:: ansible-option-title

      **context**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-context" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Free\-form values copied into the findings file, such as :literal:`mode` and :literal:`host`.

      Must not contain secrets.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`{}`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-datastream"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-datastream:

      .. rst-class:: ansible-option-title

      **datastream**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-datastream" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`path`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      SSG data stream used for the scan. Supplies STIG metadata.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-findings_dest"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-findings_dest:

      .. rst-class:: ansible-option-title

      **findings_dest**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-findings_dest" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`path`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Where to write the findings JSON file.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-findings_mode"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-findings_mode:

      .. rst-class:: ansible-option-title

      **findings_mode**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-findings_mode" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      File mode for :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:findings\_dest`.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"0640"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-include_not_selected"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-include_not_selected:

      .. rst-class:: ansible-option-title

      **include_not_selected**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-include_not_selected" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Include rules the profile did not select (large output).


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry-default:`false` :ansible-option-choices-default-mark:`← (default)`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-profile"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-profile:

      .. rst-class:: ansible-option-title

      **profile**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-profile" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Base profile ID in :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:datastream`.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"xccdf\_org.ssgproject.content\_profile\_stig"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-protected_patterns"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-protected_patterns:

      .. rst-class:: ansible-option-title

      **protected_patterns**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-protected_patterns" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Regular expressions marking a rule as protected in the findings.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-results_path"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-results_path:

      .. rst-class:: ansible-option-title

      **results_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-results_path" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`path` / :ansible-option-required:`required`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      XCCDF results file written by :literal:`oscap xccdf eval \-\-results`.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-return_findings"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-return_findings:

      .. rst-class:: ansible-option-title

      **return_findings**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-return_findings" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Return the full findings list in :ansretval:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:findings`. The findings file always has them; leave this off to keep job output small.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry-default:`false` :ansible-option-choices-default-mark:`← (default)`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-selected_rules"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__parameter-selected_rules:

      .. rst-class:: ansible-option-title

      **selected_rules**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-selected_rules" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      SSG rule names that were selected for the scan. This is the :literal:`rules` value returned by :ref:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve <ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module>`.

      When empty, all evaluated rules are reported.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    - name: Build findings from an audit
      infra.automation_development_office.rhel_stig_cac_report:
        results_path: /var/lib/ado/stig/audit-results.xml
        datastream: /usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml
        context:
          mode: audit
        findings_dest: /var/lib/ado/stig/audit-findings.json
      register: stig_report



.. Facts


.. Return values

Return Values
-------------
Common return values are documented :ref:`here <common_return_values>`, the following are the fields unique to this module:

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
        <div class="ansibleOptionAnchor" id="return-failures"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__return-failures:

      .. rst-class:: ansible-option-title

      **failures**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-failures" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Failed, errored, and not\-evaluated controls.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-findings"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__return-findings:

      .. rst-class:: ansible-option-title

      **findings**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-findings" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Every reported control with STIG metadata and status.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` when :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:return\_findings=true`


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-findings_path"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__return-findings_path:

      .. rst-class:: ansible-option-title

      **findings_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-findings_path" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Path of the findings file written.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` when :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_report#module:findings\_dest` is set


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-scan"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__return-scan:

      .. rst-class:: ansible-option-title

      **scan**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-scan" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Scan metadata from the results file (profile, target, times, score).


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-summary"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_report_module__return-summary:

      .. rst-class:: ansible-option-title

      **summary**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-summary" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Counts, failures by CAT, and compliance percentage.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>



..  Status (Presently only deprecated)


.. Authors

Authors
~~~~~~~

- Automation Development Office (@Automation-Development-Office)


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
