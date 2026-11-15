# Greenwheels On-Call Design

## Purpose and scope

This is a proposed, document-only operating model for a team of four engineers
supporting Greenwheels across Nairobi (UTC+3) and Pune (UTC+5:30). It does not
create a paging integration or change the current application. The repository
contains Prometheus alert rules and optional Alertmanager/Slack configuration;
Slack delivery is operational only after a real webhook is provisioned.

The schedule assumes 24/7 service responsibility. The two locations are only
2.5 hours apart, so this is not a full follow-the-sun arrangement: the
designated primary remains accountable throughout the assigned week, with a
secondary as backup. Confirm local employment rules, rest periods, holidays,
compensation, and actual service coverage expectations before adopting it.

## Team roles and rotation cadence

Assign the four engineers stable roster IDs, for example A, B, C, and D.
Publish the rota at least six weeks ahead and rotate primary duty weekly.
Assign the next engineer in the cycle as secondary:

| Week | Primary | Secondary |
|---|---|---|
| 1 | A | B |
| 2 | B | C |
| 3 | C | D |
| 4 | D | A |
| 5 | A | B |

This makes every engineer primary once every four weeks. The secondary backs
up the primary and is not expected to independently monitor dashboards.
Because a four-person team is small, this arrangement gives each person a
primary or secondary responsibility in two of each four weeks; review page
volume and fatigue monthly. If the load is not sustainable, reduce after-hours
coverage commitments, add trained responders, or use a wider shared/platform
rotation rather than silently increasing individual workload.

The default handoff is Monday at **09:00 Nairobi / 11:30 Pune**. Use one
calendar invite with both time zones shown. Keep the primary and secondary
roles fixed for the full week, including weekends, unless an explicit swap is
recorded and accepted by both engineers.

### Handoff process

The outgoing and incoming primary and secondary hold a 30-minute handoff at
the scheduled time. The outgoing primary prepares the handoff; the incoming
primary confirms ownership. Record the handoff in the team incident/on-call
channel and include:

1. Open incidents, severity, customer/business impact, incident lead, and
   next action/owner.
2. Recent deployments, rollbacks, maintenance, known risks, and temporary
   mitigations or silences (including expiry time and approver).
3. Current SLO/error-budget status and any active or recently firing alerts.
4. Dashboard, runbook, escalation-contact, and access links; confirm access
   without sharing credentials.
5. Known database, monitoring, Slack notification, or dependency issues.
6. Explicit verbal/written acceptance by the incoming primary and secondary.

If the incoming primary does not acknowledge the handoff, the outgoing primary
retains responsibility and contacts the engineering lead to arrange coverage.
Never treat a calendar change or unanswered message as a completed handoff.
After a high-severity incident, the outgoing primary gets an agreed recovery
period before returning to normal duties.

## Severity, escalation tiers, and response thresholds

An alert is actionable only if it has an owner, an impact statement, a
first-response action, and a usable runbook. Route pages to the primary; notify
the secondary on critical pages and escalate to them if the primary does not
acknowledge. Severity is based on impact, not only on a metric threshold.

| Tier | Example threshold/impact | Response and escalation |
|---|---|---|
| **SEV-1 / Critical** | API or database readiness unavailable for 5 minutes; sustained lease-event 5xx above the configured 5% threshold with meaningful traffic; confirmed payment-state/data-integrity risk; broad customer impact. | Page primary immediately. Acknowledge within 5 minutes, start incident coordination within 10 minutes, and notify secondary and engineering lead. Engage database/platform and payment/business owners as applicable. If primary does not acknowledge within 5 minutes, page secondary; if neither responds in 10 minutes, use the engineering-lead/manager escalation path. |
| **SEV-2 / High** | Sustained latency SLO breach, elevated but limited endpoint failures, significant single-customer/driver impact, or degradation likely to become SEV-1. | Notify/page primary according to the agreed alert policy. Acknowledge within 15 minutes. Involve secondary if diagnosis is not progressing after 30 minutes or the impact is expanding. Escalate to service/database owner when a dependency or specialist decision is needed. |
| **SEV-3 / Warning** | Early SLO burn, non-urgent degradation, a single non-critical component warning with no material customer impact. | Create a tracked work item or notify the owning team during working hours. Primary reviews by the next business day. Escalate to SEV-2 if customer impact grows, the SLO burn accelerates, or the warning becomes actionable outside business hours. |
| **SEV-4 / Informational** | Recovery/resolution notice, maintenance notice, or low-risk diagnostic information. | No page. Review during normal working hours or include in routine service review. |

These are proposed response objectives, not a staffed 24/7 guarantee. Leadership
must confirm responder availability and escalation contacts. If a target is
missed, continue escalation; do not wait for another alert evaluation interval.

### Escalation tiers

1. **Tier 1 — Primary on-call:** acknowledge, assess impact, follow the alert's
   first action and runbook, and coordinate incident communications.
2. **Tier 2 — Secondary on-call:** take over if the primary is unreachable,
   provide a second responder for SEV-1, and help with diagnosis or mitigation.
3. **Tier 3 — Service/dependency owner:** API/lease-service owner for
   application or event issues; database/DBA for PostgreSQL, connection, query,
   or RDS issues; platform/cloud owner for infrastructure; payment/business
   operations for customer financial-state discrepancies.
4. **Tier 4 — Engineering lead/manager and incident commander:** resolve
   staffing or priority conflicts, authorize higher-risk mitigations, coordinate
   cross-team/customer communication, and decide on deployment restrictions.

Use the incident commander to coordinate a SEV-1 response when available.
Responders should not make irreversible data changes, discard/replay payment
events, reset consumer offsets, or terminate database sessions without the
relevant owner and incident lead agreeing on impact and recovery steps.

## Error budgets and feature deployment policy

Use the SLOs in [SLO.md](./SLO.md) as the reliability contract:

- 99.9% API availability over 30 days (0.1% request error budget).
- 95% of eligible API requests within 300 ms (5% latency budget).
- 99.5% successful non-duplicate event processing (0.5% event error budget).
- 95% of valid synchronous event ingestions within 500 ms (5% latency budget).

Review the rolling 30-day SLOs and recent burn at each weekly service review.
The following are proposed rollout gates; adjust only through an agreed SLO
policy review:

1. **Normal budget:** all SLOs meet target, no active SEV-1/SEV-2 incident, and
   no rapid-burn alert. Feature releases use the normal review, staged rollout,
   health checks, and rollback plan.
2. **Budget burn accelerating:** if an SLO is breached or more than 25% of its
   30-day budget is consumed in any rolling 7-day period, pause risky,
   non-essential changes to the affected service. Continue low-risk changes
   only when they have an explicit owner, canary, rollback plan, and approval
   from the service owner/on-call lead. Prioritize fixes that reduce the burn.
3. **Budget exhausted or active SEV-1:** freeze non-essential feature
   deployments to the affected service. Allow only incident mitigations,
   security fixes, and reliability work approved by the incident commander and
   service owner, with staged rollout and a verified rollback path.
4. **Resume:** require the incident to be resolved, the service stable for an
   agreed observation period, and a written recovery decision by the service
   owner/engineering lead. Record any temporary exception, risk acceptance,
   and expiry.
5. **Low traffic or missing telemetry:** treat an SLO as unknown, not healthy.
   Do not claim budget recovery from an empty denominator; review sample size
   and telemetry quality before using the SLO as a release gate.

Track each SLO's budget separately. A healthy availability budget does not
cancel an exhausted event-processing budget. SLOs and alert formulas should be
reviewed with measured production traffic before being used as an automated
release gate.

## First 90 days: reduce alert fatigue

The goal is fewer, higher-confidence pages—not fewer alerts at the cost of
missed customer impact. Keep a short record of each page, action taken, outcome,
and whether it needed to wake someone.

### Days 1–30: establish signal quality

- Review every alert for an owner, severity, customer impact, specific first
  action, runbook link, and tested delivery route.
- Classify each notification as page, working-hours ticket, dashboard-only, or
  remove. Page only on conditions that need prompt human action.
- Establish baseline traffic, latency, error rates, database connections, and
  health-probe behavior; set minimum sample sizes to avoid low-traffic ratio
  noise.
- Test firing, resolution, deduplication, grouping, and Slack delivery in a
  safe channel. Do not test by generating production payment failures.
- Capture a baseline for pages per week, after-hours pages, false/unactionable
  pages, acknowledgement time, and repeat incidents.
- Add an owner and review date to every alert; fix broken runbook links.

### Days 31–60: tune and remove toil

- Review pages weekly with the four engineers. For each false or
  non-actionable page, fix the query, add an evidence-based `for` duration or
  traffic floor, downgrade it to a ticket, or remove it.
- Group alerts that share one root cause (for example API readiness and
  database unavailability) so one incident does not create a page storm.
- Add inhibition/suppression only when the parent alert clearly explains the
  suppressed symptoms and responders can still see them in dashboards.
- Turn recurring manual diagnostics into safe, documented checks or automation;
  keep destructive remediation human-approved.
- Revisit alert thresholds against observed traffic and SLO/error-budget
  behavior; do not tune solely to reduce page counts.

### Days 61–90: verify and institutionalize

- Run a tabletop or controlled non-production exercise for API health failure,
  event write failures, database pool exhaustion, and Slack/Alertmanager
  delivery failure.
- Measure missed detections as well as false pages; add a targeted signal if
  exercises reveal a real blind spot.
- Compare the 90-day page/false-page baseline with current results, including
  after-hours load and distribution across the four engineers.
- Confirm each alert still has a useful action, owner, tested route, severity,
  and current runbook.
- Publish follow-up actions and owners; schedule a quarterly alert and rota
  review. If the rotation is causing fatigue, change coverage or staffing
  rather than normalizing missed acknowledgements.

## Current implementation boundaries

- This file describes a proposed team process; no rota scheduler, paging
  service, deployment gate, or incident-command integration is implemented by
  this document.
- Prometheus rules exist in `monitoring/prometheus/alerting_rules.yml`.
  Alertmanager has optional Slack routing, but delivery requires a real webhook
  secret and the Compose `notifications` profile.
- The current application processes lease events synchronously through
  PostgreSQL. Kafka consumer lag is not currently a Greenwheels signal.
- Verify actual production alert thresholds, service ownership, contacts, and
  responder coverage before adopting this proposal.
