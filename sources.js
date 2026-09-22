// Entirely fictional source records. Publishers, reports, findings, and scores
// are invented for the prototype and make no claims about the actual vendors.
const riskDimensions = [
  {key:'cyber',label:'Cyber',icon:'lock',publisher:'Northstar Cyber Research',prefix:'NCR'},
  {key:'reputation',label:'Reputation',icon:'globe',publisher:'Meridian Reputation Monitor',prefix:'MRM'},
  {key:'fraud',label:'Fraud',icon:'shield-alert',publisher:'ClearLedger Assurance',prefix:'CLA'},
];
// Each source: illustrative subscore, report title, specific finding/excerpt.
const vendorEvidence = {
  aws: [
    [21,'AWS cloud control assessment — September 2026','The fictional review sampled 120 privileged accounts. MFA coverage reached 99%; two dormant service accounts remain scheduled for removal.'],
    [28,'AWS enterprise customer sentiment digest','The demo sample contains 240 customer mentions, of which 18 concern billing transparency. No material escalation appears in the simulated review.'],
    [14,'AWS billing and beneficiary verification','All 60 sampled invoices matched approved contracts. One beneficiary-change request was held for independent callback and resolved without payment.'],
  ],
  microsoft: [
    [23,'Microsoft identity assurance review — Q3 2026','The fictional assessment reviewed 85 privileged identities. Two legacy application permissions require removal; all administrator accounts passed MFA checks.'],
    [18,'Microsoft enterprise trust bulletin','Of 310 simulated customer mentions, 12 raise support-response concerns. All five escalated support cases in the demo dataset closed within the review window.'],
    [12,'Microsoft reseller invoice validation','A fictional sample of 75 reseller invoices contained no duplicate payments. Three bank-detail changes were independently verified before approval.'],
  ],
  nvidia: [
    [26,'NVIDIA accelerator firmware assurance note','In a fictional sample of 40 compute nodes, 38 used the approved firmware baseline. Two remaining nodes have scheduled maintenance windows.'],
    [74,'NVIDIA allocation and export-control sentiment review','The simulated digest identifies 46 critical mentions across 180 articles about delivery allocation and export restrictions. Seven enterprise customers request written delivery commitments.'],
    [58,'NVIDIA distribution-channel integrity assessment','The fictional review flags four of 25 intermediary quotes for incomplete ownership evidence. Payments to those intermediaries remain blocked pending verification.'],
  ],
  tsmc: [
    [34,'TSMC supplier portal security assessment','A fictional sample of 52 supplier accounts identified three overdue access recertifications. No unauthorized access was observed within this demo scenario.'],
    [81,'TSMC supply-chain confidence briefing','The simulated report records 62 negative mentions in 200 articles following a fictional shipping delay. Nine downstream customers request revised delivery assurances.'],
    [65,'TSMC intermediary payment-control review','Five of 30 fictional broker records lack complete beneficial-ownership documentation. Two invoice amendments remain on hold for secondary approval.'],
  ],
  sap: [
    [22,'SAP application security control review','The fictional review found 97% patch compliance across 64 application instances. Two non-production instances await the next patch window.'],
    [19,'SAP implementation and service sentiment digest','The demo review classifies 11 of 160 customer mentions as negative, primarily concerning migration timelines. No critical escalation is open in the sample.'],
    [16,'SAP software licensing reconciliation','All 48 fictional license invoices reconciled to approved purchase orders. One duplicate invoice was detected and rejected before payment.'],
  ],
  bloomberg: [
    [15,'Bloomberg terminal access assurance report','All 90 fictional terminal accounts passed access recertification. Session logging was complete in the sampled trading and risk-reporting environments.'],
    [17,'Bloomberg market-data confidence bulletin','The fictional sample includes 130 customer mentions and six minor complaints about data latency. The demo escalation register contains no unresolved priority cases.'],
    [11,'Bloomberg subscription billing verification','A fictional sample of 54 subscription invoices matched active entitlements. No duplicate billing or unverified beneficiary changes were identified.'],
  ],
  visa: [
    [13,'Visa payment interface security review','All 36 fictional payment interfaces passed certificate and encryption checks. One low-priority logging improvement was recorded for the next release.'],
    [14,'Visa payment service confidence digest','The simulated dataset contains 220 service mentions with eight low-severity complaints. All sampled incident communications met the agreed response window.'],
    [10,'Visa transaction exception control test','The fictional control test screened 10,000 synthetic transactions. All 24 seeded suspicious transactions entered the investigation queue; no test payment escaped review.'],
  ],
  infosys: [
    [37,'Infosys managed-service access review','The fictional review identified eight overdue access recertifications among 140 support accounts. Privileged sessions remained logged throughout the sample period.'],
    [49,'Infosys delivery transition sentiment briefing','In the simulated sample, 29 of 170 customer mentions concern staffing continuity. Four project milestones require revised delivery dates.'],
    [35,'Infosys subcontractor billing assessment','Three of 42 fictional subcontractor invoices require supporting timesheets. Approval is paused for the affected items until service owners confirm delivery.'],
  ],
  oracle: [
    [58,'Oracle database patch assurance review','The fictional assessment identified 12 overdue security updates across 70 database instances. Four instances support critical applications and require expedited maintenance.'],
    [43,'Oracle licensing and support sentiment review','The demo digest identifies 32 negative mentions among 190 customer reports, concentrated on license interpretation and support turnaround.'],
    [31,'Oracle contract and invoice reconciliation','Four of 58 fictional invoices have discrepancies against approved license quantities. The exceptions are held for contract-owner reconciliation before payment.'],
  ],
  lseg: [
    [29,'LSEG data-feed access control assessment','The fictional review sampled 44 feed credentials. Two rotation deadlines remain open; no unapproved data-feed entitlement was found.'],
    [38,'LSEG data-quality confidence bulletin','The simulated dataset includes 17 negative mentions among 150 customer reports. Three pricing-feed reconciliation issues remain open after a fictional quality review.'],
    [24,'LSEG data entitlement billing review','All 39 fictional invoices matched active data subscriptions. Two unusual usage adjustments were verified against approved entitlement changes.'],
  ],
  accenture: [
    [32,'Accenture third-party access assurance','The fictional sample covers 110 consulting and support accounts. Six access reviews await service-owner sign-off; all privileged accounts have MFA enabled.'],
    [41,'Accenture program delivery sentiment digest','The demo review flags 24 of 180 customer mentions for delivery delays. Three transformation initiatives require updated resourcing commitments.'],
    [39,'Accenture subcontractor ownership review','Four of 35 fictional subcontractor records await refreshed ownership evidence. Two invoices remain blocked until the required checks are complete.'],
  ],
  swift: [
    [38,'Swift messaging control assurance report','The fictional review tested 28 messaging interfaces. Three require stronger operator-role separation; all sampled messages retained complete audit records.'],
    [57,'Swift corridor confidence and policy briefing','The simulated digest records 35 critical mentions in 160 articles about a fictional cross-border policy change. Six participating institutions seek additional implementation guidance.'],
    [72,'Swift payment instruction integrity exercise','A fictional exercise introduced 50 manipulated payment instructions. Four reached manual review later than the target window, prompting a dual-approval and alert-routing remediation plan.'],
  ],
};
