"""
多模型平台 Schema 定义。
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from core.model_platform.constants import (
    ADAPTER_TYPES,
    CAPABILITY_TYPES,
    CREDENTIAL_TYPES,
    ENDPOINT_TYPES,
    MODEL_GRANTEE_TYPES,
    MODEL_SOURCE_TYPES,
    PROVIDER_PROTOCOL_TYPES,
    RESOURCE_SCOPE_TYPES,
    SYNC_STATUSES,
)
from schemas.common import ListRequest


def _validate_choice(value: str, choices: tuple[str, ...], field_name: str) -> str:
    """统一校验枚举值。"""
    if value not in choices:
        raise ValueError(f"{field_name} 必须是以下之一: {', '.join(choices)}")
    return value


class ModelProviderDefinitionCreate(BaseModel):
    """厂商定义创建 Schema。"""

    provider_code: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    protocol_type: str
    adapter_type: str = "litellm"
    supports_model_discovery: bool = True
    supported_capabilities: list[str] = Field(default_factory=list)
    icon_url: str | None = Field(default=None, max_length=512)
    sort_order: int = 100
    is_builtin: bool = True
    is_enabled: bool = True
    metadata_info: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None

    @field_validator("protocol_type")
    @classmethod
    def validate_protocol_type(cls, value: str) -> str:
        return _validate_choice(value, PROVIDER_PROTOCOL_TYPES, "protocol_type")

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_type(cls, value: str) -> str:
        return _validate_choice(value, ADAPTER_TYPES, "adapter_type")

    @field_validator("supported_capabilities")
    @classmethod
    def validate_supported_capabilities(cls, values: list[str]) -> list[str]:
        return [_validate_choice(value, CAPABILITY_TYPES, "supported_capabilities") for value in values]


class ModelProviderDefinitionUpdate(BaseModel):
    """厂商定义更新 Schema。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    protocol_type: str | None = None
    adapter_type: str | None = None
    supports_model_discovery: bool | None = None
    supported_capabilities: list[str] | None = None
    icon_url: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None
    is_builtin: bool | None = None
    is_enabled: bool | None = None
    metadata_info: dict[str, Any] | None = None
    description: str | None = None

    @field_validator("protocol_type")
    @classmethod
    def validate_protocol_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, PROVIDER_PROTOCOL_TYPES, "protocol_type")

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_type")

    @field_validator("supported_capabilities")
    @classmethod
    def validate_supported_capabilities(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return [_validate_choice(value, CAPABILITY_TYPES, "supported_capabilities") for value in values]


class ModelProviderDefinitionRead(BaseModel):
    """厂商定义读取 Schema。"""

    id: UUID
    provider_code: str
    display_name: str
    protocol_type: str
    adapter_type: str
    supports_model_discovery: bool
    supported_capabilities: list[str]
    icon_url: str | None = None
    sort_order: int
    is_builtin: bool
    is_enabled: bool
    metadata_info: dict[str, Any]
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantModelProviderCreate(BaseModel):
    """租户 provider 创建 Schema。"""

    provider_definition_id: UUID
    resource_scope: str = "tenant"
    owner_user_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    endpoint_type: str = "official"
    base_url: str = Field(..., min_length=1, max_length=1024)
    api_version: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    adapter_override_type: str | None = None
    capability_base_urls: dict[str, str] = Field(
        default_factory=dict,
        description="各能力专用URL，键为 capability_type 如 embedding/rerank，值为 base_url"
    )
    capability_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="各能力高级覆盖配置，如 base_url/endpoint_path/request_schema/adapter_type"
    )
    discovery_config: dict[str, Any] = Field(default_factory=dict)
    request_defaults: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    is_visible_in_ui: bool = True

    @field_validator("endpoint_type")
    @classmethod
    def validate_endpoint_type(cls, value: str) -> str:
        return _validate_choice(value, ENDPOINT_TYPES, "endpoint_type")

    @field_validator("resource_scope")
    @classmethod
    def validate_resource_scope(cls, value: str) -> str:
        return _validate_choice(value, RESOURCE_SCOPE_TYPES, "resource_scope")

    @field_validator("adapter_override_type")
    @classmethod
    def validate_adapter_override_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_override_type")


class TenantModelProviderUpdate(BaseModel):
    """租户 provider 更新 Schema。"""

    resource_scope: str | None = None
    owner_user_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    endpoint_type: str | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=1024)
    api_version: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    adapter_override_type: str | None = None
    capability_base_urls: dict[str, str] | None = Field(default=None, description="各能力专用URL")
    capability_overrides: dict[str, dict[str, Any]] | None = Field(default=None, description="各能力高级覆盖配置")
    discovery_config: dict[str, Any] | None = None
    request_defaults: dict[str, Any] | None = None
    is_enabled: bool | None = None
    is_visible_in_ui: bool | None = None
    sync_status: str | None = None
    sync_error: str | None = None

    @field_validator("endpoint_type")
    @classmethod
    def validate_endpoint_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ENDPOINT_TYPES, "endpoint_type")

    @field_validator("resource_scope")
    @classmethod
    def validate_provider_update_resource_scope(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, RESOURCE_SCOPE_TYPES, "resource_scope")

    @field_validator("adapter_override_type")
    @classmethod
    def validate_adapter_override_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_override_type")

    @field_validator("sync_status")
    @classmethod
    def validate_sync_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, SYNC_STATUSES, "sync_status")


class TenantModelProviderRead(BaseModel):
    """租户 provider 读取 Schema。"""

    id: UUID
    tenant_id: UUID
    resource_scope: str
    owner_user_id: UUID | None = None
    provider_definition_id: UUID
    name: str
    description: str | None = None
    endpoint_type: str
    base_url: str
    api_version: str | None = None
    region: str | None = None
    adapter_override_type: str | None = None
    capability_base_urls: dict[str, Any]
    capability_overrides: dict[str, Any]
    discovery_config: dict[str, Any]
    request_defaults: dict[str, Any]
    is_enabled: bool
    is_visible_in_ui: bool
    last_sync_at: datetime | None = None
    sync_status: str
    sync_error: str | None = None
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    updated_by_id: UUID | None = None
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantModelProviderCredentialCreate(BaseModel):
    """provider 凭证创建 Schema。"""

    tenant_id: UUID
    tenant_provider_id: UUID
    owner_user_id: UUID | None = None
    credential_name: str = Field(..., min_length=1, max_length=128)
    credential_type: str = "api_key"
    encrypted_config: dict[str, Any] = Field(default_factory=dict)
    masked_summary: str | None = Field(default=None, max_length=255)
    is_primary: bool = True
    is_enabled: bool = True
    expires_at: datetime | None = None

    @field_validator("credential_type")
    @classmethod
    def validate_credential_type(cls, value: str) -> str:
        return _validate_choice(value, CREDENTIAL_TYPES, "credential_type")


class TenantModelProviderCredentialUpdate(BaseModel):
    """provider 凭证更新 Schema。"""

    owner_user_id: UUID | None = None
    credential_name: str | None = Field(default=None, min_length=1, max_length=128)
    credential_type: str | None = None
    encrypted_config: dict[str, Any] | None = None
    masked_summary: str | None = Field(default=None, max_length=255)
    is_primary: bool | None = None
    is_enabled: bool | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None

    @field_validator("credential_type")
    @classmethod
    def validate_credential_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, CREDENTIAL_TYPES, "credential_type")


class TenantModelProviderCredentialRead(BaseModel):
    """provider 凭证读取 Schema。"""

    id: UUID
    tenant_id: UUID
    tenant_provider_id: UUID
    owner_user_id: UUID | None = None
    credential_name: str
    credential_type: str
    encrypted_config: dict[str, Any]
    masked_summary: str | None = None
    is_primary: bool
    is_enabled: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformModelCreate(BaseModel):
    """平台模型目录创建 Schema。"""

    provider_definition_id: UUID | None = None
    model_key: str = Field(..., min_length=1, max_length=255)
    raw_model_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    model_type: str
    capabilities: list[str] = Field(default_factory=list)
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    embedding_dimension: int | None = Field(default=None, ge=1)
    supports_stream: bool = False
    supports_tools: bool = False
    supports_structured_output: bool = False
    supports_vision_input: bool = False
    supports_audio_input: bool = False
    supports_audio_output: bool = False
    pricing_metadata: dict[str, Any] = Field(default_factory=dict)
    model_family: str | None = Field(default=None, max_length=128)
    release_channel: str | None = Field(default=None, max_length=64)
    source_type: str = "manual"
    is_builtin: bool = False
    is_enabled: bool = True
    description: str | None = None
    metadata_info: dict[str, Any] = Field(default_factory=dict)

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "model_type")

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, values: list[str]) -> list[str]:
        return [_validate_choice(value, CAPABILITY_TYPES, "capabilities") for value in values]

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        return _validate_choice(value, MODEL_SOURCE_TYPES, "source_type")


class PlatformModelUpdate(BaseModel):
    """平台模型目录更新 Schema。"""

    provider_definition_id: UUID | None = None
    raw_model_name: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    model_type: str | None = None
    capabilities: list[str] | None = None
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    embedding_dimension: int | None = Field(default=None, ge=1)
    supports_stream: bool | None = None
    supports_tools: bool | None = None
    supports_structured_output: bool | None = None
    supports_vision_input: bool | None = None
    supports_audio_input: bool | None = None
    supports_audio_output: bool | None = None
    pricing_metadata: dict[str, Any] | None = None
    model_family: str | None = Field(default=None, max_length=128)
    release_channel: str | None = Field(default=None, max_length=64)
    source_type: str | None = None
    is_builtin: bool | None = None
    is_enabled: bool | None = None
    description: str | None = None
    metadata_info: dict[str, Any] | None = None

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, CAPABILITY_TYPES, "model_type")

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return [_validate_choice(value, CAPABILITY_TYPES, "capabilities") for value in values]

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, MODEL_SOURCE_TYPES, "source_type")


class PlatformModelRead(BaseModel):
    """平台模型目录读取 Schema。"""

    id: UUID
    provider_definition_id: UUID | None = None
    model_key: str
    raw_model_name: str
    display_name: str
    model_type: str
    capabilities: list[str]
    context_window: int | None = None
    max_output_tokens: int | None = None
    embedding_dimension: int | None = None
    supports_stream: bool
    supports_tools: bool
    supports_structured_output: bool
    supports_vision_input: bool
    supports_audio_input: bool
    supports_audio_output: bool
    pricing_metadata: dict[str, Any]
    model_family: str | None = None
    release_channel: str | None = None
    source_type: str
    is_builtin: bool
    is_enabled: bool
    description: str | None = None
    metadata_info: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantModelCreate(BaseModel):
    """租户模型绑定创建 Schema。"""

    resource_scope: str = "tenant"
    owner_user_id: UUID | None = None
    tenant_provider_id: UUID
    platform_model_id: UUID
    model_alias: str | None = Field(default=None, max_length=255)
    model_type: str
    capabilities: list[str] = Field(default_factory=list)
    source_type: str = "discovered"
    group_key: str | None = Field(default=None, max_length=128)
    is_enabled: bool = True
    is_visible_in_ui: bool = True
    is_default_for_type: bool = False
    priority: int = 100
    weight: int = 100
    adapter_override_type: str | None = None
    implementation_key_override: str | None = Field(default=None, min_length=1, max_length=128)
    request_schema_override: str | None = Field(default=None, min_length=1, max_length=128)
    endpoint_path_override: str | None = Field(default=None, min_length=1, max_length=512)
    request_defaults: dict[str, Any] = Field(default_factory=dict)
    model_runtime_config: dict[str, Any] = Field(default_factory=dict)
    rate_limit_config: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    metadata_info: dict[str, Any] = Field(default_factory=dict)

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "model_type")

    @field_validator("resource_scope")
    @classmethod
    def validate_tenant_model_resource_scope(cls, value: str) -> str:
        return _validate_choice(value, RESOURCE_SCOPE_TYPES, "resource_scope")

    @field_validator("capabilities")
    @classmethod
    def validate_tenant_model_capabilities(cls, values: list[str]) -> list[str]:
        return [_validate_choice(value, CAPABILITY_TYPES, "capabilities") for value in values]

    @field_validator("source_type")
    @classmethod
    def validate_tenant_model_source_type(cls, value: str) -> str:
        return _validate_choice(value, MODEL_SOURCE_TYPES, "source_type")

    @field_validator("adapter_override_type")
    @classmethod
    def validate_tenant_model_adapter_override(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_override_type")


class TenantModelUpdate(BaseModel):
    """租户模型绑定更新 Schema。"""

    resource_scope: str | None = None
    owner_user_id: UUID | None = None
    model_alias: str | None = Field(default=None, max_length=255)
    model_type: str | None = None
    capabilities: list[str] | None = None
    source_type: str | None = None
    group_key: str | None = Field(default=None, max_length=128)
    is_enabled: bool | None = None
    is_visible_in_ui: bool | None = None
    is_default_for_type: bool | None = None
    priority: int | None = None
    weight: int | None = None
    adapter_override_type: str | None = None
    implementation_key_override: str | None = Field(default=None, min_length=1, max_length=128)
    request_schema_override: str | None = Field(default=None, min_length=1, max_length=128)
    endpoint_path_override: str | None = Field(default=None, min_length=1, max_length=512)
    request_defaults: dict[str, Any] | None = None
    model_runtime_config: dict[str, Any] | None = None
    rate_limit_config: dict[str, Any] | None = None
    tags: list[str] | None = None
    metadata_info: dict[str, Any] | None = None

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, CAPABILITY_TYPES, "model_type")

    @field_validator("resource_scope")
    @classmethod
    def validate_tenant_model_update_resource_scope(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, RESOURCE_SCOPE_TYPES, "resource_scope")

    @field_validator("capabilities")
    @classmethod
    def validate_tenant_model_update_capabilities(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return [_validate_choice(value, CAPABILITY_TYPES, "capabilities") for value in values]

    @field_validator("source_type")
    @classmethod
    def validate_tenant_model_update_source_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, MODEL_SOURCE_TYPES, "source_type")

    @field_validator("adapter_override_type")
    @classmethod
    def validate_tenant_model_update_adapter_override(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_override_type")


class TenantModelRead(BaseModel):
    """租户模型绑定读取 Schema。"""

    id: UUID
    tenant_id: UUID
    resource_scope: str
    owner_user_id: UUID | None = None
    tenant_provider_id: UUID
    platform_model_id: UUID
    model_alias: str | None = None
    model_type: str
    capabilities: list[str]
    source_type: str
    group_key: str | None = None
    is_enabled: bool
    is_visible_in_ui: bool
    is_default_for_type: bool
    priority: int
    weight: int
    adapter_override_type: str | None = None
    implementation_key_override: str | None = None
    request_schema_override: str | None = None
    endpoint_path_override: str | None = None
    request_defaults: dict[str, Any]
    model_runtime_config: dict[str, Any]
    rate_limit_config: dict[str, Any]
    tags: list[str]
    metadata_info: dict[str, Any]
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    updated_by_id: UUID | None = None
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantDefaultModelCreate(BaseModel):
    """租户默认模型创建 Schema。"""

    resource_scope: str = "tenant"
    owner_user_id: UUID | None = None
    capability_type: str
    tenant_model_id: UUID
    is_enabled: bool = True

    @field_validator("resource_scope")
    @classmethod
    def validate_tenant_default_resource_scope(cls, value: str) -> str:
        return _validate_choice(value, RESOURCE_SCOPE_TYPES, "resource_scope")

    @field_validator("capability_type")
    @classmethod
    def validate_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class TenantDefaultModelUpdate(BaseModel):
    """租户默认模型更新 Schema。"""

    resource_scope: str | None = None
    owner_user_id: UUID | None = None
    capability_type: str | None = None
    tenant_model_id: UUID | None = None
    is_enabled: bool | None = None

    @field_validator("resource_scope")
    @classmethod
    def validate_tenant_default_update_resource_scope(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, RESOURCE_SCOPE_TYPES, "resource_scope")

    @field_validator("capability_type")
    @classmethod
    def validate_capability_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class TenantDefaultModelRead(BaseModel):
    """租户默认模型读取 Schema。"""

    id: UUID
    tenant_id: UUID
    resource_scope: str
    owner_user_id: UUID | None = None
    capability_type: str
    tenant_model_id: UUID
    is_enabled: bool
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    updated_by_id: UUID | None = None
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelAdapterBindingCreate(BaseModel):
    """适配器绑定创建 Schema。"""

    tenant_id: UUID | None = None
    provider_definition_id: UUID | None = None
    tenant_provider_id: UUID | None = None
    capability_type: str
    adapter_type: str
    implementation_key: str = Field(..., min_length=1, max_length=128)
    priority: int = 100
    is_enabled: bool = True
    metadata_info: dict[str, Any] = Field(default_factory=dict)

    @field_validator("capability_type")
    @classmethod
    def validate_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_type(cls, value: str) -> str:
        return _validate_choice(value, ADAPTER_TYPES, "adapter_type")


class ModelAdapterBindingUpdate(BaseModel):
    """适配器绑定更新 Schema。"""

    capability_type: str | None = None
    adapter_type: str | None = None
    implementation_key: str | None = Field(default=None, min_length=1, max_length=128)
    priority: int | None = None
    is_enabled: bool | None = None
    metadata_info: dict[str, Any] | None = None

    @field_validator("capability_type")
    @classmethod
    def validate_capability_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_type")


class ModelAdapterBindingRead(BaseModel):
    """适配器绑定读取 Schema。"""

    id: UUID
    tenant_id: UUID | None = None
    provider_definition_id: UUID | None = None
    tenant_provider_id: UUID | None = None
    capability_type: str
    adapter_type: str
    implementation_key: str
    priority: int
    is_enabled: bool
    metadata_info: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantModelGrantCreate(BaseModel):
    """模型授权创建 Schema。"""

    tenant_id: UUID
    tenant_model_id: UUID
    grantee_type: str
    grantee_id: UUID | None = None
    can_use: bool = True
    can_manage: bool = False

    @field_validator("grantee_type")
    @classmethod
    def validate_grantee_type(cls, value: str) -> str:
        return _validate_choice(value, MODEL_GRANTEE_TYPES, "grantee_type")


class TenantModelGrantUpdate(BaseModel):
    """模型授权更新 Schema。"""

    grantee_type: str | None = None
    grantee_id: UUID | None = None
    can_use: bool | None = None
    can_manage: bool | None = None

    @field_validator("grantee_type")
    @classmethod
    def validate_grantee_type_update(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, MODEL_GRANTEE_TYPES, "grantee_type")


class TenantModelGrantRead(BaseModel):
    """模型授权读取 Schema。"""

    id: UUID
    tenant_id: UUID
    tenant_model_id: UUID
    grantee_type: str
    grantee_id: UUID | None = None
    can_use: bool
    can_manage: bool
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    updated_by_id: UUID | None = None
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelPlatformListRequest(ListRequest):
    """模型平台通用列表请求。"""

    provider_definition_id: UUID | None = None
    tenant_provider_id: UUID | None = None
    model_type: str | None = None
    is_enabled: bool | None = None


class ModelProviderTestConnectionRequest(BaseModel):
    """测试 provider 连通性请求。"""

    tenant_provider_id: UUID = Field(..., description="租户 provider 实例 ID")


class ModelProviderTestConnectionResponse(BaseModel):
    """测试 provider 连通性响应。"""

    success: bool
    provider_id: UUID
    provider_name: str
    protocol_type: str
    base_url: str
    detail: str
    discovered_model_count: int = 0
    sample_models: list[str] = Field(default_factory=list)


class ModelProviderSyncRequest(BaseModel):
    """同步 provider 模型请求。"""

    tenant_provider_id: UUID = Field(..., description="租户 provider 实例 ID")
    auto_enable_models: bool = Field(default=True, description="是否自动启用同步到的模型")
    overwrite_existing_display_name: bool = Field(default=False, description="是否覆盖已有展示名")


class ModelProviderSyncResponse(BaseModel):
    """同步 provider 模型响应。"""

    success: bool
    sync_record_id: UUID
    tenant_provider_id: UUID
    discovered_count: int
    added_count: int
    updated_count: int
    enabled_binding_count: int
    detail: str


class ModelSettingsProviderModelRead(BaseModel):
    """模型设置页中的模型项。"""

    tenant_model_id: UUID
    platform_model_id: UUID
    display_name: str
    raw_model_name: str
    source_type: str | None = None
    model_type: str
    capabilities: list[str]
    group_name: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    embedding_dimension: int | None = None
    supports_stream: bool = False
    supports_tools: bool = False
    supports_structured_output: bool = False
    supports_vision_input: bool = False
    supports_audio_input: bool = False
    supports_audio_output: bool = False
    model_family: str | None = None
    release_channel: str | None = None
    model_runtime_config: dict[str, Any] = Field(default_factory=dict)
    metadata_info: dict[str, Any] = Field(default_factory=dict)
    rate_limit_config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool
    is_visible_in_ui: bool


class ModelSettingsProviderRead(BaseModel):
    """模型设置页中的厂商项。"""

    provider_definition_id: UUID
    tenant_provider_id: UUID | None = None
    provider_code: str
    display_name: str
    is_builtin: bool
    protocol_type: str
    endpoint_type: str
    base_url: str
    is_base_url_editable: bool = True
    is_enabled: bool
    is_visible_in_ui: bool
    is_configured: bool
    supports_model_discovery: bool
    supported_capabilities: list[str]
    runtime_supported_capabilities: list[str] = Field(default_factory=list)
    capability_base_urls: dict[str, str] = Field(default_factory=dict, description="各能力专用URL")
    capability_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict, description="各能力高级覆盖配置")
    icon_url: str | None = None
    sort_order: int
    last_sync_at: datetime | None = None
    sync_status: str | None = None
    sync_error: str | None = None
    has_primary_credential: bool = False
    credential_masked_summary: str | None = None
    models: list[ModelSettingsProviderModelRead] = Field(default_factory=list)


class ModelSettingsDefaultModelRead(BaseModel):
    """模型设置页中的默认模型项。"""

    capability_type: str
    tenant_model_id: UUID


class ModelSettingsOverviewResponse(BaseModel):
    """模型设置页概览响应。"""

    providers: list[ModelSettingsProviderRead] = Field(default_factory=list)
    default_models: list[ModelSettingsDefaultModelRead] = Field(default_factory=list)


class ModelSettingsProviderUpsertRequest(BaseModel):
    """模型设置页厂商配置保存请求。"""

    provider_definition_id: UUID
    tenant_provider_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    endpoint_type: str | None = None
    base_url: str | None = Field(default=None, max_length=1024)
    api_version: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    api_key: str | None = None
    capability_base_urls: dict[str, str] = Field(
        default_factory=dict,
        description="各能力专用URL，键为 capability_type 如 embedding/rerank"
    )
    capability_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="各能力高级覆盖配置，如 endpoint_path/request_schema/adapter_type"
    )
    is_enabled: bool = True
    is_visible_in_ui: bool = True

    @field_validator("endpoint_type")
    @classmethod
    def validate_endpoint_type_for_settings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ENDPOINT_TYPES, "endpoint_type")


class ModelSettingsProviderUpsertResponse(BaseModel):
    """模型设置页厂商配置保存响应。"""

    success: bool
    tenant_provider_id: UUID
    detail: str


class ModelSettingsCustomProviderCreateRequest(BaseModel):
    """创建自定义厂商请求。"""

    display_name: str = Field(..., min_length=1, max_length=128)
    provider_code: str | None = Field(default=None, min_length=1, max_length=64)
    protocol_type: str
    endpoint_type: str = "openai_compatible"
    base_url: str = Field(..., min_length=1, max_length=1024)
    api_key: str | None = None
    supported_capabilities: list[str] = Field(default_factory=list)
    description: str | None = None
    is_enabled: bool = True
    is_visible_in_ui: bool = True

    @field_validator("protocol_type")
    @classmethod
    def validate_custom_provider_protocol_type(cls, value: str) -> str:
        return _validate_choice(value, PROVIDER_PROTOCOL_TYPES, "protocol_type")

    @field_validator("endpoint_type")
    @classmethod
    def validate_custom_provider_endpoint_type(cls, value: str) -> str:
        return _validate_choice(value, ENDPOINT_TYPES, "endpoint_type")

    @field_validator("supported_capabilities")
    @classmethod
    def validate_custom_provider_capabilities(cls, values: list[str]) -> list[str]:
        return [_validate_choice(value, CAPABILITY_TYPES, "supported_capabilities") for value in values]


class ModelSettingsCustomProviderCreateResponse(BaseModel):
    """创建自定义厂商响应。"""

    success: bool
    provider_definition_id: UUID
    tenant_provider_id: UUID
    provider_code: str
    detail: str


class ModelSettingsCustomProviderArchiveRequest(BaseModel):
    """归档自定义厂商请求。"""

    provider_definition_id: UUID


class ModelSettingsCustomProviderArchiveResponse(BaseModel):
    """归档自定义厂商响应。"""

    success: bool
    provider_definition_id: UUID
    detail: str


class ModelSettingsManualModelCreateRequest(BaseModel):
    """手动添加模型请求。"""

    tenant_provider_id: UUID = Field(..., description="租户 provider ID")
    model_key: str = Field(..., min_length=1, max_length=255, description="模型唯一键")
    raw_model_name: str = Field(..., min_length=1, max_length=255, description="厂商原始模型名")
    display_name: str = Field(..., min_length=1, max_length=255, description="展示名称")
    model_type: str = Field(..., description="主能力类型：chat/embedding/rerank 等")
    context_window: int | None = Field(default=None, ge=1, description="上下文窗口，私有化部署或手动模型可按实际配置填写")
    max_output_tokens: int | None = Field(default=None, ge=1, description="最大输出 token 数")
    embedding_dimension: int | None = Field(default=None, ge=1, description="embedding 模型维度（仅 embedding 模型建议填写）")
    capabilities: list[str] = Field(default_factory=list, description="能力列表")
    group_name: str | None = Field(default=None, max_length=128, description="分组名称")
    adapter_override_type: str | None = Field(default=None, description="模型级适配器覆盖")
    implementation_key_override: str | None = Field(default=None, min_length=1, max_length=128, description="模型级实现键覆盖")
    request_schema_override: str | None = Field(default=None, min_length=1, max_length=128, description="模型级请求协议覆盖")
    endpoint_path_override: str | None = Field(default=None, min_length=1, max_length=512, description="模型级 endpoint path 覆盖")
    model_runtime_config: dict[str, Any] = Field(default_factory=dict, description="模型级运行时高级配置")
    rate_limit_config: dict[str, Any] = Field(default_factory=dict, description="模型级限流配置")
    is_enabled: bool = True
    is_visible_in_ui: bool = True

    @field_validator("model_type")
    @classmethod
    def validate_manual_model_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "model_type")

    @field_validator("capabilities")
    @classmethod
    def validate_manual_model_capabilities(cls, values: list[str]) -> list[str]:
        return [_validate_choice(value, CAPABILITY_TYPES, "capabilities") for value in values]

    @field_validator("adapter_override_type")
    @classmethod
    def validate_manual_model_adapter_override(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_choice(value, ADAPTER_TYPES, "adapter_override_type")


class ModelSettingsManualModelCreateResponse(BaseModel):
    """手动添加模型响应。"""

    success: bool
    tenant_model_id: UUID
    platform_model_id: UUID
    detail: str


class ModelSettingsModelsBatchUpdateRequest(BaseModel):
    """模型设置页模型批量更新请求。"""

    model_ids: list[UUID] = Field(..., min_length=1, description="待更新的租户模型 ID 列表")
    is_enabled: bool | None = None
    is_visible_in_ui: bool | None = None

    @model_validator(mode="after")
    def validate_batch_update_patch(self) -> "ModelSettingsModelsBatchUpdateRequest":
        if self.is_enabled is None and self.is_visible_in_ui is None:
            raise ValueError("至少需要提供一个可更新字段")
        return self


class ModelSettingsModelsBatchUpdateResponse(BaseModel):
    """模型设置页模型批量更新响应。"""

    success: bool
    updated_count: int
    detail: str


class ModelSettingsDefaultModelUpsertRequest(BaseModel):
    """模型设置页默认模型保存请求。"""

    capability_type: str
    tenant_model_id: UUID | None = None

    @field_validator("capability_type")
    @classmethod
    def validate_settings_default_capability(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelSettingsDefaultModelUpsertResponse(BaseModel):
    """模型设置页默认模型保存响应。"""

    success: bool
    capability_type: str
    tenant_model_id: UUID | None = None
    detail: str


class ModelChatMessage(BaseModel):
    """统一聊天消息。"""

    role: str = Field(..., description="消息角色：system/user/assistant/tool")
    content: str = Field(..., description="消息内容")

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return _validate_choice(value, ("system", "user", "assistant", "tool"), "role")


class ModelChatCompletionRequest(BaseModel):
    """统一聊天完成请求。"""

    tenant_model_id: UUID | None = Field(default=None, description="租户模型 ID，不传则使用默认聊天模型")
    capability_type: str = Field(default="chat", description="能力类型，当前仅支持 chat")
    messages: list[ModelChatMessage] = Field(..., min_length=1, description="聊天消息列表")
    temperature: float | None = Field(default=None, ge=0, le=2, description="采样温度")
    max_tokens: int | None = Field(default=None, ge=1, description="最大输出 token")
    stream: bool = Field(default=False, description="是否流式输出，当前阶段仅支持 false")
    extra_body: dict[str, Any] = Field(default_factory=dict, description="扩展参数")

    @field_validator("capability_type")
    @classmethod
    def validate_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelChatChoice(BaseModel):
    """统一聊天响应选项。"""

    index: int
    message: ModelChatMessage
    finish_reason: str | None = None


class ModelChatUsage(BaseModel):
    """统一 token 使用信息。"""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ModelChatCompletionResponse(BaseModel):
    """统一聊天完成响应。"""

    model: str
    tenant_model_id: UUID
    capability_type: str
    adapter_type: str
    choices: list[ModelChatChoice]
    usage: ModelChatUsage = Field(default_factory=ModelChatUsage)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ModelEmbeddingRequest(BaseModel):
    """统一向量化请求。"""

    tenant_model_id: UUID | None = Field(default=None, description="租户模型 ID，不传则使用默认 embedding 模型")
    capability_type: str = Field(default="embedding", description="能力类型，当前仅支持 embedding")
    input: str | list[str] = Field(..., description="待向量化文本")
    extra_body: dict[str, Any] = Field(default_factory=dict, description="扩展参数")

    @field_validator("capability_type")
    @classmethod
    def validate_embedding_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelEmbeddingItem(BaseModel):
    """统一向量化结果项。"""

    index: int
    embedding: list[float]


class ModelEmbeddingResponse(BaseModel):
    """统一向量化响应。"""

    model: str
    tenant_model_id: UUID
    capability_type: str
    adapter_type: str
    data: list[ModelEmbeddingItem]
    usage: ModelChatUsage = Field(default_factory=ModelChatUsage)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ModelRerankDocument(BaseModel):
    """统一 rerank 文档。"""

    text: str | None = Field(default=None, description="文本内容")
    image: str | None = Field(default=None, description="图片地址")
    video: str | None = Field(default=None, description="视频地址")

    @model_validator(mode="after")
    def validate_rerank_document_payload(self) -> "ModelRerankDocument":
        if not (self.text or self.image or self.video):
            raise ValueError("文档至少需要提供 text、image、video 之一")
        return self


class ModelRerankRequest(BaseModel):
    """统一 rerank 请求。"""

    tenant_model_id: UUID | None = Field(default=None, description="租户模型 ID，不传则使用默认 rerank 模型")
    capability_type: str = Field(default="rerank", description="能力类型，当前仅支持 rerank")
    query: str | dict[str, Any] = Field(..., description="查询内容，支持字符串或多模态查询结构")
    documents: list[str | ModelRerankDocument] = Field(..., min_length=1, description="候选文档列表")
    top_n: int | None = Field(default=None, ge=1, description="返回前 N 条")
    return_documents: bool | None = Field(default=None, description="是否返回原文档")
    extra_body: dict[str, Any] = Field(default_factory=dict, description="扩展参数")

    @field_validator("capability_type")
    @classmethod
    def validate_rerank_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelRerankResult(BaseModel):
    """统一 rerank 结果。"""

    index: int
    score: float
    document: str | dict[str, Any] | None = None


class ModelRerankResponse(BaseModel):
    """统一 rerank 响应。"""

    model: str
    tenant_model_id: UUID
    capability_type: str
    adapter_type: str
    results: list[ModelRerankResult]
    usage: ModelChatUsage = Field(default_factory=ModelChatUsage)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ModelAudioTranscriptionRequest(BaseModel):
    """统一语音识别请求。"""

    tenant_model_id: UUID | None = Field(default=None, description="租户模型 ID，不传则使用默认 asr 模型")
    capability_type: str = Field(default="asr", description="能力类型，当前仅支持 asr")
    audio_url: str | None = Field(default=None, description="音频文件地址")
    audio_base64: str | None = Field(default=None, description="base64 编码后的音频内容")
    filename: str | None = Field(default=None, description="文件名，不传则自动推导")
    mime_type: str | None = Field(default=None, description="音频 MIME 类型")
    language: str | None = Field(default=None, description="语言提示")
    prompt: str | None = Field(default=None, description="识别提示词")
    response_format: str | None = Field(default=None, description="上游响应格式，如 json/text/srt")
    temperature: float | None = Field(default=None, ge=0, le=2, description="采样温度")
    extra_body: dict[str, Any] = Field(default_factory=dict, description="扩展参数")

    @field_validator("capability_type")
    @classmethod
    def validate_asr_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")

    @model_validator(mode="after")
    def validate_audio_source(self) -> "ModelAudioTranscriptionRequest":
        if not self.audio_url and not self.audio_base64:
            raise ValueError("audio_url 与 audio_base64 至少需要提供一个")
        return self


class ModelAudioTranscriptionSegment(BaseModel):
    """统一语音识别分段。"""

    id: int | None = None
    start: float | None = None
    end: float | None = None
    text: str | None = None


class ModelAudioTranscriptionResponse(BaseModel):
    """统一语音识别响应。"""

    model: str
    tenant_model_id: UUID
    capability_type: str
    adapter_type: str
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    segments: list[ModelAudioTranscriptionSegment] = Field(default_factory=list)
    usage: ModelChatUsage = Field(default_factory=ModelChatUsage)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ModelSpeechRequest(BaseModel):
    """统一语音合成请求。"""

    tenant_model_id: UUID | None = Field(default=None, description="租户模型 ID，不传则使用默认 tts 模型")
    capability_type: str = Field(default="tts", description="能力类型，当前仅支持 tts")
    input: str = Field(..., min_length=1, description="待合成文本")
    voice: str = Field(default="alloy", min_length=1, description="音色名称")
    response_format: str | None = Field(default=None, description="输出格式，如 mp3/wav/pcm")
    speed: float | None = Field(default=None, gt=0, le=4, description="语速")
    extra_body: dict[str, Any] = Field(default_factory=dict, description="扩展参数")

    @field_validator("capability_type")
    @classmethod
    def validate_tts_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelSpeechResponse(BaseModel):
    """统一语音合成响应。"""

    model: str
    tenant_model_id: UUID
    capability_type: str
    adapter_type: str
    audio_base64: str
    content_type: str
    content_length: int | None = None
    usage: ModelChatUsage = Field(default_factory=ModelChatUsage)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ModelDebugRuntimeProfileRequest(BaseModel):
    """调试面板运行时画像预览请求。"""

    tenant_model_id: UUID = Field(..., description="租户模型 ID")
    capability_type: str = Field(..., description="能力类型")

    @field_validator("capability_type")
    @classmethod
    def validate_debug_runtime_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelDebugRuntimeProfileResponse(BaseModel):
    """调试面板运行时画像预览响应。"""

    tenant_model_id: UUID
    provider_name: str
    provider_code: str
    model_name: str
    display_name: str
    capability_type: str
    adapter_type: str
    implementation_key: str
    request_schema: str
    response_schema: str
    base_url: str
    endpoint_path: str | None = None
    effective_url: str
    supports_multimodal_input: bool = False
    timeout_seconds: float = 30.0
    concurrency_limit: int | None = None
    concurrency_mode: str | None = None
    concurrency_wait_timeout_seconds: int | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)
    sources: dict[str, str] = Field(default_factory=dict)


class ModelDebugInvokeRequest(BaseModel):
    """调试面板最小调用请求。"""

    tenant_model_id: UUID = Field(..., description="租户模型 ID")
    capability_type: str = Field(..., description="能力类型")
    prompt: str | None = Field(default=None, description="chat / embedding / tts 的测试文本")
    query: str | None = Field(default=None, description="rerank 查询文本")
    documents: list[str] = Field(default_factory=list, description="rerank 文档列表")
    audio_url: str | None = Field(default=None, description="asr 测试音频地址")
    audio_base64: str | None = Field(default=None, description="asr 测试音频 base64")
    filename: str | None = Field(default=None, description="asr 文件名")
    mime_type: str | None = Field(default=None, description="asr 音频 MIME 类型")
    voice: str | None = Field(default=None, description="tts 音色")
    response_format: str | None = Field(default=None, description="asr / tts 上游响应格式")
    temperature: float | None = Field(default=None, ge=0, le=2, description="chat / asr 温度")
    max_tokens: int | None = Field(default=None, ge=1, description="chat 最大输出 token")
    top_n: int | None = Field(default=None, ge=1, description="rerank 返回前 N 条")
    return_documents: bool | None = Field(default=None, description="rerank 是否返回原文档")

    @field_validator("capability_type")
    @classmethod
    def validate_debug_invoke_capability_type(cls, value: str) -> str:
        return _validate_choice(value, CAPABILITY_TYPES, "capability_type")


class ModelDebugInvokeResponse(BaseModel):
    """调试面板最小调用响应。"""

    profile: ModelDebugRuntimeProfileResponse
    result: dict[str, Any] = Field(default_factory=dict)
