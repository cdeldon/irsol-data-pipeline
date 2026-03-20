"""Static command metadata and registries for the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from irsol_data_pipeline.orchestration.flows.tags import DeploymentTopicTag
from irsol_data_pipeline.orchestration.variables import PrefectVariableName

OutputFormat = Literal["table", "json"]
FlowGroupName = Literal[
    "flat-field-correction",
    "slit-images",
    "maintenance",
]


@dataclass(frozen=True)
class VariableMetadata:
    """Metadata describing one configurable Prefect variable.

    Attributes:
        prefect_name: Canonical Prefect variable name.
        prompt_text: Prompt displayed during interactive configuration.
        default_value: Optional default shown to operators.
        required: Whether the variable must be set for normal operation.
        topic_tags: Flow groups that depend on this variable.
    """

    prefect_name: PrefectVariableName
    prompt_text: str
    default_value: str | None = None
    required: bool = True
    topic_tags: tuple[DeploymentTopicTag, ...] = ()


@dataclass(frozen=True)
class FlowMetadata:
    """Metadata describing one flow/deployment exposed by the CLI.

    Attributes:
        group_name: User-facing flow-group identifier.
        flow_name: Registered Prefect flow name.
        deployment_name: Deployment name created by `flows serve`.
        description: Operator-facing description.
        automation: Automation mode tag.
        schedule: Schedule label shown in reports.
    """

    group_name: FlowGroupName
    flow_name: str
    deployment_name: str
    description: str
    automation: Literal["manual", "scheduled"]
    schedule: str


@dataclass(frozen=True)
class FlowGroupMetadata:
    """Metadata describing one flow group.

    Attributes:
        name: Canonical CLI flow-group name.
        topic_tag: Deployment topic tag associated with the group.
        description: Human-readable group summary.
        flows: Concrete flow metadata entries served by the group.
    """

    name: FlowGroupName
    topic_tag: DeploymentTopicTag
    description: str
    flows: tuple[FlowMetadata, ...] = field(default_factory=tuple)


VARIABLES: tuple[VariableMetadata, ...] = (
    VariableMetadata(
        prefect_name=PrefectVariableName.JSOC_EMAIL,
        prompt_text=(
            "JSOC email (register at http://jsoc.stanford.edu/ajax/register_email.html)"
        ),
        required=True,
        topic_tags=(DeploymentTopicTag.SLIT_IMAGES,),
    ),
    VariableMetadata(
        prefect_name=PrefectVariableName.CACHE_EXPIRATION_HOURS,
        prompt_text="Cache expiration time in hours (e.g. 4 weeks)",
        default_value=f"{24 * 7 * 4}",
        required=False,
        topic_tags=(DeploymentTopicTag.MAINTENANCE,),
    ),
    VariableMetadata(
        prefect_name=PrefectVariableName.FLOW_RUN_EXPIRATION_HOURS,
        prompt_text="Prefect flow-run history retention in hours (e.g. 4 weeks)",
        default_value=f"{24 * 7 * 4}",
        required=False,
        topic_tags=(DeploymentTopicTag.MAINTENANCE,),
    ),
)


FLOW_GROUPS: tuple[FlowGroupMetadata, ...] = (
    FlowGroupMetadata(
        name="flat-field-correction",
        topic_tag=DeploymentTopicTag.FLAT_FIELD_CORRECTION,
        description="Serve the flat-field correction deployments.",
        flows=(
            FlowMetadata(
                group_name="flat-field-correction",
                flow_name="ff-correction-full",
                deployment_name="flat-field-correction-full",
                description=(
                    "Run the flat field correction pipeline on all unprocessed "
                    "measurements."
                ),
                automation="scheduled",
                schedule="daily",
            ),
            FlowMetadata(
                group_name="flat-field-correction",
                flow_name="ff-correction-daily",
                deployment_name="flat-field-correction-daily",
                description="Run the flat field correction pipeline on a specific day folder.",
                automation="manual",
                schedule="manual",
            ),
        ),
    ),
    FlowGroupMetadata(
        name="slit-images",
        topic_tag=DeploymentTopicTag.SLIT_IMAGES,
        description="Serve the slit-image generation deployments.",
        flows=(
            FlowMetadata(
                group_name="slit-images",
                flow_name="slit-images-full",
                deployment_name="slit-images-full",
                description=(
                    "Generate slit preview images for all unprocessed measurements."
                ),
                automation="scheduled",
                schedule="daily",
            ),
            FlowMetadata(
                group_name="slit-images",
                flow_name="slit-images-daily",
                deployment_name="slit-images-daily",
                description=(
                    "Generate slit preview images for a specific observation day."
                ),
                automation="manual",
                schedule="manual",
            ),
        ),
    ),
    FlowGroupMetadata(
        name="maintenance",
        topic_tag=DeploymentTopicTag.MAINTENANCE,
        description="Serve maintenance and retention-cleanup deployments.",
        flows=(
            FlowMetadata(
                group_name="maintenance",
                flow_name="maintenance-cleanup",
                deployment_name="prefect-run-cleanup",
                description="Delete Prefect flow runs older than a retention duration.",
                automation="scheduled",
                schedule="daily",
            ),
            FlowMetadata(
                group_name="maintenance",
                flow_name="maintenance-cache-cleanup",
                deployment_name="cache-cleanup",
                description=(
                    "Delete stale .pkl cache files under processed/_cache and "
                    "processed/_sdo_cache."
                ),
                automation="scheduled",
                schedule="daily",
            ),
        ),
    ),
)


FLOW_GROUP_NAMES: tuple[FlowGroupName, ...] = tuple(group.name for group in FLOW_GROUPS)
