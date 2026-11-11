# Panel-managed agents and parallel tasks

Approved conversation requirements: exactly one permanent, editable assistant receives user messages, delegates to an admin-created specialist and returns its result. Specialists, including existing ones, are database configuration using a shared agent implementation. Admins set names, duties, models, skills, enabled state and user grants. A long-running task must not block accepting, starting or delivering another task.

Implementation decisions: preserve existing database roles/grants/models; bootstrap only the assistant on clean installations. Historical migration data and legacy domain parsers are compatibility artifacts, not the live role catalog. Retire the old manager catalog entry. Archive specialists rather than erase task history. Keep skills implemented in trusted backend code. Keep explicit approval for business work; accepted tasks remain independent of subsequent drafts. Use configurable bounded concurrency (default 3), refill available worker slots without waiting for an entire batch, deliver outbox independently, and prepare slow generated/read results outside owner transaction locks. Expose task identity in notifications.

Not included: a slide-generation skill, model-provider expansion or deployment to production.
