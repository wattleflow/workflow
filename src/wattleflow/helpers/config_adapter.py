# Module name: helpers/config_adapter.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2026 WattleFlow. All rights reserved.
# License: Apache 2 Licence


# --------------------------------------------------------------------------- #
# region Imports                                                              #
# --------------------------------------------------------------------------- #

from __future__ import annotations
import os
import re
from abc import ABC, abstractmethod
from logging import Handler
from pathlib import Path
from typing import Any, Optional

from wattleflow.core import IHandler
from wattleflow.concrete.logger import AuditLogger
from wattleflow.helpers.config import Config

try:
    import yaml
except Exception:
    from wattleflow.helpers.yaml import yaml  # noqa: E401

# --------------------------------------------------------------------------- #
# endregion Imports                                                           #
# --------------------------------------------------------------------------- #


_REF_PATTERN = re.compile(r"^\$\{\s*(\w+)\s*:\s*([^}]+)\s*\}$")


# --------------------------------------------------------------------------- #
# region Global methods                                                       #
# --------------------------------------------------------------------------- #
def config_section(*path: str):

    def decorator(cls):
        cls._CONFIG_SECTION_PATH = path
        original_init = cls.__init__

        def patched_init(self, *args, **kwargs):
            config: Optional[Config] = kwargs.pop("config", None)
            chain: Optional[SecretResolverChain] = kwargs.pop("resolver_chain", None)

            name = kwargs.get("name")

            if config is not None:
                adapter = ConfigAdapter(config, *path, resolver_chain=chain)

                if name:
                    for section in adapter.as_dict().values():
                        if isinstance(section, list):
                            for item in section:
                                if item.get("name") == name:
                                    for k, v in item.items():
                                        kwargs.setdefault(k, v)
                                    break
                else:
                    for k, v in adapter.as_dict().items():
                        kwargs.setdefault(k, v)

            original_init(self, *args, **kwargs)

        cls.__init__ = patched_init
        return cls

    return decorator


def deep_resolve(value: Any, chain: SecretResolverChain) -> Any:
    if isinstance(value, str):
        resolved = chain.resolve(value)
        return resolved if resolved is not None else value

    if isinstance(value, dict):
        return {k: deep_resolve(v, chain) for k, v in value.items()}

    if isinstance(value, list):
        return [deep_resolve(v, chain) for v in value]

    return value


# --------------------------------------------------------------------------- #
# endregion Global methods                                                    #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Interfaces                                                           #
# --------------------------------------------------------------------------- #


class ISecretResolver(ABC):
    """Strategy interface for resolving secret references embedded in config values.
    A secret reference has the form: ${prefix:reference}
    e.g. ${env:MY_VAR}, ${aws:my-secret/key}, ${vault:secret/data/app/db_pass}
    """

    PREFIX: str = ""

    def can_resolve(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        m = _REF_PATTERN.match(value)
        return m is not None and m.group(1) == self.PREFIX

    # def resolve(self, value: str) -> Optional[str]:
    def resolve(self, value: Any, strict: bool = False) -> Optional[str]:
        m = _REF_PATTERN.match(value)
        if m is None or m.group(1) != self.PREFIX:
            return None
        return self._fetch(m.group(2))

    @abstractmethod
    def _fetch(self, ref: str) -> Optional[str]: ...


class IConfigValidator(IHandler, ABC):
    """
    Chain of Responsibility za validaciju razrijesene konfiguracije.
    Nasljedivanje: implementiraj validate() u konkretnoj klasi.
    Ulancavanje:   validator_a.set_next(validator_b).set_next(validator_c)
    """

    def __init__(self) -> None:
        self._next: Optional["IConfigValidator"] = None

    def set_next(self, handler: "IConfigValidator") -> "IConfigValidator":
        self._next = handler
        return handler

    def handle(self, data: Any) -> Any:
        self.validate(data)
        return self._next.handle(data) if self._next else data

    @abstractmethod
    def validate(self, data: Any) -> None: ...


# --------------------------------------------------------------------------- #
# endregion Interfaces                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Resolvers                                                            #
# --------------------------------------------------------------------------- #


class EnvVarResolver(ISecretResolver):
    """Resolves ${env:VAR_NAME} references from environment variables."""

    PREFIX = "env"

    def _fetch(self, ref: str) -> Optional[str]:
        return os.environ.get(ref)


class AwsSecretsResolver(ISecretResolver):
    """Resolves ${aws:secret-id/key} references from AWS Secrets Manager.

    ref format: secret-id/json-key  (key is optional for plain-string secrets)
    """

    PREFIX = "aws"

    def __init__(self, region_name: str = "us-east-1") -> None:
        self._region = region_name

    def _fetch(self, ref: str) -> Optional[str]:
        try:
            import boto3  # noqa: PLC0415
            import json  # noqa: PLC0415

            client = boto3.client("secretsmanager", region_name=self._region)
            parts = ref.rsplit("/", 1)
            secret_id = parts[0] if len(parts) == 2 else ref
            key = parts[1] if len(parts) == 2 else None
            response = client.get_secret_value(SecretId=secret_id)
            secret = response.get("SecretString", "")
            if key:
                return json.loads(secret).get(key)
            return secret
        except Exception:
            return None


class AzureKeyVaultResolver(ISecretResolver):
    """Resolves ${azure:secret-name} references from Azure Key Vault."""

    PREFIX = "azure"

    def __init__(self, vault_url: str) -> None:
        self._vault_url = vault_url

    def _fetch(self, ref: str) -> Optional[str]:
        try:
            from azure.keyvault.secrets import SecretClient  # noqa: PLC0415
            from azure.identity import DefaultAzureCredential  # noqa: PLC0415

            client = SecretClient(
                vault_url=self._vault_url,
                credential=DefaultAzureCredential(),
            )
            return client.get_secret(ref).value
        except Exception:
            return None


class GcpSecretResolver(ISecretResolver):
    """Resolves ${gcp:projects/P/secrets/S/versions/V} references from GCP Secret Manager."""

    PREFIX = "gcp"

    def _fetch(self, ref: str) -> Optional[str]:
        try:
            from google.cloud import secretmanager  # noqa: PLC0415

            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(request={"name": ref})
            return response.payload.data.decode("UTF-8")
        except Exception:
            return None


class VaultResolver(ISecretResolver):
    """Resolves ${vault:secret/path/key} references from HashiCorp Vault (KV v2)."""

    PREFIX = "vault"

    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token

    def _fetch(self, ref: str) -> Optional[str]:
        try:
            import hvac  # noqa: PLC0415

            client = hvac.Client(url=self._url, token=self._token)
            parts = ref.rsplit("/", 1)
            path = parts[0] if len(parts) == 2 else ref
            key = parts[1] if len(parts) == 2 else None
            data = client.secrets.kv.read_secret_version(path=path)["data"]["data"]
            return data.get(key) if key else str(data)
        except Exception:
            return None


class SecretResolverChain:
    __slots__ = ("_resolvers",)

    def __init__(self) -> None:
        self._resolvers: list[ISecretResolver] = []

    def add(self, resolver: ISecretResolver) -> "SecretResolverChain":
        self._resolvers.append(resolver)
        return self

    def resolve(self, value: Any) -> Optional[str]:
        for resolver in self._resolvers:
            if resolver.can_resolve(value):
                try:
                    result = resolver.resolve(value)
                    if result is not None:
                        return result
                except Exception:
                    continue
        return None


# --------------------------------------------------------------------------- #
# endregion Resolvers                                                         #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region Validators                                                           #
# --------------------------------------------------------------------------- #


class TypeValidator(IConfigValidator):
    """Validates that the resolved config root is a mapping (dict)."""

    def validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            raise TypeError(f"Config: expected mapping at root, got {type(data).__name__}")


class RequiredKeysValidator(IConfigValidator):
    """Validates that all specified top-level keys are present."""

    def __init__(self, *keys: str) -> None:
        super().__init__()
        self._keys = keys

    def validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        missing = [k for k in self._keys if k not in data]
        if missing:
            raise ValueError(f"Config: missing required keys {missing}")


class AllowedKeysValidator(IConfigValidator):
    """Validates that no keys outside the allowed set are present."""

    def __init__(self, *keys: str) -> None:
        super().__init__()
        self._allowed = set(keys)

    def validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        unknown = [k for k in data if k not in self._allowed]
        if unknown:
            raise ValueError(f"Config: unexpected keys {unknown}")


class AllowedValuesValidator(IConfigValidator):
    """Validates that a specific key holds one of the allowed values."""

    def __init__(self, key: str, *allowed: Any) -> None:
        super().__init__()
        self._key = key
        self._allowed = set(allowed)

    def validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        value = data.get(self._key)
        if value is not None and value not in self._allowed:
            raise ValueError(f"Config: {self._key!r} must be one of {self._allowed}, got {value!r}")


class NonEmptyValidator(IConfigValidator):
    """Validates that specified keys are present and non-empty."""

    def __init__(self, *keys: str) -> None:
        super().__init__()
        self._keys = keys

    def validate(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        for key in self._keys:
            value = data.get(key)
            if value is None or value == "" or value == [] or value == {}:
                raise ValueError(f"Config: {key!r} must be non-empty")


# --------------------------------------------------------------------------- #
# endregion Validators                                                        #
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# region ConfigAdapter                                                        #
# --------------------------------------------------------------------------- #


class ConfigAdapter(AuditLogger):
    def __init__(
        self,
        config_file: Path,
        *section_path: str,
        **kwargs,
    ) -> None:

        level = kwargs.get("level", 0)
        handler: Optional[Handler] = kwargs.get("handler", None)
        formater = {"formating": kwargs.get("formatter")} if kwargs.get("formating") else {}
        validator: Optional[IConfigValidator] = kwargs.get("validator", None)
        resolver_chain: Optional[SecretResolverChain] = kwargs.get("resolver_chain", None)

        AuditLogger.__init__(self, level=level, handler=handler, **formater)

        self._config_file: Path = config_file
        self._section_path = section_path
        self._chain = resolver_chain
        self._root: Any = None
        self._resolved: Any = None

        config = Config(config_file=config_file)
        self._resolve_all(config)

        if validator:
            validator.handle(self._resolved)

    def _resolve_all(self, config: Config) -> None:
        self._root = config.find(*self._section_path)

        if self._chain:
            self._resolved = deep_resolve(self._root, self._chain)
        else:
            self._resolved = self._root

    def _maybe_resolve(self, value: Any) -> Any:
        if self._chain:
            return deep_resolve(value, self._chain)
        return value

    def find(
        self,
        *keys: str,
        name: str = None,
        default: Any = None,
    ) -> Any:
        node = self._resolved

        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            elif isinstance(node, list):
                # Ako je lista, pokusaj flatten traversal
                found = None
                for item in node:
                    if isinstance(item, dict) and key in item:
                        found = item[key]
                        break
                node = found
            else:
                return default

            if node is None:
                return default

        # Ako je lista → filtriraj
        if isinstance(node, list):
            if name is not None:
                for item in node:
                    if isinstance(item, dict) and item.get("name") == name:
                        return item
                return default

            return node  # eksplicitno trazena lista

        if name:
            node = node.get(name, default)

        return node

    def get(
        self,
        key: str = None,
        name: str = None,
        default: Any = None,
    ) -> Any:
        """Deterministic lookup for resolved node and specific name value"""

        # Layout B (root je lista)
        if key is None:
            if isinstance(self._resolved, list) and name:
                for item in self._resolved:
                    if isinstance(item, dict) and item.get("name") == name:
                        return item
            return default

        # Layout A
        if not isinstance(self._resolved, dict):
            return default

        val = self._resolved.get(key)

        if val is None:
            return default

        if isinstance(val, list) and name:
            for item in val:
                if isinstance(item, dict) and item.get("name") == name:
                    return item
            return default

        return val

    def as_dict(self) -> dict:
        return dict(self._resolved) if isinstance(self._resolved, dict) else {}

    def config(self) -> Path:
        return self._config_file


# --------------------------------------------------------------------------- #
# endregion ConfigAdapter                                                     #
# --------------------------------------------------------------------------- #
