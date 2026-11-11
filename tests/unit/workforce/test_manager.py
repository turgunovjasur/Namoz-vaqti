import pytest

from namoz_bot.application.workforce.planning import Manager
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.profiles import AccessDenied
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_role_model_settings import service
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant
from tests.integration.test_workforce_tasks import workforce as workforce


class Interpreter:
    def __init__(self, capability="finance.income"):
        self.capability = capability
        self.calls = []

    async def route(self, **kwargs):
        self.calls.append(("route", kwargs))
        return "accounting"

    async def interpret(self, **kwargs):
        self.calls.append(("interpret", kwargs))
        return CapabilitySelection(
            role_id="accounting",
            capability_id=self.capability,
            parameters={
                "amount": 1000,
                "currency": "UZS",
                "category": "oylik",
                "description": "Oylik",
            }
            if self.capability != "finance.report"
            else {},
        )


async def test_manager_sends_only_granted_catalog_and_rejects_forged_specialist(workforce):
    tasks, _, access, plan, _, profiles, _ = workforce
    await grant(
        profiles, plan.context.user_id, plan.context.user_id, "accounting", {"finance.report"}
    )
    ai = Interpreter("finance.expense")
    manager = Manager(access, service(profiles), ai, tasks)
    with pytest.raises(AccessDenied):
        await manager.plan(context=plan.context, request_id="new", text="Sarfladim", pending=None)
    available = ai.calls[0][1]["roles"]
    assert len(available) == 1 and available[0].capability_ids == ("finance.report",)
    capabilities = ai.calls[1][1]["capabilities"]
    assert [c.id for c in capabilities] == ["finance.report"]


async def test_task_pins_models_parameters_and_does_not_read_business_before_approval(workforce):
    tasks, _, access, old, _, profiles, _ = workforce
    ai = Interpreter()
    manager = Manager(access, service(profiles), ai, tasks)
    plan = await manager.plan(
        context=old.context, request_id="new", text="Oylik tushdi", pending=None
    )
    assert plan.selection.parameters["amount"] == 1000
    assert plan.models["accounting"].model_id == "original-model"
    assert len(ai.calls) == 2
    assert (await tasks.get_owned(plan.task_id, plan.context)).status == "awaiting_approval"


async def test_task_pins_edited_assistant_identity_and_duties_for_review(workforce):
    tasks, _, access, old, _, profiles, _ = workforce
    roles = tuple(
        role.model_copy(
            update={
                "name": "Kotib",
                "instruction": "Natijani foydalanuvchi vazifasiga solishtir.",
                "common_rules": "Faqat xizmat dalillariga tayan.",
            }
        )
        if role.id == "assistant"
        else role
        for role in access.roles.all()
    )
    manager = Manager(access, service(profiles), Interpreter(), tasks)
    with access.roles.bind(roles):
        plan = await manager.plan(
            context=old.context, request_id="edited-assistant", text="Oylik tushdi", pending=None
        )
    saved = await tasks.get_owned(plan.task_id, plan.context)
    assert "Kotib" in saved.plan.review_instruction
    assert "Natijani foydalanuvchi vazifasiga solishtir." in saved.plan.review_instruction
    assert "Faqat xizmat dalillariga tayan." in saved.plan.review_instruction


async def test_reviewer_failure_after_save_returns_receipt_and_never_reexecutes(workforce):
    from sqlalchemy import select

    from namoz_bot.application.capabilities.registry import build_capability_registry
    from namoz_bot.application.workforce.execution import TaskExecutionService
    from namoz_bot.application.workforce.manager import ManagedExecution
    from namoz_bot.application.workforce.review import ReviewService
    from namoz_bot.infrastructure.orm import FinanceEntryRecord, WorkforceOutboxRecord
    from namoz_bot.presentation.result_messages import render_result

    tasks, queue, access, plan, factory, _, current = workforce

    class FailedReviewer:
        async def review(self, plan, result):
            raise TimeoutError("provider failed")

    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    claim = (await queue.claim(now=current[0], limit=3, lease_seconds=180))[0]
    await ManagedExecution(
        tasks,
        TaskExecutionService(tasks, access, build_capability_registry()),
        ReviewService(FailedReviewer(), render_result),
    ).run(claim)
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1
        result = await session.scalar(
            select(WorkforceOutboxRecord).where(WorkforceOutboxRecord.kind == "result")
        )
        assert result.status == "pending"
        assert "10 000 000" in result.payload["text"] and "Amal saqlandi" in result.payload["text"]
    assert (await tasks.get_owned(plan.task_id, plan.context)).status == "awaiting_feedback"


async def test_revise_on_write_is_bounded_without_repeating_effect(workforce):
    from sqlalchemy import select

    from namoz_bot.application.capabilities.registry import build_capability_registry
    from namoz_bot.application.workforce.execution import TaskExecutionService
    from namoz_bot.application.workforce.manager import ManagedExecution
    from namoz_bot.application.workforce.review import ReviewService
    from namoz_bot.domain.workforce.tasks import ReviewVerdict
    from namoz_bot.infrastructure.orm import FinanceEntryRecord
    from namoz_bot.presentation.result_messages import render_result

    tasks, queue, access, plan, factory, _, current = workforce

    class Reviewer:
        calls = 0

        async def review(self, plan, result):
            self.calls += 1
            return ReviewVerdict(decision="revise", issues=["Kategoriya tekshirilsin."])

    reviewer = Reviewer()
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    claim = (await queue.claim(now=current[0], limit=3, lease_seconds=180))[0]
    await ManagedExecution(
        tasks,
        TaskExecutionService(tasks, access, build_capability_registry()),
        ReviewService(reviewer, render_result),
    ).run(claim)
    assert reviewer.calls == 2
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_shared_capability_requires_explicit_role_and_never_switches(workforce):
    from namoz_bot.domain.workforce.tasks import ClarificationRequired

    tasks, _, access, old, _, profiles, _ = workforce
    owner = old.context.user_id
    await grant(profiles, owner, owner, "prayer", {"preferences.region_view"})
    await grant(profiles, owner, owner, "settings", {"preferences.region_view"})

    class Shared:
        async def route(self, **kwargs):
            return "settings"

        async def interpret(self, **kwargs):
            return CapabilitySelection(
                role_id="settings",
                capability_id="preferences.region_view",
                parameters={"view": "region"},
            )

    manager = Manager(access, service(profiles), Shared(), tasks)
    with pytest.raises(ClarificationRequired):
        await manager.plan(
            context=old.context, request_id="ambiguous", text="Hududim qaysi?", pending=None
        )
    plan = await manager.plan(
        context=old.context, request_id="named", text="Sozlovchi hududim qaysi?", pending=None
    )
    assert plan.selection.role_id == "settings"


async def test_wrong_month_read_is_reread_once_without_ledger_writes(workforce):
    from sqlalchemy import select

    from namoz_bot.application.capabilities.registry import build_capability_registry
    from namoz_bot.application.workforce.execution import TaskExecutionService
    from namoz_bot.application.workforce.manager import ManagedExecution
    from namoz_bot.application.workforce.review import ReviewService
    from namoz_bot.domain.workforce.tasks import ReviewVerdict
    from namoz_bot.infrastructure.orm import FinanceEntryRecord, WorkforceRevisionRecord
    from namoz_bot.presentation.result_messages import render_result

    tasks, queue, access, old, factory, profiles, current = workforce
    owner = old.context.user_id
    await grant(profiles, owner, owner, "accounting", {"finance.report"})
    plan = old.model_copy(
        update={
            "permission": await access.require(owner, "accounting", "finance.report"),
            "selection": CapabilitySelection(
                role_id="accounting",
                capability_id="finance.report",
                parameters={"month": "2026-10"},
            ),
        }
    )
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    claim = (await queue.claim(now=current[0], limit=3, lease_seconds=180))[0]
    executor = TaskExecutionService(tasks, access, build_capability_registry())
    await executor.run(claim)
    async with factory.begin() as session:
        row = await session.get(WorkforceRevisionRecord, (plan.task_id, 1))
        row.service_result = {
            **row.service_result,
            "data": {**row.service_result["data"], "month": "2026-09-01"},
        }

    class Reviewer:
        async def review(self, plan, result):
            return ReviewVerdict(decision="accept")

    await ManagedExecution(tasks, executor, ReviewService(Reviewer(), render_result)).run(claim)
    result = await tasks.get_owned(plan.task_id, plan.context)
    assert result.service_result.data["month"] == "2026-10-01" and result.review_attempts == 1
    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
