"""
Build a lightweight HTML report: all data lives in a JS array,
one table renders it with client-side sort/filter/search.
"""

import re as _re
from collections import Counter
import csv
import json
import os
import sys
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CVE_DATA_DIR', os.path.join(BASE_DIR, "data"))
REPORT_ID = os.path.basename(DATA_DIR)
TRIAGE_CSV = os.path.join(DATA_DIR, "triage.csv")
SCAN_JSON = os.path.join(DATA_DIR, "roxctl_scan_results.json")
RH_SCORES_JSON = os.path.join(DATA_DIR, "redhat_cve_scores.json")
LATEST_JSON = os.path.join(DATA_DIR, "latest_scan_results.json")
RHSA_DESC_JSON = os.path.join(DATA_DIR, "rhsa_descriptions.json")
KEV_JSON = os.path.join(DATA_DIR, "kev_matches.json")
OUTPUT = os.path.join(DATA_DIR, "report.html")
DATA_JSON_OUTPUT = os.path.join(DATA_DIR, "data.json")
REPORT_NAME = os.environ.get('REPORT_NAME', '')

rows = list(csv.DictReader(open(TRIAGE_CSV)))
scan = json.load(open(SCAN_JSON))
rh_scores = json.load(open(RH_SCORES_JSON))
try:
    rhsa_descs = json.load(open(RHSA_DESC_JSON))
except FileNotFoundError:
    rhsa_descs = {}
try:
    kev_matches = json.load(open(KEV_JSON))
except FileNotFoundError:
    kev_matches = {}
latest_data = json.load(open(LATEST_JSON))
fix_results = latest_data.get('fix_results', {})

# roxctl lookup
rox_lk = {}
for img, res in scan.items():
    if 'error' in res:
        continue
    for v in res.get('vulnerabilities', []):
        rox_lk[f"{img}|||{v.get('cveId', '')}"] = v.get('componentFixedVersion', '')

for row in rows:
    k = f"{row['Image_Full']}|||{row['CVE']}"
    if k in rox_lk:
        row['rox'] = 'CONFIRMED'
        row['roxf'] = rox_lk[k]
    elif row['Image_Full'] in scan and 'error' not in scan[row['Image_Full']]:
        row['rox'] = 'NOT_FOUND'
        row['roxf'] = ''
    else:
        row['rox'] = 'SCAN_ERROR'
        row['roxf'] = ''

    # Latest image fix verification
    fix_key = f"{row['Image_Full']}|||{row['CVE']}"
    fix = fix_results.get(fix_key, {})
    row['fix_status'] = fix.get('status', 'UNKNOWN')
    row['fix_latest_ref'] = fix.get('latest_ref', '')
    row['fix_latest_tag'] = fix.get('latest_tag', '')
    row['fix_catalog_url'] = fix.get('catalog_url', '')

    rhsa_id = row.get('RHSA_Advisory', '')
    rhsa_info = rhsa_descs.get(rhsa_id, {})
    row['rhsa_description'] = rhsa_info.get('description', '')

# Enrich with Red Hat CVSS scores and re-prioritize
for row in rows:
    cve = row['CVE']
    rh = rh_scores.get(cve, {})
    row['rh_cvss'] = str(rh.get('score', 0))
    row['rh_severity'] = rh.get('severity', '')
    row['rh_vector'] = rh.get('vector', '')
    row['rh_mitigation'] = rh.get('mitigation', '')
    row['rh_statement'] = rh.get('statement', '')

    rh_score = float(row['rh_cvss'])
    epss = float(row.get('EPSS_Pct', '0') or '0')

    # Re-prioritize using Red Hat CVSS as authoritative
    # Use Red Hat score when available (>0), fall back to existing CVSS
    auth_cvss = rh_score if rh_score > 0 else float(row.get('CVSS', '0') or '0')
    rh_sev = row['rh_severity']

    if (rh_sev == 'Critical') or (auth_cvss >= 9.0 and epss >= 1.0):
        row['Priority'] = 'P1-CRITICAL'
        row['Action'] = 'PATCH'
    elif epss >= 10.0:
        row['Priority'] = 'P1-HIGH-EPSS'
        row['Action'] = 'PATCH'
    elif auth_cvss >= 9.0 or (auth_cvss >= 8.0 and epss >= 1.0):
        row['Priority'] = 'P2-HIGH-IMPACT'
        row['Action'] = 'PATCH'
    elif epss >= 5.0:
        row['Priority'] = 'P2-HIGH-EPSS'
        row['Action'] = 'PATCH'
    elif auth_cvss >= 8.0 or (auth_cvss >= 7.0 and epss >= 1.0):
        row['Priority'] = 'P3-MODERATE'
        row['Action'] = 'PATCH'
    elif auth_cvss >= 7.0 or (rh_sev == 'Important' and auth_cvss >= 6.0):
        row['Priority'] = 'P4-MONITOR'
        row['Action'] = 'MONITOR'
    else:
        row['Priority'] = 'P5-LOW'
        row['Action'] = 'MONITOR'

    # Update triage reasoning to reference Red Hat score
    if rh_score > 0:
        row['Triage_Reasoning'] = (
            f"Red Hat CVSS {rh_score:.1f} ({rh_sev}), "
            f"EPSS {epss:.3f}%"
            + (f", NVD CVSS {row.get('CVSS', '')}" if row.get('CVSS', '') and row.get('CVSS', '') != '0' else '')
        )

for row in rows:
    kev = kev_matches.get(row['CVE'], {})
    row['kev_date_added'] = kev.get('dateAdded', '')
    row['kev_due_date'] = kev.get('dueDate', '')

print(f"Re-prioritized {len(rows)} records using Red Hat CVSS scores")
new_pri = Counter(r['Priority'] for r in rows)
new_act = Counter(r['Action'] for r in rows)
print(f"  Priorities: {dict(sorted(new_pri.items()))}")
print(f"  Actions: {dict(new_act)}")

rh_not_found = {k for k, v in rh_scores.items() if v.get('status') == 'not_found'}


def build_cve_links(cve_id):
    """Build prioritized links: Red Hat > NVD > OSV for CVE-*, OSV for GHSA-*.
    If the CVE doesn't exist in the Red Hat DB, fall back to NVD > OSV."""
    if cve_id.startswith('CVE-'):
        rh = f'https://access.redhat.com/security/cve/{cve_id}'
        nvd = f'https://nvd.nist.gov/vuln/detail/{cve_id}'
        osv = f'https://osv.dev/vulnerability/{cve_id}'
        if cve_id in rh_not_found:
            return (nvd, osv, '')
        return (rh, nvd, osv)
    elif cve_id.startswith('GHSA-'):
        return (
            f'https://osv.dev/vulnerability/{cve_id}',
            f'https://github.com/advisories/{cve_id}',
            '',
        )
    return ('', '', '')


# Compact records for JS
R = []
for i, r in enumerate(rows):
    link1, link2, link3 = build_cve_links(r['CVE'])
    R.append([
        r['Priority'],           # 0
        r['Action'],             # 1
        r['CVE'],                # 2
        r['Severity'],           # 3
        r.get('CVSS', ''),        # 4
        r.get('NVD_CVSS', ''),    # 5
        r.get('EPSS_Pct', ''),    # 6
        r.get('Product_Line', ''),  # 7
        r.get('Image_Short', ''),  # 8
        r.get('Image_Full', ''),  # 9
        r.get('Cluster', ''),     # 10
        r.get('Namespaces', ''),  # 11
        r.get('Deployments', ''),  # 12
        r.get('Affected_Components', ''),  # 13
        r.get('Component_Versions', ''),   # 14
        r.get('Fixed_In', ''),    # 15
        r.get('RHSA_Advisory', ''),        # 16
        r.get('Advisory_Link', ''),        # 17
        link1,                   # 18 — primary link (Red Hat for CVE, OSV for GHSA)
        r.get('Remediation_Path', ''),     # 19
        r.get('Triage_Reasoning', ''),     # 20
        r.get('OSV_Verification', ''),     # 21
        r.get('OSV_Affected_Range', ''),   # 22
        r.get('POAM_Justification', ''),   # 23
        r.get('Discovered', ''),  # 24
        r.get('rox', ''),         # 25
        r.get('roxf', ''),        # 26
        link2,                   # 27 — secondary link (NVD for CVE, GitHub for GHSA)
        link3,                   # 28 — tertiary link (OSV for CVE, empty for GHSA)
        r.get('rh_cvss', '0'),   # 29 — Red Hat CVSS score
        r.get('rh_severity', ''),  # 30 — Red Hat severity
        r.get('rh_vector', ''),  # 31 — Red Hat CVSS vector
        r.get('fix_status', ''),  # 32 — latest image fix status
        r.get('fix_latest_ref', ''),  # 33 — latest image ref
        r.get('fix_latest_tag', ''),  # 34 — latest image tag
        r.get('fix_catalog_url', ''),  # 35 — catalog.redhat.com URL
        r.get('rhsa_description', ''),  # 36 — RHSA advisory description
        r.get('rh_mitigation', ''),  # 37 — Red Hat CVE mitigation
        r.get('rh_statement', ''),   # 38 — Red Hat CVE statement
        r.get('kev_date_added', ''),  # 39 — CISA KEV date added (empty = not in KEV)
        r.get('kev_due_date', ''),   # 40 — CISA KEV due date
    ])

data_json = json.dumps(R, separators=(',', ':'))


def detect_ocp_version():
    """Detect OCP version from image paths or fall back to OCP_TARGET_VERSION."""
    version_counts = defaultdict(int)
    for r in rows:
        img = r.get('Image_Full', '')
        m = _re.search(r'ocp-release[:/]v?(\d+\.\d+\.\d+)', img)
        if m:
            version_counts[m.group(1)] += 1
            continue
        m = _re.search(r'openshift4/ose-[^:]*:v(\d+\.\d+\.\d+)', img)
        if m:
            version_counts[m.group(1)] += 1
            continue
        for tag in (r.get('fix_latest_tag', ''),):
            m = _re.match(r'^(\d+\.\d+\.\d+)(?:\s|$)', tag)
            if m:
                version_counts[m.group(1)] += 1
    if version_counts:
        return max(version_counts, key=version_counts.get)
    return os.environ.get('OCP_TARGET_VERSION', '')


ocp_version = detect_ocp_version()
report_name = REPORT_NAME or REPORT_ID
if ocp_version:
    report_title = f'OpenShift {ocp_version} - CVE Triage Report - {report_name}'
    page_title = f'OCP {ocp_version} - CVE Triage Report - {report_name}'
else:
    report_title = f'OpenShift CVE Triage Report - {report_name}'
    page_title = f'OCP CVE Triage Report - {report_name}'
print(f"Report title: {report_title}")

# Stats
pc = defaultdict(int)
ac = defaultdict(int)
for r in R:
    pc[r[0]] += 1
    ac[r[1]] += 1
ucve = len(set(r[2] for r in R))
uimg = len(set(r[8] for r in R))
rox_ok = sum(1 for r in R if r[25] == 'CONFIRMED')
osv_ok = sum(1 for r in R if r[21].startswith('Confirmed'))
fix_fixed = sum(1 for r in R if r[32] == 'FIXED_IN_LATEST')
fix_still = sum(1 for r in R if r[32] == 'STILL_VULNERABLE')
kev_records = [r for r in R if r[39]]
kev_unique_cves = sorted(set(r[2] for r in kev_records))

# Executive summary tables
rem_sum = defaultdict(lambda: {'p': 0, 'm': 0, 'p1': 0, 'c': set()})
prod_sum = defaultdict(lambda: {'t': 0, 'p': 0, 'p1': 0, 'c': set(), 'i': set()})
for r in R:
    rem = r[19] or 'Unknown'
    rem_sum[rem]['p' if r[1] == 'PATCH' else 'm'] += 1
    if r[0].startswith('P1'):
        rem_sum[rem]['p1'] += 1
    rem_sum[rem]['c'].add(r[2])
    pl = r[7]
    prod_sum[pl]['t'] += 1
    if r[1] == 'PATCH':
        prod_sum[pl]['p'] += 1
    if r[0].startswith('P1'):
        prod_sum[pl]['p1'] += 1
    prod_sum[pl]['c'].add(r[2])
    prod_sum[pl]['i'].add(r[8])


def e(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# Build exec summary HTML
exec_html = ''
if kev_unique_cves:
    kev_by_cve = defaultdict(int)
    kev_info = {}
    for r in kev_records:
        kev_by_cve[r[2]] += 1
        if r[2] not in kev_info:
            kev_info[r[2]] = (r[39], r[40])
    exec_html += '<div class="es kev-summary"><h3 style="color:#f59e0b">&#9888; CISA Known Exploited Vulnerabilities</h3>'
    exec_html += (
        f'<p class="esub">{len(kev_unique_cves)} CVE(s) in the '
        '<a href="https://www.cisa.gov/known-exploited-vulnerabilities-catalog" '
        'target="_blank">CISA KEV catalog</a>. These have confirmed active '
        'exploitation and carry mandatory remediation deadlines per BOD 22-01.</p>'
    )
    exec_html += '<table><thead><tr><th>CVE</th><th>Date Added</th><th>Due Date</th><th>Records</th></tr></thead><tbody>'
    for cve in kev_unique_cves:
        added, due = kev_info[cve]
        exec_html += f'<tr onclick="drill(\'cve\',\'{
            e(cve)}\')"><td><a href="https://access.redhat.com/security/cve/{
            e(cve)}" target="_blank" onclick="event.stopPropagation()">{
            e(cve)}</a></td>'
        exec_html += f'<td>{e(added)}</td><td style="color:#f59e0b;font-weight:600">{e(due)}</td><td class="n">{kev_by_cve[cve]}</td></tr>'
    exec_html += '</tbody></table></div>'

exec_html += '<div class="es"><h3>Remediation Action Summary</h3>'
exec_html += '<p class="esub">What you need to do and how many CVE+image records each action covers.</p>'
exec_html += '<table><thead><tr><th>Remediation Action</th><th>PATCH</th><th>MONITOR</th><th>P1</th><th>CVEs</th></tr></thead><tbody>'
for rem in sorted(rem_sum.keys(), key=lambda r: -rem_sum[r]['p']):
    s = rem_sum[rem]
    exec_html += f'<tr onclick="drill(\'remediation\',this.dataset.v)" data-v="{
        e(rem)}"><td>{
        e(rem)}</td><td class="n r">{
            s["p"] or "—"}</td><td class="n">{
                s["m"] or "—"}</td>'
    exec_html += f'<td class="n{" r" if s["p1"] else ""}">{s["p1"] or "—"}</td><td class="n">{len(s["c"])}</td></tr>'
exec_html += '</tbody></table></div>'

exec_html += '<div class="es"><h3>Product Line Summary</h3>'
exec_html += '<p class="esub">CVE exposure by product — use the Product filter below to drill in.</p>'
exec_html += '<table><thead><tr><th>Product</th><th>Images</th><th>Total</th><th>PATCH</th><th>P1</th><th>CVEs</th></tr></thead><tbody>'
for pl in sorted(prod_sum.keys(), key=lambda p: -prod_sum[p]['p']):
    s = prod_sum[pl]
    exec_html += f'<tr onclick="drill(\'product\',this.dataset.v)" data-v="{e(pl)}"><td>{e(pl)}</td><td class="n">{len(s["i"])}</td><td class="n">{s["t"]}</td>'
    exec_html += f'<td class="n r">{s["p"] or "—"}</td><td class="n{" r" if s["p1"] else ""}">{s["p1"] or "—"}</td>'
    exec_html += f'<td class="n">{len(s["c"])}</td></tr>'
exec_html += '</tbody></table></div>'

exec_html += '<div class="es"><h3>Priority Breakdown</h3><table><thead><tr><th>Priority</th><th>Count</th><th>Criteria</th></tr></thead><tbody>'
pd = {'P1-CRITICAL': 'Red Hat Critical severity, or RH CVSS >= 9.0 + EPSS >= 1%',
      'P1-HIGH-EPSS': 'EPSS >= 10% — high exploitation probability',
      'P2-HIGH-IMPACT': 'RH CVSS >= 9.0, or RH CVSS >= 8.0 + EPSS >= 1%',
      'P2-HIGH-EPSS': 'EPSS >= 5% — elevated exploitation risk',
      'P3-MODERATE': 'RH CVSS >= 8.0, or RH CVSS >= 7.0 + EPSS >= 1%',
      'P4-MONITOR': 'RH CVSS >= 7.0 (or Important + >= 6.0), low EPSS',
      'P5-LOW': 'Low RH CVSS or no score — informational'}
for p in ['P1-CRITICAL', 'P1-HIGH-EPSS', 'P2-HIGH-IMPACT', 'P2-HIGH-EPSS', 'P3-MODERATE', 'P4-MONITOR', 'P5-LOW']:
    if pc.get(p, 0):
        exec_html += f'<tr onclick="drill(\'priority\',\'{e(p)}\')"><td>{e(p)}</td><td class="n">{pc[p]}</td><td class="tm">{e(pd.get(p, ""))}</td></tr>'
exec_html += '</tbody></table></div>'

# Products list for filter dropdown
products = sorted(set(r[7] for r in R))
prod_options = ''.join(f'<option value="{e(p)}">{e(p)}</option>' for p in products)

html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<link rel="icon" href="https://access.redhat.com/favicon.ico" type="image/x-icon">
<style>
:root{{--bg:#0f172a;--sf:#1e293b;--sf2:#334155;--tx:#e2e8f0;--tm:#94a3b8;--bd:#475569;--ac:#38bdf8;--rd:#ef4444;--gn:#22c55e;--or:#f97316}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;background:var(--bg);color:var(--tx);line-height:1.5;padding:16px;font-size:14px}}
h1{{font-size:1.3rem;font-weight:600}}
.sub{{color:var(--tm);font-size:.78rem;margin-bottom:14px}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:16px}}
.c{{background:var(--sf);border-radius:6px;padding:10px 12px;border:1px solid var(--bd)}}
.cl{{font-size:.6rem;text-transform:uppercase;letter-spacing:.05em;color:var(--tm)}}
.cv{{font-size:1.3rem;font-weight:700}}
.r{{color:var(--rd)}}.o{{color:var(--or)}}.bl{{color:var(--ac)}}.gr{{color:var(--gn)}}
.n{{text-align:right}}
.b{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.63rem;font-weight:600;color:#fff;white-space:nowrap}}
.tabs{{display:flex;border-bottom:2px solid var(--bd);margin-bottom:12px}}
.tab{{padding:6px 14px;cursor:pointer;color:var(--tm);border-bottom:2px solid transparent;margin-bottom:-2px;font-size:.82rem;font-weight:500}}
.tab:hover{{color:var(--tx)}}.tab.on{{color:var(--ac);border-bottom-color:var(--ac)}}
.tc{{display:none}}.tc.on{{display:block}}
.bar{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;align-items:center}}
.sb{{flex:1;min-width:200px;padding:6px 10px;border-radius:5px;border:1px solid var(--bd);background:var(--sf);color:var(--tx);font-size:.8rem;outline:none}}
.sb:focus{{border-color:var(--ac)}}
.fb{{padding:3px 10px;border-radius:4px;border:1px solid var(--bd);background:var(--sf);color:var(--tx);cursor:pointer;font-size:.72rem}}
.fb:hover{{border-color:var(--ac)}}.fb.on{{background:var(--ac);color:var(--bg);border-color:var(--ac);font-weight:600}}
select.fb{{appearance:auto;padding:3px 6px}}
.tw{{overflow-x:auto;max-height:60vh;overflow-y:auto}}
table{{width:100%;border-collapse:collapse;font-size:.75rem}}
th{{background:var(--sf2);color:var(--tm);font-weight:600;text-align:left;padding:5px 7px;position:sticky;top:0;z-index:2;font-size:.65rem;text-transform:upperc
ase;letter-spacing:.03em;cursor:pointer;white-space:nowrap}}
th:hover{{color:var(--ac)}}
td{{padding:5px 7px;border-bottom:1px solid var(--bd);vertical-align:top}}
tr.dr{{cursor:pointer}}tr.dr:hover td{{background:rgba(56,189,248,.05)}}
tr.sel td{{background:rgba(56,189,248,.1)}}
.dp{{background:var(--sf);border:1px solid var(--bd);border-radius:8px;padding:14px 18px;margin-top:10px;display:none;box-shadow:0 -2px 12px rgba(0,0,0,.3)}}
.dp.on{{display:block}}
.dp .x{{float:right;cursor:pointer;color:var(--tm);font-size:1.1rem}}.dp .x:hover{{color:var(--tx)}}
.dg{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}}
.dl{{font-size:.62rem;color:var(--tm);text-transform:uppercase;letter-spacing:.03em}}
.dv{{font-size:.78rem;word-break:break-word}}
.bx{{border-radius:5px;padding:7px 10px;margin-top:6px;font-size:.78rem}}
.bx .bl2{{font-size:.62rem;text-transform:uppercase;letter-spacing:.03em;margin-bottom:2px}}
.bxr{{background:#1a2332;border:1px solid #1e40af}}.bxr .bl2{{color:#60a5fa}}
.bxa{{background:#0c1f2d;border:1px solid #0e7490}}.bxa .bl2{{color:#22d3ee}}
.bxg{{background:#0f1a12;border:1px solid #166534}}.bxg .bl2{{color:#4ade80}}
.bxp{{background:#1f1a10;border:1px solid #854d0e}}.bxp .bl2{{color:#fbbf24}}
.eb{{display:inline-block;height:4px;border-radius:2px;background:var(--sf2);width:40px;vertical-align:middle}}
.ef{{height:100%;border-radius:2px}}
a{{color:var(--ac);text-decoration:none}}a:hover{{text-decoration:underline}}
.es{{background:var(--sf);border-radius:6px;padding:12px 14px;border:1px solid var(--bd);margin-bottom:10px;font-size:.78rem}}
.es h3{{font-size:.88rem;margin-bottom:6px;color:var(--ac)}}
.esub{{color:var(--tm);margin-bottom:8px;font-size:.72rem}}
.es table{{font-size:.72rem}}.es td,.es th{{padding:3px 7px}}
.tm{{color:var(--tm)}}
.cnt{{font-size:.72rem;color:var(--tm);margin:4px 0}}
@media print{{body{{background:#fff;color:#000}}.tw{{max-height:none}}}}
.prow td{{opacity:.45}}.pcb{{width:14px;height:14px;cursor:pointer;accent-color:var(--ac)}}
.pbtn{{padding:2px 8px;border-radius:4px;border:1px solid var(--bd);background:var(--sf);color:var(--tm);cursor:pointer;font-size:.7rem;white-space:nowrap}}
.pbtn:hover{{border-color:var(--ac);color:var(--ac)}}
.fprow td{{opacity:.45}}.fpbtn{{padding:1px 6px;border-radius:4px;border:1px solid var(--bd);background:var(--sf);color:var(--tm);cursor:pointer;font-size:.65re
m;white-space:nowrap}}.fpbtn:hover{{border-color:var(--rd);color:var(--rd)}}.fpflag{{cursor:pointer;font-size:.85rem;user-select:none}}
.kevrow{{background:rgba(245,158,11,.05)!important}}.kevrow>td:first-child{{border-left:3px solid #f59e0b}}
.kev{{display:inline-block;padding:1px 5px;border-radius:3px;font-size:.55rem;font-weight:700;color:#fff;background:linear-gradient(135deg,#dc2626,#f59e0b);anim
ation:kevpulse 2s ease-in-out infinite;vertical-align:middle;margin-left:3px;letter-spacing:.03em}}
@keyframes kevpulse{{0%,100%{{box-shadow:0 0 3px rgba(245,158,11,.3)}}50%{{box-shadow:0 0 8px rgba(245,158,11,.6),0 0 16px rgba(220,38,38,.2)}}}}
.kev-summary{{border-color:#f59e0b!important;background:linear-gradient(135deg,#1a1708,#1f1a0a)!important}}
.es tr[onclick]{{cursor:pointer}}.es tr[onclick]:hover td{{background:rgba(56,189,248,.08)}}
.c[onclick]{{cursor:pointer;transition:all .15s}}.c[onclick]:hover{{border-color:var(--ac)}}
</style></head><body>
<h1>{report_title}</h1>
<p class="sub">Generated Aug 25, 2026 &bull; Clusters: prod, prod-infra &bull; RHACS scan Aug 21 &bull; Verified: roxctl + OSV &bull; Prioritized by Red Hat
CVSS &bull; {len(R):,} records, {ucve} CVEs, {uimg} images</p>
<div class="g">
<div class="c" onclick="drill('all')"><div class="cl">Records</div><div class="cv">{len(R):,}</div></div>
<div class="c" onclick="drill('all')"><div class="cl">CVEs</div><div class="cv">{ucve}</div></div>
<div class="c" onclick="drill('action','PATCH')"><div class="cl">PATCH</div><div class="cv r">{ac['PATCH']:,}</div></div>
<div class="c" onclick="drill('action','MONITOR')"><div class="cl">MONITOR</div><div class="cv bl">{ac['MONITOR']:,}</div></div>
<div class="c" onclick="drill('priority','P1')">
<div class="cl">P1 Critical</div>
<div class="cv r">{pc.get('P1-CRITICAL', 0) + pc.get('P1-HIGH-EPSS', 0)}</div>
</div>
<div class="c" onclick="drill('priority','P2')">
<div class="cl">P2 High</div>
<div class="cv o">{pc.get('P2-HIGH-IMPACT', 0) + pc.get('P2-HIGH-EPSS', 0)}</div>
</div>
<div class="c" onclick="drill('fix','FIXED_IN_LATEST')"><div class="cl">Fixed in Latest</div><div class="cv gr">{fix_fixed:,}</div></div>
<div class="c" onclick="drill('fix','STILL_VULNERABLE')"><div class="cl">Not Fixed</div><div class="cv r">{fix_still:,}</div></div>
<div class="c" onclick="drill('kev')" style="border-color:#f59e0b">
<div class="cl">CISA KEV</div>
<div class="cv" style="color:{'#f59e0b' if kev_unique_cves else 'var(--gn)'}">{len(kev_unique_cves)}</div>
</div>
</div>

<div class="tabs">
<div class="tab on" onclick="stab(this,'exec')">Summary</div>
<div class="tab" onclick="stab(this,'data')">CVE Data</div>
<div class="tab" onclick="stab(this,'proc')">Processed <span id="procCnt" class="b" style="background:var(--bd);font-size:.6rem">0</span></div>
<div class="tab" onclick="stab(this,'fp')">Potential False Positives <span id="fpCnt" class="b" style="background:var(--bd);font-size:.6rem">0</span></div>
</div>

<div class="tc on" id="tc-exec">{exec_html}</div>

<div class="tc" id="tc-data">
<div class="bar">
<input class="sb" id="q" placeholder="Search any field..." oninput="drillPred=null;filt()">
<button class="fb on" onclick="sf(this,'all')">All</button>
<button class="fb" onclick="sf(this,'PATCH')">PATCH</button>
<button class="fb" onclick="sf(this,'MONITOR')">MONITOR</button>
<span style="color:var(--bd)">|</span>
<button class="fb" onclick="sf(this,'P1')">P1</button>
<button class="fb" onclick="sf(this,'P2')">P2</button>
<button class="fb" onclick="sf(this,'P3')">P3</button>
<button class="fb" onclick="sf(this,'P4')">P4</button>
<button class="fb" onclick="sf(this,'P5')">P5</button>
<span style="color:var(--bd)">|</span>
<select class="fb" id="prodFilt" onchange="drillPred=null;filt()"><option value="">All Products</option>{prod_options}</select>
<span style="color:var(--bd)">|</span>
<label style="display:flex;align-items:center;gap:4px;font-size:.75rem;cursor:pointer;color:var(--tm)">
<input type="checkbox" id="hideNew" onchange="drillPred=null;filt()" style="cursor:pointer"> Hide &lt;30 days old
<span id="cutoffDate" style="font-size:.65rem;color:var(--bd)"></span>
</label>
<label style="display:flex;align-items:center;gap:4px;font-size:.75rem;cursor:pointer;color:var(--tm)">
<input type="checkbox" id="hideGhsa" onchange="drillPred=null;filt()" style="cursor:pointer"> Hide GHSA
</label>
<label style="display:flex;align-items:center;gap:4px;font-size:.75rem;cursor:pointer;color:var(--tm)">
<input type="checkbox" id="hideProc" onchange="drillPred=null;filt()" checked style="cursor:pointer"> Hide Processed
</label>
<label style="display:flex;align-items:center;gap:4px;font-size:.75rem;cursor:pointer;color:var(--tm)">
<input type="checkbox" id="hideFP" onchange="drillPred=null;filt()" checked style="cursor:pointer"> Hide False Positives
</label>
</div>
<div class="cnt" id="rowCount"></div>
<div class="tw" id="tableWrap"><table><thead><tr>
<th style="width:28px">Processed</th><th style="width:28px">FP</th><th onclick="srt(0)">Priority</th><th onclick="srt(1)">Action</th><th
onclick="srt(2)">CVE</th>
<th onclick="srt(3)">Sev</th><th onclick="srt(29)">RH CVSS</th><th onclick="srt(4)">CVSS</th><th onclick="srt(6)">EPSS</th>
<th onclick="srt(7)">Product</th><th onclick="srt(8)">Image</th>
<th onclick="srt(13)">Component</th><th onclick="srt(15)">Fixed In</th>
<th onclick="srt(32)">Fix Status</th><th onclick="srt(21)">OSV</th><th onclick="srt(16)">RHSA</th>
</tr></thead><tbody id="tbody"></tbody></table></div>
<div class="dp" id="dp"></div>
</div>

<div class="tc" id="tc-proc">
<div class="cnt" id="procInfo">0 processed records</div>
<div class="tw"><table><thead><tr>
<th style="width:28px">Processed</th><th>Priority</th><th>Action</th><th>CVE</th><th>Sev</th><th>RH CVSS</th>
<th>Product</th><th>Image</th><th>Component</th><th>Fix Status</th>
</tr></thead><tbody id="procBody"></tbody></table></div>
</div>

<div class="tc" id="tc-fp">
<div class="cnt" id="fpInfo">0 potential false positives</div>
<div class="tw"><table><thead><tr>
<th style="width:28px">FP</th><th>Priority</th><th>Action</th><th>CVE</th><th>Sev</th><th>RH CVSS</th>
<th>Product</th><th>Image</th><th>Component</th><th>Fix Status</th>
</tr></thead><tbody id="fpBody"></tbody></table></div>
</div>

<script>
const D={data_json};
const PO={{'P1-CRITICAL':0,'P1-HIGH-EPSS':1,'P2-HIGH-IMPACT':2,'P2-HIGH-EPSS':3,'P3-MODERATE':4,'P4-MONITOR':5,'P5-LOW':6}};
const PC={{'P1-CRITICAL':'#dc2626','P1-HIGH-EPSS':'#dc2626','P2-HIGH-IMPACT':'#ea580c','P2-HIGH-EPSS':'#ea580c','P3-MODERATE':'#d97706','P4-MONITOR':'#2563eb','
P5-LOW':'#6b7280'}};
const AC={{'PATCH':'#dc2626','MONITOR':'#2563eb'}};
const SC={{'CRITICAL':'#7f1d1d','IMPORTANT':'#92400e'}};
const RC={{'CONFIRMED':'#16a34a','NOT_FOUND':'#d97706','SCAN_ERROR':'#dc2626'}};

// Add index to each record for O(1) lookup
D.forEach((r,i)=>r.push(i)); // index at position 41

const REPORT_ID='{REPORT_ID}';
let PS=new Set(JSON.parse(localStorage.getItem('cve_proc_'+REPORT_ID)||'[]'));
function savePS(){{
  const arr=[...PS];
  localStorage.setItem('cve_proc_'+REPORT_ID,JSON.stringify(arr));
  fetch('/api/reports/'+REPORT_ID+'/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(arr)}}).catch(()=>{{}});
}}
fetch('/api/reports/'+REPORT_ID+'/state').then(r=>r.json()).then(arr=>{{
  if(Array.isArray(arr)&&arr.length){{PS=new Set(arr);localStorage.setItem('cve_proc_'+REPORT_ID,JSON.stringify(arr));updPC();
  if(document.getElementById('tc-data').classList.contains('on'))filt();}}
}}).catch(()=>{{}});
function pk(r){{return r[2]+'|||'+r[9]}}
function isProc(r){{return PS.has(pk(r))}}
function toggleProc(idx,ev){{
  if(ev)ev.stopPropagation();
  const r=D[idx];const k=pk(r);
  if(PS.has(k))PS.delete(k);else PS.add(k);
  savePS();filt();renderProc();
}}
function cveLink(r){{return r[18]?'<a href="'+h(r[18])+'" target="_blank" onclick="event.stopPropagation()">'+h(r[2])+'</a>':h(r[2])}}

let FP=new Set(JSON.parse(localStorage.getItem('cve_fp_'+REPORT_ID)||'[]'));
function saveFP(){{
  const arr=[...FP];
  localStorage.setItem('cve_fp_'+REPORT_ID,JSON.stringify(arr));
  fetch('/api/reports/'+REPORT_ID+'/fp_state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(arr)}}).catch(()=>{{}});
}}
fetch('/api/reports/'+REPORT_ID+'/fp_state').then(r=>r.json()).then(arr=>{{
  if(Array.isArray(arr)&&arr.length){{FP=new Set(arr);localStorage.setItem('cve_fp_'+REPORT_ID,JSON.stringify(arr));updFPC();
  if(document.getElementById('tc-data').classList.contains('on'))filt();}}
}}).catch(()=>{{}});
function isFP(r){{return FP.has(pk(r))}}
function toggleFP(idx,ev){{
  if(ev)ev.stopPropagation();
  const r=D[idx];const k=pk(r);
  if(FP.has(k))FP.delete(k);else FP.add(k);
  saveFP();filt();renderFP();
}}
function fpCell(r){{
  const idx=r[41];
  if(isFP(r))return'<td><span class="fpflag" onclick="toggleFP('+idx+',event)" title="Remove false positive flag">&#x1F6A9;</span></td>';
  return'<td><button class="fpbtn" onclick="toggleFP('+idx+',event)" title="Flag as false positive">FP</button></td>';
}}

// Parse "Month Day, Year" dates once and cache as timestamps
const MONTHS={{January:0,February:1,March:2,April:3,May:4,June:5,July:6,August:7,September:8,October:9,November:10,December:11}};
function parseDisc(s){{
  if(!s)return 0;
  const m=s.match(/^(\\w+)\\s+(\\d+),?\\s+(\\d{{4}})$/);
  if(!m)return 0;
  const mon=MONTHS[m[1]];
  if(mon===undefined)return 0;
  return new Date(parseInt(m[3]),mon,parseInt(m[2])).getTime();
}}
const discCache=D.map(r=>parseDisc(r[24]));

// Show cutoff date on load
(function(){{
  const cut=new Date();cut.setDate(cut.getDate()-30);
  const el=document.getElementById('cutoffDate');
  if(el)el.textContent='(before '+cut.toLocaleDateString('en-US',{{month:'short',day:'numeric',year:'numeric'}})+')';
}})();

let cf='all',sortCol=0,sortAsc=true,filtered=D.slice(),drillPred=null;

function stab(el,id){{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('on'));
  el.classList.add('on');
  document.getElementById('tc-'+id).classList.add('on');
  if(id==='data'&&!document.getElementById('tbody').children.length)filt();
  if(id==='proc')renderProc();
  if(id==='fp')renderFP();
}}

function drill(type,val){{
  const tabs=document.querySelectorAll('.tab');
  stab(tabs[1],'data');
  document.getElementById('hideProc').checked=false;
  document.getElementById('hideFP').checked=false;
  document.getElementById('hideNew').checked=false;
  document.getElementById('hideGhsa').checked=false;
  document.getElementById('q').value='';
  document.getElementById('prodFilt').value='';
  const btns=document.querySelectorAll('.bar .fb:not(select)');
  btns.forEach(b=>b.classList.remove('on'));
  drillPred=null;cf='all';
  if(type==='action'){{cf=val;btns.forEach(b=>{{if(b.textContent.trim()===val)b.classList.add('on')}})}}
  else if(type==='priority'){{cf=val;btns.forEach(b=>{{const t=b.textContent.trim();if(val.startsWith(t)&&t.length>1)b.classList.add('on')}})}}
  else if(type==='product'){{document.getElementById('prodFilt').value=val;btns[0].classList.add('on')}}
  else if(type==='cve'){{document.getElementById('q').value=val;btns[0].classList.add('on')}}
  else if(type==='kev'){{drillPred=r=>!!r[39];btns[0].classList.add('on')}}
  else if(type==='remediation'){{drillPred=r=>(r[19]||'Unknown')===val;btns[0].classList.add('on')}}
  else if(type==='fix'){{drillPred=r=>r[32]===val;btns[0].classList.add('on')}}
  else{{btns[0].classList.add('on')}}
  filt();
}}

function sf(btn,f){{
  drillPred=null;
  const btns=btn.parentElement.querySelectorAll('.fb:not(select)');
  btns.forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  cf=f;filt();
}}

function filt(){{
  const q=document.getElementById('q').value.toLowerCase();
  const prod=document.getElementById('prodFilt').value;
  const hideNew=document.getElementById('hideNew').checked;
  const hideGhsa=document.getElementById('hideGhsa').checked;
  const hideProc=document.getElementById('hideProc').checked;
  const hideFP=document.getElementById('hideFP').checked;
  let cutoff=0;
  if(hideNew){{
    const d=new Date();d.setDate(d.getDate()-30);
    cutoff=d.getTime();
  }}
  filtered=D.filter(r=>{{
    if(cf==='PATCH'&&r[1]!=='PATCH')return false;
    if(cf==='MONITOR'&&r[1]!=='MONITOR')return false;
    if(cf!=='all'&&cf!=='PATCH'&&cf!=='MONITOR'&&!r[0].startsWith(cf))return false;
    if(prod&&r[7]!==prod)return false;
    if(hideGhsa&&r[2].startsWith('GHSA-'))return false;
    if(hideProc&&isProc(r))return false;
    if(hideFP&&isFP(r))return false;
    if(drillPred&&!drillPred(r))return false;
    if(hideNew&&!r[39]){{
      const ts=discCache[r[41]];
      if(ts&&ts>cutoff)return false;
    }}
    if(q){{
      const s=r.slice(0,41).join(' ').toLowerCase();
      if(!s.includes(q))return false;
    }}
    return true;
  }});
  doSort();
  loaded=0;
  render();
}}

function srt(col){{
  if(sortCol===col)sortAsc=!sortAsc;
  else{{sortCol=col;sortAsc=true;}}
  doSort();loaded=0;render();
}}

function doSort(){{
  filtered.sort((a,b)=>{{
    let va=a[sortCol],vb=b[sortCol];
    if(sortCol===0){{va=PO[va]??99;vb=PO[vb]??99;}}
    else if(sortCol===4||sortCol===6||sortCol===29){{va=parseFloat(va)||0;vb=parseFloat(vb)||0;}}
    else if(sortCol===32){{const fo={{'FIXED_IN_LATEST':0,'STILL_VULNERABLE':1,'SCAN_UNAVAILABLE':2,'UNKNOWN':3,'':4}};va=fo[va]??4;vb=fo[vb]??4;}}
    if(va<vb)return sortAsc?-1:1;
    if(va>vb)return sortAsc?1:-1;
    return 0;
  }});
}}

function render(){{
  const tb=document.getElementById('tbody');
  const rows=[];
  const n=Math.min(filtered.length,500);
  for(let i=0;i<n;i++){{
    const r=filtered[i];
    const ep=parseFloat(r[6])||0;
    const ec=ep>=10?'#ef4444':ep>=1?'#f97316':ep>0?'#22c55e':'#6b7280';
    const ew=Math.min(100,ep<10?ep*10:50+ep);
    const cveL=cveLink(r);const ip=isProc(r);const ifp=isFP(r);const ik=!!r[39];
    const rhsaL=r[16]&&r[17]?'<a href="'+h(r[17])+'" target="_blank" onclick="event.stopPropagation()">'+h(r[16])+'</a>':(r[16]?h(r[16]):'<span
    class="tm">—</span>');
    const osvT=r[21]||'';
    const osvC=osvT.startsWith('Confirmed')?'#16a34a':(osvT.includes('RPM')||osvT.includes('RHSA')||osvT.includes('Container'))?'#0891b2':'#6b7280';
    const idx=r[41];
    const rowCls='dr'+(ip?' prow':'')+(ifp?' fprow':'')+(ik?' kevrow':'');
    rows.push('<tr class="'+rowCls+'" onclick="det('+idx+')" data-i="'+idx+'">'
      +'<td><input type="checkbox" class="pcb"'+(ip?' checked':'')+' onclick="toggleProc('+idx+',event)"></td>'
      +fpCell(r)
      +'<td><span class="b" style="background:'+(PC[r[0]]||'#6b7280')+'">'+h(r[0])+'</span></td>'
      +'<td><span class="b" style="background:'+(AC[r[1]]||'#6b7280')+'">'+h(r[1])+'</span></td>'
      +'<td>'+cveL+(ik?'<span class="kev">KEV</span>':'')+'</td>'
      +'<td><span class="b" style="background:'+(SC[r[3]]||'#6b7280')+'">'+h(r[3])+'</span></td>'
      +'<td>'+rhCvss(r)+'</td>'
      +'<td style="font-size:.72rem;color:var(--tm)">'+h(r[4])+'</td>'
      +'<td><span class="eb"><span class="ef" style="width:'+ew+'%;background:'+ec+'"></span></span> '+ep.toFixed(2)+'%</td>'
      +'<td style="font-size:.7rem">'+h(r[7])+'</td>'
      +'<td style="font-size:.7rem" title="'+h(r[9])+'">'+h(r[8])+'</td>'
      +'<td style="font-size:.7rem">'+h(r[13])+'<br><span class="tm">'+h(r[14])+'</span></td>'
      +'<td style="font-size:.7rem">'+(r[15]?h(r[15]):'<span class="tm">—</span>')+'</td>'
      +'<td>'+fixBadge(r)+'</td>'
      +'<td><span class="b" style="background:'+osvC+'">'+h(osvT).substring(0,20)+'</span></td>'
      +'<td style="font-size:.7rem">'+rhsaL+'</td>'
      +'</tr>');
  }}
  tb.innerHTML=rows.join('');
  document.getElementById('rowCount').textContent='Showing '+n+' of '+filtered.length+' records'+(filtered.length>500?' (scroll to load more)':'');
  if(filtered.length>500){{
    const tw=document.getElementById('tableWrap');
    tw.onscroll=function(){{
      if(tw.scrollTop+tw.clientHeight>=tw.scrollHeight-100)loadMore();
    }};
  }}
}}

let loaded=500;
function loadMore(){{
  if(loaded>=filtered.length)return;
  const tb=document.getElementById('tbody');
  const end=Math.min(loaded+200,filtered.length);
  const frag=document.createDocumentFragment();
  for(let i=loaded;i<end;i++){{
    const r=filtered[i];
    const ep=parseFloat(r[6])||0;
    const ec=ep>=10?'#ef4444':ep>=1?'#f97316':ep>0?'#22c55e':'#6b7280';
    const ew=Math.min(100,ep<10?ep*10:50+ep);
    const cveL=cveLink(r);const ip=isProc(r);const ifp=isFP(r);const ik=!!r[39];
    const rhsaL=r[16]&&r[17]?'<a href="'+h(r[17])+'" target="_blank" onclick="event.stopPropagation()">'+h(r[16])+'</a>':(r[16]?h(r[16]):'<span
    class="tm">—</span>');
    const osvT=r[21]||'';
    const osvC=osvT.startsWith('Confirmed')?'#16a34a':(osvT.includes('RPM')||osvT.includes('RHSA')||osvT.includes('Container'))?'#0891b2':'#6b7280';
    const idx=r[41];
    const tr=document.createElement('tr');
    tr.className='dr'+(ip?' prow':'')+(ifp?' fprow':'')+(ik?' kevrow':'');tr.setAttribute('onclick','det('+idx+')');tr.setAttribute('data-i',idx);
    tr.innerHTML='<td><input type="checkbox" class="pcb"'+(ip?' checked':'')+' onclick="toggleProc('+idx+',event)"></td>'
      +fpCell(r)
      +'<td><span class="b" style="background:'+(PC[r[0]]||'#6b7280')+'">'+h(r[0])+'</span></td>'
      +'<td><span class="b" style="background:'+(AC[r[1]]||'#6b7280')+'">'+h(r[1])+'</span></td>'
      +'<td>'+cveL+(ik?'<span class="kev">KEV</span>':'')+'</td>'
      +'<td><span class="b" style="background:'+(SC[r[3]]||'#6b7280')+'">'+h(r[3])+'</span></td>'
      +'<td>'+rhCvss(r)+'</td>'
      +'<td style="font-size:.72rem;color:var(--tm)">'+h(r[4])+'</td>'
      +'<td><span class="eb"><span class="ef" style="width:'+ew+'%;background:'+ec+'"></span></span> '+ep.toFixed(2)+'%</td>'
      +'<td style="font-size:.7rem">'+h(r[7])+'</td>'
      +'<td style="font-size:.7rem" title="'+h(r[9])+'">'+h(r[8])+'</td>'
      +'<td style="font-size:.7rem">'+h(r[13])+'<br><span class="tm">'+h(r[14])+'</span></td>'
      +'<td style="font-size:.7rem">'+(r[15]?h(r[15]):'<span class="tm">—</span>')+'</td>'
      +'<td>'+fixBadge(r)+'</td>'
      +'<td><span class="b" style="background:'+osvC+'">'+h(osvT).substring(0,20)+'</span></td>'
      +'<td style="font-size:.7rem">'+rhsaL+'</td>';
    frag.appendChild(tr);
  }}
  tb.appendChild(frag);
  loaded=end;
  document.getElementById('rowCount').textContent='Showing '+loaded+' of '+filtered.length+' records';
}}

function det(idx){{
  const r=D[idx];if(!r)return;
  document.querySelectorAll('.dr').forEach(t=>t.classList.remove('sel'));
  const row=document.querySelector('tr[data-i="'+idx+'"]');
  if(row)row.classList.add('sel');
  const dp=document.getElementById('dp');
  let o='<span class="x" onclick="this.parentElement.classList.remove(&#39;on&#39;)">&times;</span>';
  o+='<div style="display:flex;gap:6px;align-items:center;margin-bottom:8px;flex-wrap:wrap">';
  o+='<span class="b" style="background:'+(PC[r[0]]||'#6b7280')+'">'+h(r[0])+'</span>';
  o+='<span class="b" style="background:'+(AC[r[1]]||'#6b7280')+'">'+h(r[1])+'</span>';
  o+='<strong>'+h(r[2])+'</strong>';
  o+='<span>RH CVSS: '+rhCvss(r)+'</span>';
  o+='<span class="tm">Scanner CVSS: '+h(r[4])+(r[5]&&r[5]!=='0'?' (NVD:'+h(r[5])+')':'')+'</span>';
  o+='<span class="tm">EPSS: '+h(r[6])+'%</span>';
  o+='<button class="pbtn" onclick="toggleFP('+idx+',event)" style="margin-left:auto">'+(isFP(r)?'&#x1F6A9; Remove False Positive':'Flag False
  Positive')+'</button>';
  o+='<button class="pbtn" onclick="toggleProc('+idx+',event)">'+(isProc(r)?'Unmark Processed':'Mark Processed')+'</button>';
  o+='</div>';
  if(r[31])o+='<div style="font-size:.72rem;color:var(--tm);margin-bottom:8px">RH Vector: '+h(r[31])+'</div>';
  o+='<div class="dg">';
  o+=di('Product',r[7]);o+=di('Image',r[8]);
  o+=di('Full Image','<span style="font-size:.68rem;word-break:break-all">'+h(r[9])+'</span>');
  o+=di('Cluster / NS',h(r[10])+' / '+h(r[11]));
  o+=di('Deployments',r[12]);o+=di('Component',h(r[13])+' '+h(r[14]));
  o+=di('Fixed In',r[15]||'—');o+=di('Discovered',r[24]);
  o+='</div>';
  o+=di('Triage Reasoning',r[20]);
  if(r[19])o+='<div class="bx bxr"><div class="bl2">Remediation Path</div>'+h(r[19])+'</div>';
  if(r[16]){{o+='<div class="bx bxa"><div class="bl2">Red Hat Advisory</div>';
    o+=(r[17]?'<a href="'+h(r[17])+'" target="_blank">'+h(r[16])+'</a>':h(r[16]))+' — '+h(r[13])+' fix';
    if(r[36])o+='<div style="margin-top:6px;font-size:.72rem;color:var(--tm);white-space:pre-wrap">'+h(r[36])+'</div>';
    o+='</div>';}}
  o+='<div class="bx bxg"><div class="bl2">roxctl Scan Verification</div>';
  o+='Current image: <span class="b" style="background:'+(RC[r[25]]||'#6b7280')+'">'+h(r[25])+'</span>';
  if(r[26])o+=' &bull; Fix available: <strong>'+h(r[26])+'</strong>';
  // Latest image fix check
  const fs=r[32],fref=r[33],ftag=r[34],fcat=r[35];
  if(fs){{
    const fsc={{'FIXED_IN_LATEST':'#16a34a','STILL_VULNERABLE':'#dc2626','SCAN_UNAVAILABLE':'#6b7280','UNKNOWN':'#6b7280'}};
    const fsl={{'FIXED_IN_LATEST':'FIXED in latest','STILL_VULNERABLE':'Still vulnerable in latest','SCAN_UNAVAILABLE':'Latest scan
    unavailable','UNKNOWN':'Unknown'}};
    o+='<div style="margin-top:6px;padding-top:6px;border-top:1px solid var(--bd)">';
    o+='Latest image: <span class="b" style="background:'+(fsc[fs]||'#6b7280')+'">'+(fsl[fs]||fs)+'</span>';
    if(ftag)o+=' <span class="tm">('+h(ftag)+')</span>';
    if(fref){{
      o+='<div style="margin-top:3px;font-size:.7rem;word-break:break-all">';
      if(fref.includes('quay.io/')&&fref.includes('@sha256:')){{const fp=fref.split('@');const rp=fp[0].replace('quay.io/','');o+='<a href="https://quay.io/repo
      sitory/'+h(rp)+'/manifest/'+h(fp[1])+'" target="_blank">'+h(fref)+'</a>';}}
      else if(fref.includes('quay.io/')){{const rp=fref.replace('quay.io/','').split(':')[0];o+='<a href="https://quay.io/repository/'+h(rp)+'"
      target="_blank">'+h(fref)+'</a>';}}
      else if(fcat)o+='<a href="'+h(fcat)+'" target="_blank">'+h(fref)+'</a>';
      else o+=h(fref);
      o+='</div>';
    }}
    o+='</div>';
  }}
  o+='</div>';
  if(r[21]){{const oc=r[21].startsWith('Confirmed')?'#16a34a':'#0891b2';
    o+='<div class="bx" style="background:#111827;border:1px solid '+oc+'40"><div class="bl2" style="color:'+oc+'">OSV Verification</div>';
    o+='<span class="b" style="background:'+oc+'">'+h(r[21])+'</span>';
    if(r[22])o+='<div style="margin-top:3px;font-size:.72rem" class="tm">Range: '+h(r[22])+'</div>';
    o+='</div>';}}
  if(r[39]){{o+='<div class="bx" style="background:#1a1708;border:1px solid #f59e0b"><div class="bl2" style="color:#f59e0b">&#9888; CISA Known Exploited
  Vulnerability</div>';
    o+='<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:4px"><div><span class="dl">Date Added</span> '+h(r[39])+'</div><div><span class="dl">Due
    Date</span> <strong style="color:#f59e0b">'+h(r[40])+'</strong></div></div>';
    o+='<div style="font-size:.72rem;color:var(--tm)">Active exploitation confirmed. Mandatory remediation deadline per <a href="https://www.cisa.gov/known-expl
    oited-vulnerabilities-catalog" target="_blank">CISA BOD 22-01</a>.</div></div>';}}
  if(r[37])o+='<div class="bx bxr"><div class="bl2">Red Hat CVE Mitigation</div>'+h(r[37])+'</div>';
  if(r[38])o+='<div class="bx bxr"><div class="bl2">Red Hat CVE Statement</div>'+h(r[38])+'</div>';
  if(r[23])o+='<div class="bx bxp"><div class="bl2">POA&amp;M Justification</div>'+h(r[23])+'</div>';
  // CVE reference links — detect source from URL
  function lnk(u){{if(u.includes('access.redhat.com'))return'Red Hat CVE';if(u.includes('nvd.nist.gov'))return'NVD';if(u.includes('osv.dev'))return'OSV';
  if(u.includes('github.com'))return'GitHub Advisory';return'Link'}}
  let links='<div style="margin-top:6px;font-size:.78rem;display:flex;gap:12px;flex-wrap:wrap">';
  if(r[18])links+='<a href="'+h(r[18])+'" target="_blank">'+lnk(r[18])+' &rarr;</a>';
  if(r[27])links+='<a href="'+h(r[27])+'" target="_blank">'+lnk(r[27])+' &rarr;</a>';
  if(r[28])links+='<a href="'+h(r[28])+'" target="_blank">'+lnk(r[28])+' &rarr;</a>';
  links+='</div>';
  o+=links;
  dp.innerHTML=o;dp.classList.add('on');
  dp.scrollIntoView({{behavior:'smooth',block:'nearest'}});
}}

function h(s){{return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}}
function fixBadge(r){{
  const fs=r[32];
  if(fs==='FIXED_IN_LATEST'){{
    const cat=r[35];const ref=r[33];
    let o='<span class="b" style="background:#16a34a">FIXED</span>';
    if(cat)o='<a href="'+h(cat)+'" target="_blank" onclick="event.stopPropagation()" title="'+h(ref)+'">'+o+'</a>';
    return o;
  }}
  if(fs==='STILL_VULNERABLE')return'<span class="b" style="background:#dc2626">NOT FIXED</span>';
  if(fs==='SCAN_UNAVAILABLE')return'<span class="b" style="background:#6b7280">N/A</span>';
  return'<span class="b" style="background:#6b7280">—</span>';
}}
function rhCvss(r){{
  const s=parseFloat(r[29])||0;
  if(s===0)return'<span class="tm">—</span>';
  const c=s>=9?'#dc2626':s>=7?'#f97316':s>=4?'#eab308':'#22c55e';
  const sev=r[30]||'';
  const sevC={{'Critical':'#dc2626','Important':'#ea580c','Moderate':'#d97706','Low':'#22c55e'}};
  let o='<span style="color:'+c+';font-weight:600">'+s.toFixed(1)+'</span>';
  if(sev)o+=' <span class="b" style="background:'+(sevC[sev]||'#6b7280')+';font-size:.58rem">'+h(sev)+'</span>';
  return o;
}}
function di(l,v){{return'<div><div class="dl">'+h(l)+'</div><div class="dv">'+(v||'—')+'</div></div>'}}
function renderProc(){{
  const pb=document.getElementById('procBody');
  if(!pb)return;
  const proc=D.filter(r=>isProc(r));
  const rows=[];
  for(const r of proc){{
    const idx=r[41];
    rows.push('<tr class="dr" onclick="det('+idx+')" data-i="'+idx+'">'
      +'<td><input type="checkbox" class="pcb" checked onclick="toggleProc('+idx+',event)"></td>'
      +'<td><span class="b" style="background:'+(PC[r[0]]||'#6b7280')+'">'+h(r[0])+'</span></td>'
      +'<td><span class="b" style="background:'+(AC[r[1]]||'#6b7280')+'">'+h(r[1])+'</span></td>'
      +'<td>'+cveLink(r)+'</td>'
      +'<td><span class="b" style="background:'+(SC[r[3]]||'#6b7280')+'">'+h(r[3])+'</span></td>'
      +'<td>'+rhCvss(r)+'</td>'
      +'<td style="font-size:.7rem">'+h(r[7])+'</td>'
      +'<td style="font-size:.7rem" title="'+h(r[9])+'">'+h(r[8])+'</td>'
      +'<td style="font-size:.7rem">'+h(r[13])+'</td>'
      +'<td>'+fixBadge(r)+'</td>'
      +'</tr>');
  }}
  pb.innerHTML=rows.join('');
  document.getElementById('procInfo').textContent=proc.length+' processed records';
  updPC();
}}
function updPC(){{
  const el=document.getElementById('procCnt');
  if(el)el.textContent=PS.size;
}}
function renderFP(){{
  const fb=document.getElementById('fpBody');
  if(!fb)return;
  const fps=D.filter(r=>isFP(r));
  const rows=[];
  for(const r of fps){{
    const idx=r[41];
    rows.push('<tr class="dr" onclick="det('+idx+')" data-i="'+idx+'">'
      +'<td><span class="fpflag" onclick="toggleFP('+idx+',event)" title="Remove false positive flag">&#x1F6A9;</span></td>'
      +'<td><span class="b" style="background:'+(PC[r[0]]||'#6b7280')+'">'+h(r[0])+'</span></td>'
      +'<td><span class="b" style="background:'+(AC[r[1]]||'#6b7280')+'">'+h(r[1])+'</span></td>'
      +'<td>'+cveLink(r)+'</td>'
      +'<td><span class="b" style="background:'+(SC[r[3]]||'#6b7280')+'">'+h(r[3])+'</span></td>'
      +'<td>'+rhCvss(r)+'</td>'
      +'<td style="font-size:.7rem">'+h(r[7])+'</td>'
      +'<td style="font-size:.7rem" title="'+h(r[9])+'">'+h(r[8])+'</td>'
      +'<td style="font-size:.7rem">'+h(r[13])+'</td>'
      +'<td>'+fixBadge(r)+'</td>'
      +'</tr>');
  }}
  fb.innerHTML=rows.join('');
  document.getElementById('fpInfo').textContent=fps.length+' potential false positive'+(fps.length!==1?'s':'');
  updFPC();
}}
function updFPC(){{
  const el=document.getElementById('fpCnt');
  if(el)el.textContent=FP.size;
}}
updPC();updFPC();
</script></body></html>"""

with open(OUTPUT, 'w') as f:
    f.write(html)
print(f"Report: {OUTPUT}")
print(f"Size: {os.path.getsize(OUTPUT) / 1024 / 1024:.1f} MB")

FIELD_NAMES = [
    'priority', 'action', 'cve', 'severity', 'cvss', 'nvd_cvss', 'epss_pct',
    'product', 'image_short', 'image_full', 'cluster', 'namespaces', 'deployments',
    'component', 'component_version', 'fixed_in', 'rhsa_advisory', 'advisory_link',
    'primary_link', 'remediation_path', 'triage_reasoning', 'osv_verification',
    'osv_affected_range', 'poam_justification', 'discovered', 'rox_status',
    'rox_fix_version', 'secondary_link', 'tertiary_link', 'rh_cvss', 'rh_severity',
    'rh_vector', 'fix_status', 'fix_latest_ref', 'fix_latest_tag', 'fix_catalog_url',
    'rhsa_description', 'rh_mitigation', 'rh_statement',
    'kev_date_added', 'kev_due_date',
]
data_rows = []
for r in R:
    row = {}
    for i, name in enumerate(FIELD_NAMES):
        row[name] = r[i] if i < len(r) else ''
    row['key'] = r[2] + '|||' + r[9]
    data_rows.append(row)
with open(DATA_JSON_OUTPUT, 'w') as f:
    json.dump(data_rows, f, separators=(',', ':'))
print(f"Data JSON: {DATA_JSON_OUTPUT} ({os.path.getsize(DATA_JSON_OUTPUT) / 1024:.0f} KB)")
