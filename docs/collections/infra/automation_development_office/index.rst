.. meta::
  :antsibull-docs: 2.29.1


.. _plugins_in_infra.automation_development_office:

Infra.Automation_Development_Office
===================================

Collection version 2.1.4

.. contents::
   :local:
   :depth: 1

Description
-----------

Automation Development Office roles for AAP, OpenShift, RHEL, Satellite, IdM, RHBK, and platform bootstrap workflows.

**Author:**

* Automation Development Office

**Supported ansible-core versions:**

* 2.17.0 or newer

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




.. toctree::
    :maxdepth: 1

.. _plugin_index_for_infra.automation_development_office:

Plugin Index
------------

These are the plugins in the infra.automation_development_office collection:

.. _module_plugins_in_infra.automation_development_office:

Modules
~~~~~~~

* :ansplugin:`ec2_ami_copy module <infra.automation_development_office.ec2_ami_copy#module>` --
* :ansplugin:`rhel_stig_cac_report module <infra.automation_development_office.rhel_stig_cac_report#module>` -- Build structured STIG findings from OpenSCAP results
* :ansplugin:`rhel_stig_cac_resolve module <infra.automation_development_office.rhel_stig_cac_resolve#module>` -- Resolve STIG controls to SCAP rules and write an OpenSCAP tailoring file

.. toctree::
    :maxdepth: 1
    :hidden:

    ec2_ami_copy_module
    rhel_stig_cac_report_module
    rhel_stig_cac_resolve_module

.. _filter_plugins_in_infra.automation_development_office:

Filter Plugins
~~~~~~~~~~~~~~

* :ansplugin:`ocp_absent_cleanup_cleanup_refused filter <infra.automation_development_office.ocp_absent_cleanup_cleanup_refused#filter>` -- Return whether ocp\_absent\_cleanup must not touch a namespace
* :ansplugin:`ocp_absent_cleanup_csv_name_matches filter <infra.automation_development_office.ocp_absent_cleanup_csv_name_matches#filter>` -- Return whether a CSV name is an exact or package.version match
* :ansplugin:`ocp_absent_cleanup_is_olm_copy filter <infra.automation_development_office.ocp_absent_cleanup_is_olm_copy#filter>` -- Return whether a CSV is an OLM copy rather than the operator CSV
* :ansplugin:`ocp_absent_cleanup_namespace_delete_blocked filter <infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked#filter>` -- Return whether ocp\_namespace must refuse to delete a namespace
* :ansplugin:`ocp_absent_cleanup_namespace_name_valid filter <infra.automation_development_office.ocp_absent_cleanup_namespace_name_valid#filter>` -- Return whether a namespace name is one DNS\-1123 label
* :ansplugin:`ocp_absent_cleanup_select_csvs filter <infra.automation_development_office.ocp_absent_cleanup_select_csvs#filter>` -- Return CSVs in a namespace that this run may delete
* :ansplugin:`ocp_absent_cleanup_select_installplans filter <infra.automation_development_office.ocp_absent_cleanup_select_installplans#filter>` -- Return InstallPlans in a namespace that this run may delete
* :ansplugin:`ocp_absent_cleanup_select_workloads filter <infra.automation_development_office.ocp_absent_cleanup_select_workloads#filter>` -- Return workloads in a namespace that this run may delete
* :ansplugin:`tls_first_pem_trust_bundle filter <infra.automation_development_office.tls_first_pem_trust_bundle#filter>` --
* :ansplugin:`tls_pem_looks_like_certificate filter <infra.automation_development_office.tls_pem_looks_like_certificate#filter>` --
* :ansplugin:`tls_split_pem_certificates filter <infra.automation_development_office.tls_split_pem_certificates#filter>` --
* :ansplugin:`tls_trust_bundle_from_secret filter <infra.automation_development_office.tls_trust_bundle_from_secret#filter>` --

.. toctree::
    :maxdepth: 1
    :hidden:

    ocp_absent_cleanup_cleanup_refused_filter
    ocp_absent_cleanup_csv_name_matches_filter
    ocp_absent_cleanup_is_olm_copy_filter
    ocp_absent_cleanup_namespace_delete_blocked_filter
    ocp_absent_cleanup_namespace_name_valid_filter
    ocp_absent_cleanup_select_csvs_filter
    ocp_absent_cleanup_select_installplans_filter
    ocp_absent_cleanup_select_workloads_filter
    tls_first_pem_trust_bundle_filter
    tls_pem_looks_like_certificate_filter
    tls_split_pem_certificates_filter
    tls_trust_bundle_from_secret_filter


.. _role_plugins_in_infra.automation_development_office:

Role Index
----------

These are the roles in the infra.automation_development_office collection:

* :ansplugin:`aap_build_ee role <infra.automation_development_office.aap_build_ee#role>` -- Build a custom Ansible execution environment image.
* :ansplugin:`capsule_install role <infra.automation_development_office.capsule_install#role>` --
* :ansplugin:`satellite_config role <infra.automation_development_office.satellite_config#role>` --
* :ansplugin:`satellite_install role <infra.automation_development_office.satellite_install#role>` --
* :ansplugin:`vm_image_management role <infra.automation_development_office.vm_image_management#role>` -- Create a qcow2 virtual machine image from an existing base image.

.. toctree::
    :maxdepth: 1
    :hidden:

    aap_build_ee_role
    capsule_install_role
    satellite_config_role
    satellite_install_role
    vm_image_management_role


.. seealso::

    List of :ref:`collections <list_of_collections>` with docs hosted here.
