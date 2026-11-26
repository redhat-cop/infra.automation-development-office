.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/modules/rhel_stig_cac_resolve.py?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.rhel_stig_cac_resolve module -- Resolve STIG controls to SCAP rules and write an OpenSCAP tailoring file
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This module is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.rhel_stig_cac_resolve`.

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

- Reads a SCAP Security Guide (SSG) data stream installed on the managed host.
- Resolves STIG IDs (\ :literal:`RHEL\-09\-255100`\ ), vulnerability IDs (\ :literal:`V\-257996`\ ), rule IDs (\ :literal:`SV\-257996r1134915\_rule`\ ), or SSG rule names to SSG rules that the STIG profile selects.
- Adds rules that a selected rule :literal:`requires`\ , because XCCDF silently drops a rule whose requirement is not selected.
- Reports which resolved rules match a protected\-control pattern and were not explicitly allowed. The module never decides to proceed; the role does.
- When :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:controls` is set and :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:tailoring\_dest` is given, writes an XCCDF tailoring file that selects only the resolved rules. Running OpenSCAP with that file and :literal:`\-\-remediate` cannot touch any other control.
- Never modifies the system other than writing :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:tailoring\_dest`.


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
        <div class="ansibleOptionAnchor" id="parameter-allow_protected"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-allow_protected:

      .. rst-class:: ansible-option-title

      **allow_protected**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-allow_protected" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Controls (same formats as :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:controls`\ ) that may bypass :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:protected\_patterns`.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-controls"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-controls:

      .. rst-class:: ansible-option-title

      **controls**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-controls" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      STIG IDs, vulnerability IDs, rule IDs, or SSG rule names to select.

      When empty, nothing is resolved and no tailoring file is written.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-datastream"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-datastream:

      .. rst-class:: ansible-option-title

      **datastream**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-datastream" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`path` / :ansible-option-required:`required`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Path to the SSG data stream on the managed host.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-profile"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-profile:

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

      XCCDF profile ID that defines the available controls.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"xccdf\_org.ssgproject.content\_profile\_stig"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-protected_patterns"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-protected_patterns:

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

      Regular expressions matched against SSG rule names. A resolved rule that matches is reported in :ansretval:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:blocked\_protected` unless it is listed in :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:allow\_protected`.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-tailoring_dest"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-tailoring_dest:

      .. rst-class:: ansible-option-title

      **tailoring_dest**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-tailoring_dest" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`path`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Where to write the tailoring file. Written only when :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:controls` is set.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-tailoring_mode"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__parameter-tailoring_mode:

      .. rst-class:: ansible-option-title

      **tailoring_mode**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-tailoring_mode" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      File mode for :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:tailoring\_dest`.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"0640"`

      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    - name: Resolve two controls and write a tailoring file
      infra.automation_development_office.rhel_stig_cac_resolve:
        datastream: /usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml
        controls:
          - RHEL-09-255100
          - V-258083
        protected_patterns:
          - ^sshd_
        tailoring_dest: /var/lib/ado/stig/tailoring.xml
      register: stig_resolved



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
        <div class="ansibleOptionAnchor" id="return-benchmark_version"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-benchmark_version:

      .. rst-class:: ansible-option-title

      **benchmark_version**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-benchmark_version" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      SSG benchmark version, for example :literal:`0.1.82`.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-blocked_protected"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-blocked_protected:

      .. rst-class:: ansible-option-title

      **blocked_protected**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-blocked_protected" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Selected rules that match a protected pattern and were not allowed.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-dependencies"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-dependencies:

      .. rst-class:: ansible-option-title

      **dependencies**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-dependencies" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Rules added because another selected rule requires them.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-not_in_profile"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-not_in_profile:

      .. rst-class:: ansible-option-title

      **not_in_profile**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-not_in_profile" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Controls known to the data stream that the profile does not select.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-profile_found"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-profile_found:

      .. rst-class:: ansible-option-title

      **profile_found**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-profile_found" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Whether :ansopt:`infra.automation\_development\_office.rhel\_stig\_cac\_resolve#module:profile` exists in the data stream.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-profile_rule_count"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-profile_rule_count:

      .. rst-class:: ansible-option-title

      **profile_rule_count**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-profile_rule_count" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`integer`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Number of rules the profile selects.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-resolved"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-resolved:

      .. rst-class:: ansible-option-title

      **resolved**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-resolved" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Each input control mapped to the SSG rules it selects.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-rules"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-rules:

      .. rst-class:: ansible-option-title

      **rules**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-rules" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Sorted SSG rule names selected, including required rules.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` always


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-tailoring_path"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-tailoring_path:

      .. rst-class:: ansible-option-title

      **tailoring_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-tailoring_path" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Path of the tailoring file written.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` when a tailoring file was requested


      .. raw:: html

        </div>


  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-unmatched"></div>

      .. _ansible_collections.infra.automation_development_office.rhel_stig_cac_resolve_module__return-unmatched:

      .. rst-class:: ansible-option-title

      **unmatched**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-unmatched" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Controls that are not in the data stream.


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
