import uuid
from decimal import Decimal

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.domain.prioritization import CriterionWeight, PriorityScoreResult, calculate_priority_score
from app.models.enums import MoscowCategory, PrioritizationFrameworkType
from app.models.prioritization_framework import PrioritizationFramework
from app.models.project import Project
from app.models.project_priority_criterion_value import ProjectPriorityCriterionValue
from app.models.project_priority_score import ProjectPriorityScore
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.schemas.prioritization import (
    CriterionValueInput,
    ProjectPriorityScoreCreate,
    ProjectPriorityScoreUpdate,
)

RankedEntry = tuple[Project, ProjectPriorityScore, PriorityScoreResult]


class ProjectPriorityScoreService:
    """Organization-scoped (Phase 12), project-nested (matches
    RiskService/PersonSkillService's exact pattern) — project_id and
    framework_id are each independently verified same-organization before
    a score is ever written, the same "resolve through the org-scoped
    repository first" discipline as every other cross-entity service in
    this codebase.

    Every read recomputes the score via app/domain/prioritization.py —
    see ProjectPriorityScore's model docstring for why nothing here is
    ever cached."""

    def __init__(
        self,
        repository: ProjectPriorityScoreRepository,
        project_repository: ProjectRepository,
        framework_repository: PrioritizationFrameworkRepository,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.framework_repository = framework_repository

    def create(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, data: ProjectPriorityScoreCreate
    ) -> tuple[ProjectPriorityScore, PriorityScoreResult]:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        framework = self._require_framework(organization_id, data.framework_id)
        if (
            self.repository.get_by_project_and_framework(
                project_id, data.framework_id, organization_id
            )
            is not None
        ):
            raise ConflictError(
                "This project already has a score recorded under this framework — "
                "update it instead of creating a second one."
            )

        self._validate_category(framework, data.category)
        score = self.repository.add(
            ProjectPriorityScore(
                organization_id=organization_id,
                project_id=project_id,
                framework_id=data.framework_id,
                category=data.category,
                notes=data.notes,
            )
        )
        self._apply_values(framework, score, data.values)
        self.repository.session.flush()
        return score, self._compute(framework, score)

    def get(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, score_id: uuid.UUID
    ) -> tuple[ProjectPriorityScore, PriorityScoreResult]:
        score = self._get_owned(organization_id, project_id, score_id)
        return score, self._compute(score.framework, score)

    def list_for_project(
        self, organization_id: uuid.UUID, project_id: uuid.UUID
    ) -> list[tuple[ProjectPriorityScore, PriorityScoreResult]]:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        scores = self.repository.list_for_project(project_id, organization_id)
        return [(score, self._compute(score.framework, score)) for score in scores]

    def update(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        score_id: uuid.UUID,
        data: ProjectPriorityScoreUpdate,
    ) -> tuple[ProjectPriorityScore, PriorityScoreResult]:
        score = self._get_owned(organization_id, project_id, score_id)
        framework = score.framework

        updates = data.model_dump(exclude_unset=True, exclude={"values"})
        if "category" in updates:
            self._validate_category(framework, updates["category"])
        for field, value in updates.items():
            setattr(score, field, value)
        if data.values is not None:
            self._apply_values(framework, score, data.values)

        self.repository.session.flush()
        return score, self._compute(framework, score)

    def delete(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, score_id: uuid.UUID
    ) -> None:
        score = self._get_owned(organization_id, project_id, score_id)
        self.repository.delete(score)

    def rank_portfolio(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID
    ) -> tuple[PrioritizationFramework, list[RankedEntry]]:
        """Every project currently scored under this framework, ordered by
        computed score descending — a project with a still-incomplete
        score (missing_criteria non-empty) is listed last, unranked,
        never sorted as if a missing input were zero."""
        framework = self._require_framework(organization_id, framework_id)
        scores = self.repository.list_for_framework(framework_id, organization_id)
        computed = [(score.project, score, self._compute(framework, score)) for score in scores]
        computed.sort(key=lambda entry: (entry[2].score is None, -(entry[2].score or Decimal(0))))
        return framework, computed

    def _apply_values(
        self,
        framework: PrioritizationFramework,
        score: ProjectPriorityScore,
        values: list[CriterionValueInput],
    ) -> None:
        """Upsert per criterion_key (see ProjectPriorityScoreUpdate's
        docstring for why this is deliberately NOT a full-replace like
        WorkingScheduleUpdate.entries) — a criterion not mentioned in
        `values` keeps whatever value it already had."""
        criteria_by_key = {c.key: c for c in framework.criteria}
        values_by_criterion_id = {v.criterion_id: v for v in score.values}
        for item in values:
            criterion = criteria_by_key.get(item.criterion_key)
            if criterion is None:
                raise DomainValidationError(
                    f"'{item.criterion_key}' is not a criterion of framework '{framework.name}'."
                )
            existing_value = values_by_criterion_id.get(criterion.id)
            if existing_value is not None:
                existing_value.value = item.value
            else:
                score.values.append(
                    ProjectPriorityCriterionValue(criterion_id=criterion.id, value=item.value)
                )

    def _compute(
        self, framework: PrioritizationFramework, score: ProjectPriorityScore
    ) -> PriorityScoreResult:
        criteria_by_id = {c.id: c for c in framework.criteria}
        weights = [
            CriterionWeight(key=c.key, weight=c.weight if c.weight is not None else Decimal(0))
            for c in framework.criteria
        ]
        values: dict[str, Decimal] = {}
        for criterion_value in score.values:
            criterion = criteria_by_id.get(criterion_value.criterion_id)
            if criterion is not None:
                values[criterion.key] = criterion_value.value
        return calculate_priority_score(
            framework.framework_type, weights, values, category=score.category
        )

    def _validate_category(
        self, framework: PrioritizationFramework, category: MoscowCategory | None
    ) -> None:
        """`category` is only ever meaningful for a MOSCOW framework — see
        ProjectPriorityScore.category's model docstring. Supplying it
        against any other framework_type is rejected rather than silently
        ignored, since a caller who set it clearly expected it to matter."""
        if category is not None and framework.framework_type != PrioritizationFrameworkType.MOSCOW:
            raise DomainValidationError(
                f"'category' is only meaningful for a MOSCOW framework, not "
                f"{framework.framework_type.value.upper()}."
            )

    def _require_framework(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID
    ) -> PrioritizationFramework:
        framework = self.framework_repository.get(framework_id, organization_id)
        if framework is None:
            raise NotFoundError("PrioritizationFramework", framework_id)
        return framework

    def _get_owned(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, score_id: uuid.UUID
    ) -> ProjectPriorityScore:
        score = self.repository.get(score_id, organization_id)
        if score is None or score.project_id != project_id:
            raise NotFoundError("ProjectPriorityScore", score_id)
        return score
