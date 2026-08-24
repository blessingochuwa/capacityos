"""Phase 20 — scenario-vs-baseline prioritization comparison
(docs/adr/0020-scenario-priority-comparison.md).

Deliberately its own service, not a method bolted onto
ScenarioCalculationService or ProjectPriorityScoreService: it reuses both
(ProjectPriorityScoreService.compute_result/values_dict for the scoring
engine itself, never a second one) without either of those services
needing to know Scenario/Prioritization overrides exist.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.prioritization import (
    PriorityScoreResult,
    rank_priority_results,
    validate_category_for_framework_type,
)
from app.models.enums import PrioritizationFrameworkType
from app.models.prioritization_framework import PrioritizationFramework
from app.models.project import Project
from app.models.scenario import Scenario
from app.models.scenario_priority_override import ScenarioPriorityOverride
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.repositories.scenario import ScenarioRepository
from app.repositories.scenario_priority_override import ScenarioPriorityOverrideRepository
from app.schemas.scenario_priority import ScenarioPriorityOverrideSet
from app.services.project_priority_score import ProjectPriorityScoreService


@dataclass(frozen=True)
class ScenarioPriorityComparisonItem:
    project: Project
    has_override: bool
    baseline_result: PriorityScoreResult
    baseline_rank: int | None
    scenario_result: PriorityScoreResult
    scenario_rank: int | None
    changed: bool


class ScenarioPriorityService:
    """Organization-scoped (Phase 12) — scenario_id, project_id, and
    framework_id are each independently verified same-organization before
    an override is ever written or a comparison ever computed, the same
    "resolve through the org-scoped repository first" discipline as every
    other cross-entity service in this codebase.

    Authorization note: gated entirely by SCENARIO_READ/WRITE/DELETE
    (role-only, no ProjectAccessGrant) — matching every other Scenario
    mutation (Phase 16 deliberately kept Scenario role-only, not
    instance-scoped). A caller who can read/write Scenarios in this
    organization can create overrides against, and compare against, any
    project in the SAME organization — exactly the same reach
    PRIORITIZATION_READ already grants for the live portfolio board, and
    exactly the same reach every other Scenario operation already has
    over the projects/people it references. Organization membership,
    not a project-level grant, is the access boundary here.
    """

    def __init__(
        self,
        override_repository: ScenarioPriorityOverrideRepository,
        scenario_repository: ScenarioRepository,
        project_repository: ProjectRepository,
        framework_repository: PrioritizationFrameworkRepository,
        score_repository: ProjectPriorityScoreRepository,
        score_service: ProjectPriorityScoreService,
    ) -> None:
        self.override_repository = override_repository
        self.scenario_repository = scenario_repository
        self.project_repository = project_repository
        self.framework_repository = framework_repository
        self.score_repository = score_repository
        self.score_service = score_service

    # -- Overrides --------------------------------------------------------

    def set_override(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, data: ScenarioPriorityOverrideSet
    ) -> ScenarioPriorityOverride:
        """Create-or-replace (upsert) the override for this
        (scenario, project, framework) triple — see
        ScenarioPriorityOverrideSet's docstring for why this is
        deliberately not a separate PATCH endpoint."""
        self._require_scenario(organization_id, scenario_id)
        if self.project_repository.get(data.project_id, organization_id) is None:
            raise NotFoundError("Project", data.project_id)
        framework = self._require_framework(organization_id, data.framework_id)

        validate_category_for_framework_type(framework.framework_type, data.category)
        if data.values and framework.framework_type == PrioritizationFrameworkType.MOSCOW:
            raise DomainValidationError(
                "MOSCOW frameworks have no criteria to override — set category instead."
            )
        criteria_keys = {c.key for c in framework.criteria}
        for item in data.values:
            if item.criterion_key not in criteria_keys:
                raise DomainValidationError(
                    f"'{item.criterion_key}' is not a criterion of framework "
                    f"'{framework.name}'."
                )
        values = {item.criterion_key: str(item.value) for item in data.values}

        existing = self.override_repository.get_by_natural_key(
            scenario_id, data.project_id, data.framework_id, organization_id
        )
        if existing is not None:
            existing.values = values
            existing.category = data.category
            self.override_repository.session.flush()
            return existing

        override = self.override_repository.add(
            ScenarioPriorityOverride(
                organization_id=organization_id,
                scenario_id=scenario_id,
                project_id=data.project_id,
                framework_id=data.framework_id,
                values=values,
                category=data.category,
            )
        )
        self.override_repository.session.flush()
        self.override_repository.session.refresh(override, attribute_names=["project", "framework"])
        return override

    def list_for_scenario(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID
    ) -> list[ScenarioPriorityOverride]:
        self._require_scenario(organization_id, scenario_id)
        return self.override_repository.list_for_scenario(scenario_id, organization_id)

    def delete_override(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, override_id: uuid.UUID
    ) -> None:
        self._require_scenario(organization_id, scenario_id)
        override = self.override_repository.get(override_id, organization_id)
        if override is None or override.scenario_id != scenario_id:
            raise NotFoundError("ScenarioPriorityOverride", override_id)
        self.override_repository.delete(override)

    # -- Comparison ---------------------------------------------------------

    def compare(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, framework_id: uuid.UUID
    ) -> tuple[Scenario, PrioritizationFramework, list[ScenarioPriorityComparisonItem]]:
        """Baseline ranking vs. scenario ranking for one framework — the
        SAME calculate_priority_score/rank_priority_results machinery the
        live portfolio board uses, run twice: once against each project's
        real, persisted values, once against those same values with this
        scenario's overrides merged on top. A project with no override at
        all naturally scores identically on both sides (its "scenario"
        values ARE its baseline values, unmodified) — never a special
        case, just what the merge produces when there's nothing to
        merge."""
        scenario = self._require_scenario(organization_id, scenario_id)
        framework = self._require_framework(organization_id, framework_id)

        baseline_scores = self.score_repository.list_for_framework(framework_id, organization_id)
        overrides = self.override_repository.list_for_scenario_and_framework(
            scenario_id, framework_id, organization_id
        )
        baseline_by_project = {s.project_id: s for s in baseline_scores}
        override_by_project = {o.project_id: o for o in overrides}

        projects_by_id: dict[uuid.UUID, Project] = {
            score.project_id: score.project for score in baseline_scores
        }
        for project_id, override in override_by_project.items():
            projects_by_id.setdefault(project_id, override.project)

        baseline_entries: list[tuple[uuid.UUID, PriorityScoreResult]] = []
        scenario_entries: list[tuple[uuid.UUID, PriorityScoreResult]] = []
        computed: dict[uuid.UUID, tuple[PriorityScoreResult, PriorityScoreResult, bool]] = {}

        for project_id in projects_by_id:
            score = baseline_by_project.get(project_id)
            baseline_values = (
                self.score_service.values_dict(framework, score) if score is not None else {}
            )
            baseline_category = score.category if score is not None else None
            baseline_result = self.score_service.compute_result(
                framework, baseline_values, baseline_category
            )

            override = override_by_project.get(project_id)
            if override is not None:
                scenario_values = {
                    **baseline_values,
                    **{key: Decimal(value) for key, value in override.values.items()},
                }
                scenario_category = (
                    override.category if override.category is not None else baseline_category
                )
            else:
                scenario_values = baseline_values
                scenario_category = baseline_category
            scenario_result = self.score_service.compute_result(
                framework, scenario_values, scenario_category
            )

            baseline_entries.append((project_id, baseline_result))
            scenario_entries.append((project_id, scenario_result))
            computed[project_id] = (baseline_result, scenario_result, override is not None)

        baseline_rank_by_project = {
            project_id: rank for project_id, _, rank in rank_priority_results(baseline_entries)
        }
        scenario_ranked = rank_priority_results(scenario_entries)
        scenario_rank_by_project = {
            project_id: rank for project_id, _, rank in scenario_ranked
        }

        items: list[ScenarioPriorityComparisonItem] = []
        for project_id, (baseline_result, scenario_result, has_override) in computed.items():
            baseline_rank = baseline_rank_by_project[project_id]
            scenario_rank = scenario_rank_by_project[project_id]
            baseline_key = (baseline_result.score, baseline_result.category, baseline_rank)
            scenario_key = (scenario_result.score, scenario_result.category, scenario_rank)
            items.append(
                ScenarioPriorityComparisonItem(
                    project=projects_by_id[project_id],
                    has_override=has_override,
                    baseline_result=baseline_result,
                    baseline_rank=baseline_rank,
                    scenario_result=scenario_result,
                    scenario_rank=scenario_rank,
                    changed=baseline_key != scenario_key,
                )
            )
        items.sort(key=lambda item: (item.scenario_rank is None, item.scenario_rank or 0))
        return scenario, framework, items

    # -- Reference validation -------------------------------------------

    def _require_scenario(self, organization_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.scenario_repository.get(scenario_id, organization_id)
        if scenario is None:
            raise NotFoundError("Scenario", scenario_id)
        return scenario

    def _require_framework(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID
    ) -> PrioritizationFramework:
        framework = self.framework_repository.get(framework_id, organization_id)
        if framework is None:
            raise NotFoundError("PrioritizationFramework", framework_id)
        return framework
