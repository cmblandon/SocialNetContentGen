## REMOVED Requirements

### Requirement: Publish Approved Content To Social Networks
**Reason**: The system's deliverable is now an approved script, handed to the operator for rendering in an external video tool. It no longer produces anything publishable, so it cannot publish.

**Migration**: Replaced by `script-export`. Publishing and scheduling move entirely outside the system, alongside video production.

### Requirement: Editorial Calendar And Optimal Publishing Time
**Reason**: Scheduling exists to decide when to post. The system no longer posts.

**Migration**: None. The calendar and its `optimal_time` configuration are removed.

### Requirement: Publish Record Audit Trail
**Reason**: Records the outcome of publish attempts that no longer occur.

**Migration**: None. The `publish_records` table is dropped. Historical rows are preserved on the `archive/pre-pivot` branch.
