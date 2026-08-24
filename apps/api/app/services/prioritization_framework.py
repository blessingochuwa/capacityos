import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.domain.prioritization import RICE_CRITERION_KEYS
from app.models.enums import PrioritizationFrameworkType
from app.models.prioritization_criterion import PrioritizationCriterion
from app.models.prioritization_framework import PrioritizationFramework
from app.repositories.prioritization_criterion import PrioritizationCriterionRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.schemas.prioritization import (
    CriterionCreate,
    PrioritizationFrameworkCreate,
    PrioritizationFrameworkUpdate,
    slugify_criterion_key,
)

_RICE_CRITERION_NAMES: dict[str, str] = {
    "reach": "Reach",
    "impact": "Impact",
    "confidence": "Confidence",
    "effort": "Effort",
}


class PrioritizationFrameworkService:
    """Organization-scoped (Phase 12) — create/list/get/update/deactivate
    a PrioritizationFramework, including seeding RICE's fixed criteria.
    See docs/PRD-phase-17-prioritization.md §5/§6."""

    def __init__(
        self,
        repository: PrioritizationFrameworkRepository,
        criterion_repository: PrioritizationCriterionRepository,
    ) -> None:
        self.repository = repository
        self.criterion_repository = criterion_repository

    def create(
        self, organization_id: uuid.UUID, data: PrioritizationFrameworkCreate
    ) -> PrioritizationFramework:
        if self.repository.get_by_name(data.name, organization_id) is not None:
            raise ConflictError(
                f"A prioritization framework named '{data.name}' already exists."
            )

        framework = self.repository.add(
            PrioritizationFramework(
                organization_id=organization_id,
                name=data.name,
                framework_type=data.framework_type,
                is_active=True,
            )
        )

        if data.framework_type == PrioritizationFrameworkType.RICE:
            self._seed_rice_criteria(organization_id, framework)
        else:
            self._seed_weighted_criteria(organization_id, framework, data.criteria)

        self.repository.session.flush()
        self.repository.session.refresh(framework, attribute_names=["criteria"])
        return framework

    def get(self, organization_id: uuid.UUID, framework_id: uuid.UUID) -> PrioritizationFramework:
        framework = self.repository.get(framework_id, organization_id)
        if framework is None:
            raise NotFoundError("PrioritizationFramework", framework_id)
        return framework

    def list(
        self,
        organization_id: uuid.UUID,
        *,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PrioritizationFramework], int]:
        return self.repository.list(
            organization_id, is_active=is_active, limit=limit, offset=offset
        )

    def update(
        self,
        organization_id: uuid.UUID,
        framework_id: uuid.UUID,
        data: PrioritizationFrameworkUpdate,
    ) -> PrioritizationFramework:
        framework = self.get(organization_id, framework_id)
        updates = data.model_dump(exclude_unset=True)

        new_name = updates.get("name")
        if (
            new_name is not None
            and new_name != framework.name
            and self.repository.get_by_name(new_name, organization_id) is not None
        ):
            raise ConflictError(f"A prioritization framework named '{new_name}' already exists.")

        for field, value in updates.items():
            setattr(framework, field, value)
        self.repository.session.flush()
        return framework

    def deactivate(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID
    ) -> PrioritizationFramework:
        """Soft-delete only — matches Skill.is_active's exact precedent.
        Existing ProjectPriorityScore rows under this framework stay
        readable; the framework is excluded from ranking and from the
        create-framework name-uniqueness check going forward (an
        organization may reuse a deactivated framework's name)."""
        framework = self.get(organization_id, framework_id)
        framework.is_active = False
        self.repository.session.flush()
        return framework

    def _seed_rice_criteria(
        self, organization_id: uuid.UUID, framework: PrioritizationFramework
    ) -> None:
        for sequence, key in enumerate(RICE_CRITERION_KEYS):
            self.criterion_repository.add(
                PrioritizationCriterion(
                    framework_id=framework.id,
                    organization_id=organization_id,
                    key=key,
                    name=_RICE_CRITERION_NAMES[key],
                    weight=None,
                    is_editable=False,
                    sequence=sequence,
                )
            )

    def _seed_weighted_criteria(
        self,
        organization_id: uuid.UUID,
        framework: PrioritizationFramework,
        criteria: list[CriterionCreate],
    ) -> None:
        seen_keys: set[str] = set()
        for sequence, criterion in enumerate(criteria):
            key = slugify_criterion_key(criterion.name)
            if not key:
                raise DomainValidationError(
                    f"Criterion name '{criterion.name}' has no usable characters for a key."
                )
            if key in seen_keys:
                raise DomainValidationError(
                    f"Two criteria produce the same key ('{key}') — choose more distinct names."
                )
            seen_keys.add(key)
            self.criterion_repository.add(
                PrioritizationCriterion(
                    framework_id=framework.id,
                    organization_id=organization_id,
                    key=key,
                    name=criterion.name,
                    weight=criterion.weight,
                    is_editable=True,
                    sequence=sequence,
                )
            )
