"""Compare service evidence; a reviewer never supplies replacement facts."""

from collections.abc import Callable
from dataclasses import dataclass

from namoz_bot.application.workforce.ports import ResultReviewer
from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.domain.workforce.tasks import ReviewVerdict, TaskPlan


@dataclass(frozen=True)
class ReviewedResult:
    verdict: ReviewVerdict
    text: str


class ReviewService:
    def __init__(self, reviewer: ResultReviewer, renderer: Callable[[AgentResult], str]):
        self.reviewer, self.renderer = reviewer, renderer

    async def inspect(self, plan: TaskPlan, result: AgentResult) -> ReviewVerdict:
        if result.status != "done":
            return ReviewVerdict(
                decision="clarify", issues=["Xizmat aniqlashtirish yoki qayta urinish so‘radi."]
            )
        parameters, data = plan.selection.parameters, result.data
        issues = []
        if result.action in {"income", "expense"}:
            for field in ("amount", "category"):
                if parameters.get(field) is not None and data.get(field) != parameters[field]:
                    issues.append(f"{field} tasdiqlangan parametrga mos emas.")
        if (
            result.action == "report"
            and parameters.get("month")
            and str(data.get("month", ""))[:7] != str(parameters["month"])[:7]
        ):
            issues.append("Hisobot oyi tasdiqlangan oyga mos emas.")
        if issues:
            return ReviewVerdict(decision="revise", issues=issues)
        return await self.reviewer.review(plan, result)

    def render(self, result: AgentResult, *, complete: bool) -> str:
        text = self.renderer(result)
        if not complete:
            text += "\n\n" + ("Amal saqlandi. " if result.effect == "committed" else "")
            text += "Natijani tekshirish yakunlanmadi. Xato bo‘lsa «Yo‘q» orqali ayting."
        if result.status == "done":
            text += "\n\nSiz kutgan natijami?"
        return text
