---
name: mitre_cybersecurity
description: Perform security auditing, vulnerability scanning, CVE analysis, and mapping against the MITRE ATT&CK framework.
category: Specialist
autonomy_required: LEVEL_2
parameters: scan_target:string:Target IP, domain, codebase path, or system to audit, audit_type:string:Audit type (code_scan, cve_lookup, mitre_mapping, config_audit), severity_threshold:string:Minimum severity to report (LOW, MEDIUM, HIGH, CRITICAL)
tags: [security, cyber, mitre, att&ck, audit, cve, scanning, vulnerabilities]
---

# MITRE Cybersecurity & Vulnerability Auditing

This skill conducts automated cybersecurity audits, code vulnerability scans, CVE lookups, and threat mapping against the MITRE ATT&CK enterprise framework.

## Audit Capabilities

1. **Static Code Analysis (`code_scan`)**:
   - Inspect source files in `{scan_target}` for common vulnerabilities (SQLi, XSS, hardcoded secrets, insecure deserialization, buffer overflows).
   - Maps discovered flaws to CWE and MITRE ATT&CK techniques.

2. **CVE & Exploit Lookup (`cve_lookup`)**:
   - Query national vulnerability databases and NVD feeds for known CVE IDs or software version strings.
   - Summarize CVSS scores, attack vectors, and patching remediation steps.

3. **MITRE ATT&CK Mapping (`mitre_mapping`)**:
   - Map observed behaviors, system logs, or architecture designs to specific Tactics (e.g., Persistence TA0003, Lateral Movement TA0008) and Techniques (e.g., T1059 Command and Scripting Interpreter).

4. **Configuration Audit (`config_audit`)**:
   - Evaluate server, cloud, or container configurations against CIS benchmarks and least-privilege security principles.

## Security & Guardrails
- **Level 2 Autonomy**: Active network scanning or penetration testing techniques require explicit user authorization before execution.
- **Defensive Focus**: All findings are structured to prioritize remediation, hardening, and defensive posture enhancement.

## Output Format
Return an executive security report in markdown containing:
- **Audit Summary Table** (Severity breakdown: Critical, High, Medium, Low)
- **Detailed Findings**:
  - Finding Title & Severity Badge
  - MITRE ATT&CK Tactic/Technique ID
  - Affected Component / Line Number
  - Root Cause Analysis & Actionable Remediation
