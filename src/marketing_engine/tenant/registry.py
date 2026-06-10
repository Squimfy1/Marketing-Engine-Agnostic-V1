"""Discover and validate tenants and their brands from the vault.

A tenant exists iff ``tenants/<id>/tenant.yaml`` parses against ``TenantConfig``.
A brand exists iff ``.../brands/<id>/brand.yaml`` parses against ``BrandConfig``.
There is no central registry file to drift — the filesystem is the registry.

All lookups fail fast with a clear, typed error so the CLI/engine can surface a
useful message instead of a stack trace deep inside the agent.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from marketing_engine.brand.schema import BrandConfig
from marketing_engine.tenant.schema import TenantConfig
from marketing_engine.vault.layout import VaultLayout


class RegistryError(Exception):
    """Base class for tenant/brand resolution failures."""


class TenantNotFoundError(RegistryError):
    pass


class BrandNotFoundError(RegistryError):
    pass


class ConfigInvalidError(RegistryError):
    pass


def _load_yaml(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - exercised via ConfigInvalidError
        raise ConfigInvalidError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigInvalidError(f"{path} must contain a YAML mapping, got {type(raw).__name__}")
    return raw


class Registry:
    """Resolves ``TenantConfig`` / ``BrandConfig`` against a vault layout."""

    def __init__(self, layout: VaultLayout) -> None:
        self.layout = layout

    # -- tenants ---------------------------------------------------------
    def list_tenants(self) -> list[str]:
        tenants_dir = self.layout.tenants_dir
        if not tenants_dir.is_dir():
            return []
        ids = [
            d.name
            for d in sorted(tenants_dir.iterdir())
            if d.is_dir() and (d / "tenant.yaml").is_file()
        ]
        return ids

    def get_tenant(self, tenant_id: str) -> TenantConfig:
        config_path = self.layout.tenant_config(tenant_id)
        if not config_path.is_file():
            known = ", ".join(self.list_tenants()) or "(none)"
            raise TenantNotFoundError(
                f"No tenant '{tenant_id}' (missing {config_path}). Known tenants: {known}"
            )
        data = _load_yaml(config_path)
        data.setdefault("id", tenant_id)
        try:
            config = TenantConfig(**data)
        except ValidationError as exc:
            raise ConfigInvalidError(f"Invalid tenant config {config_path}:\n{exc}") from exc
        if config.id != tenant_id:
            raise ConfigInvalidError(
                f"{config_path}: id '{config.id}' does not match folder '{tenant_id}'"
            )
        return config

    # -- brands ----------------------------------------------------------
    def list_brands(self, tenant_id: str) -> list[str]:
        brands_dir = self.layout.brands_dir(tenant_id)
        if not brands_dir.is_dir():
            return []
        return [
            d.name
            for d in sorted(brands_dir.iterdir())
            if d.is_dir() and (d / "brand.yaml").is_file()
        ]

    def get_brand(self, tenant_id: str, brand_id: str) -> BrandConfig:
        # Resolving the brand implies the tenant must exist and be valid.
        self.get_tenant(tenant_id)
        config_path = self.layout.brand_config(tenant_id, brand_id)
        if not config_path.is_file():
            known = ", ".join(self.list_brands(tenant_id)) or "(none)"
            raise BrandNotFoundError(
                f"No brand '{brand_id}' under tenant '{tenant_id}' (missing {config_path}). "
                f"Known brands: {known}"
            )
        data = _load_yaml(config_path)
        data.setdefault("id", brand_id)
        try:
            config = BrandConfig(**data)
        except ValidationError as exc:
            raise ConfigInvalidError(f"Invalid brand config {config_path}:\n{exc}") from exc
        if config.id != brand_id:
            raise ConfigInvalidError(
                f"{config_path}: id '{config.id}' does not match folder '{brand_id}'"
            )
        return config
