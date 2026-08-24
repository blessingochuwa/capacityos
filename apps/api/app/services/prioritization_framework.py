import uuid

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.domain.prioritization import FIXED_CRITERION_KEYS
from app.models.enums import PrioritizationFrameworkType
from app.models.prioritization_criterion import PrioritizationCriterion
from app.models.prioritization_framework import PrioritizationFramework
from app.repositories.prioritization_criterion import PrioritizationCriterionRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.schemas.prioritization import (
    CriterionCreate,
    CriterionUpdate,
    PrioritizationFrameworkCreate,
    PrioritizationFrameworkUpdate,
    slugify_criterion_key,
)

_FIXED_CRITERION_NAMES: dict[str, str] = {
    "reach": "Reach",
    "impact": "Impact",
    "confidence": "Confidence",
    "effort": "Effort",
    "ease": "Ease",
    "business_value": "Business Value",
    "time_criticality": "Time Criticality",
    "risk_reduction_opportunity_enablement": "Risk Reduction / Opportunity Enablement",
    "job_size": "Job Size",
}
"""Display names for every fixed criterion key across RICE/ICE/WSJF
(Phase 18 generalizes what was previously an RICE-only dict) — keyed by
the same machine keys app/domain/prioritization.py's *_CRITERION_KEYS
tuples define, so _seed_fixed_criteria never has to special-case which
framework type it's seeding."""


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

        if data.framework_type in FIXED_CRITERION_KEYS:
            self._seed_fixed_criteria(
                organization_id, framework, FIXED_CRITERION_KEYS[data.framework_type]
            )
        elif data.framework_type == PrioritizationFrameworkType.WEIGHTED:
            self._seed_weighted_criteria(organization_id, framework, data.criteria)
        # MOSCOW: no criteria at all — see calculate_moscow_result's docstring.

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

    def _seed_fixed_criteria(
        self, organization_id: uuid.UUID, framework: PrioritizationFramework, keys: tuple[str, ...]
    ) -> None:
        for sequence, key in enumerate(keys):
            self.criterion_repository.add(
                PrioritizationCriterion(
                    framework_id=framework.id,
                    organization_id=organization_id,
                    key=key,
                    name=_FIXED_CRITERION_NAMES[key],
                    weight=None,
                    is_editable=False,
                    sequence=sequence,
                )
            )

    def add_criterion(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID, data: CriterionCreate
    ) -> PrioritizationCriterion:
        """Add one new criterion to an existing Weighted Scoring framework
        (Phase 18). Only WEIGHTED accepts this — RICE/ICE/WSJF's criteria
        are fixed by the methodology (adding a fifth RICE criterion isn't
        RICE anymore) and MOSCOW has none at all, so both raise
        ForbiddenError rather than silently accepting a criterion that
        would never be used by any formula."""
        framework = self.get(organization_id, framework_id)
        if framework.framework_type != PrioritizationFrameworkType.WEIGHTED:
            raise ForbiddenError(
                f"{framework.framework_type.value.upper()}'s criteria are fixed by the "
                "methodology itself — only a Weighted Scoring framework's criteria can be edited."
            )

        key = slugify_criterion_key(data.name)
        if not key:
            raise DomainValidationError(
                f"Criterion name '{data.name}' has no usable characters for a key."
            )
        existing_keys = {c.key for c in framework.criteria}
        if key in existing_keys:
            raise ConflictError(
                f"This framework already has a criterion with key '{key}' — choose a more "
                "distinct name."
            )

        next_sequence = max((c.sequence for c in framework.criteria), default=-1) + 1
        criterion = self.criterion_repository.add(
            PrioritizationCriterion(
                framework_id=framework.id,
                organization_id=organization_id,
                key=key,
                name=data.name,
                weight=data.weight,
                is_editable=True,
                sequence=next_sequence,
            )
        )
        self.repository.session.flush()
        self.criterion_repository.session.refresh(criterion)
        return criterion

    def update_criterion(
        self,
        organization_id: uuid.UUID,
        framework_id: uuid.UUID,
        criterion_id: uuid.UUID,
        data: CriterionUpdate,
    ) -> PrioritizationCriterion:
        """Rename and/or reweight one existing criterion. `key` is never
        changed by a rename — it stays the stable identifier
        ProjectPriorityCriterionValue rows and app/domain/prioritization.py
        key off of, so renaming a criterion never orphans previously
        recorded values or requires a re-key migration."""
        criterion = self._require_editable_criterion(organization_id, framework_id, criterion_id)
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(criterion, field, value)
        self.criterion_repository.session.flush()
        # Refresh so a reweight comes back quantized to the column's
        # declared scale (Numeric(6, 3)) exactly like a freshly seeded
        # criterion does — without this, the in-memory attribute would
        # still hold the caller's raw, unquantized Decimal.
        self.criterion_repository.session.refresh(criterion)
        return criterion

    def remove_criterion(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID, criterion_id: uuid.UUID
    ) -> None:
        """Removing a framework's last remaining criterion is rejected —
        the same "a weighted framework needs at least one criterion"
        invariant PrioritizationFrameworkCreate enforces at creation time
        (see its docstring), just as true after the fact."""
        criterion = self._require_editable_criterion(organization_id, framework_id, criterion_id)
        remaining = self.criterion_repository.list_for_framework(framework_id, organization_id)
        if len(remaining) <= 1:
            raise DomainValidationError(
                "Cannot remove a framework's last remaining criterion — a weighted-scoring "
                "framework needs at least one."
            )
        self.criterion_repository.delete(criterion)

    def _require_editable_criterion(
        self, organization_id: uuid.UUID, framework_id: uuid.UUID, criterion_id: uuid.UUID
    ) -> PrioritizationCriterion:
        criterion = self.criterion_repository.get(criterion_id, organization_id)
        if criterion is None or criterion.framework_id != framework_id:
            raise NotFoundError("PrioritizationCriterion", criterion_id)
        if not criterion.is_editable:
            raise ForbiddenError(
                "This criterion is fixed by its framework's methodology and cannot be edited."
            )
        return criterion

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
