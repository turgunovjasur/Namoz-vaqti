"""Execute the approved selection once, preserving canonical service evidence."""

from typing import cast

from namoz_bot.application.capabilities.registry import CapabilityRegistry
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.authorization import access_context
from namoz_bot.application.workforce.ports import TaskStore
from namoz_bot.domain.agent_protocol import AgentRequest
from namoz_bot.domain.workforce.tasks import ClaimedTask, TaskRevision


class TaskExecutionService:
    def __init__(self, store: TaskStore, access: AccessService, capabilities: CapabilityRegistry):
        self.store, self.access, self.capabilities = store, access, capabilities

    async def run(self, claim: ClaimedTask) -> TaskRevision:
        return await self._execute(claim, replace_read=False)

    async def reread(self, claim: ClaimedTask) -> TaskRevision:
        if self.capabilities.get(claim.task.plan.selection.capability_id).spec.effect != "read":
            raise ValueError("Writes cannot be repeated during review")
        return await self._execute(claim, replace_read=True)

    async def _execute(self, claim: ClaimedTask, *, replace_read: bool) -> TaskRevision:
        plan = claim.task.plan
        current = await self.store.get_owned(plan.task_id, plan.context)
        if current.service_result is not None and not replace_read:
            return current
        selection = self.access.roles.validate_selection(plan.selection)
        await self.access.require(plan.context.user_id, selection.role_id, selection.capability_id)
        capability = self.capabilities.get(selection.capability_id)
        if capability.spec.requires_result and plan.parent_revision is None:
            raise ValueError("Correction is not bound to a result")
        view = selection.parameters.get("view")
        route = next(
            (r for r in capability.spec.routes if r.view == view), capability.spec.routes[0]
        )
        request = AgentRequest(
            domain=route.domain,
            action=route.action,
            parameters=selection.parameters,
            transcript=plan.transcript,
            context=plan.context,
            operation_id=f"{plan.task_id}{plan.revision:06x}",
            request_id=f"task:{plan.task_id}:{plan.revision}",
        )
        with access_context(
            self.access,
            user_id=plan.context.user_id,
            telegram_user_id=plan.context.telegram_user_id,
            role_id=selection.role_id,
            capability_id=selection.capability_id,
        ):
            prepared = await capability.prepare(request)
            async with self.store.effect_scope(
                plan.task_id, plan.revision, claim.lease_token
            ) as tx:
                await self.access.require_in(
                    tx, plan.context.user_id, selection.role_id, selection.capability_id
                )
                result = prepared
                if prepared.status == "needs_confirmation":
                    from pydantic import JsonValue

                    request = AgentRequest.model_validate(
                        {
                            **request.model_dump(),
                            "parameters": cast(dict[str, JsonValue], prepared.data["draft"]),
                        }
                    )
                    result = await capability.execute(request, tx)
                elif prepared.status == "done" and not prepared.data:
                    result = await capability.execute(request, tx)
                await tx.save_result(result, replace_read=replace_read)
        return await self.store.get_owned(plan.task_id, plan.context)
