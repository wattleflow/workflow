# Module name: s3bucket.py
# Author: (wattleflow@outlook.com)
# Copyright: © 2022–2025 WattleFlow. All rights reserved.
# License: Apache 2 Licence

from __future__ import annotations
import logging
import os
import re
import shutil
import tempfile as tmp
from pathlib import Path
from typing import Generator, List, Optional
from urllib.parse import urlparse

from wattleflow.concrete import GenericDriverClass
from wattleflow.constants.enums import Event, FileTypes
from wattleflow.helpers import Normaliser

_DEFAULT_CACHE_DIR: str = os.environ.get(
    "WATTLEFLOW_CACHE",
    str(Path(tmp.gettempdir()).joinpath("wattleflow_cache").absolute()),
)


class S3UriParser:
    """
    Prepoznaje i parsira sve poznate oblike Amazon S3 URI-a.

    Podržani oblici:
      1. s3://bucket/key
      2. https://bucket.s3.amazonaws.com/key
      3. https://s3.amazonaws.com/bucket/key
      4. https://bucket.s3.region.amazonaws.com/key
    """

    _S3_SCHEME = re.compile(r"^s3://", re.IGNORECASE)

    _VIRTUAL_HOST = re.compile(
        r"^(?P<bucket>[a-z0-9][a-z0-9\-]{1,61}[a-z0-9])"
        r"\.s3(?:\.(?P<region>[a-z0-9\-]+))?\.amazonaws\.com$",
        re.IGNORECASE,
    )

    _PATH_STYLE = re.compile(
        r"^s3(?:\.(?P<region>[a-z0-9\-]+))?\.amazonaws\.com$",
        re.IGNORECASE,
    )

    @classmethod
    def is_s3(cls, uri: str) -> bool:
        if cls._S3_SCHEME.match(uri):
            return True
        parsed = urlparse(uri)
        if parsed.scheme in ("http", "https"):
            host = parsed.hostname or ""
            if cls._VIRTUAL_HOST.match(host) or cls._PATH_STYLE.match(host):
                return True
        return False

    @classmethod
    def parse(cls, uri: str) -> dict:
        """
        Vrati rječnik s ključevima:
          bucket, key, region (može biti None), is_file
        """
        parsed = urlparse(uri)

        if cls._S3_SCHEME.match(uri):
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            region = None
        else:
            host = parsed.hostname or ""
            path = parsed.path.lstrip("/")
            vm = cls._VIRTUAL_HOST.match(host)
            pm = cls._PATH_STYLE.match(host)

            if vm:
                bucket = vm.group("bucket")
                region = vm.group("region")
                key = path
            elif pm:
                region = pm.group("region")
                parts = path.split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            else:
                raise ValueError(f"[S3UriParser] Cannot parse S3 URI: {uri}")

        is_file = bool(key) and not key.endswith("/") and "." in Path(key).name

        return {
            "bucket": bucket,
            "key": key,
            "region": region,
            "is_file": is_file,
        }


class S3Driver(GenericDriverClass):
    """
    Driver za Amazon S3 pohrane, usklađen s GenericDriverClass interfejsom.

    Koristi PresetDecorator za konfiguraciju:
      - cache_dir           : lokalni direktorij za cache preuzetih datoteka
      - aws_access_key_id   : AWS pristupni ključ (opcionalno, fallback na env)
      - aws_secret_access_key
      - aws_session_token
      - region_name
    """

    __ALLOWED__ = [
        "cache_dir",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "region_name",
    ]

    def __init__(
        self,
        level: int = logging.NOTSET,
        handler: Optional[logging.Handler] = None,
        lazy_load: bool = False,
        **kwargs,
    ) -> None:
        GenericDriverClass.__init__(
            self,
            level=level,
            handler=handler,
            lazy_load=lazy_load,
            allowed=self.__ALLOWED__,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # GenericDriverClass — apstraktne metode
    # ------------------------------------------------------------------

    def load(self) -> None:
        """
        Inicijalizira boto3 S3 klijent i lokalni cache direktorij.
        Poziva se automatski iz GenericDriverClass.__init__ ako lazy_load=False.
        """
        # Cache direktorij — čita iz PresetDecorator ili pada na default
        cache_dir: str = getattr(self, "cache_dir", None) or _DEFAULT_CACHE_DIR
        self._resolved_cache_dir = Path(cache_dir)
        self._resolved_cache_dir.mkdir(parents=True, exist_ok=True)

        # Boto3 kredencijali — čita iz PresetDecorator ili pada na env varijable
        key_id = getattr(self, "aws_access_key_id", None) or os.getenv(
            "AWS_ACCESS_KEY_ID"
        )
        secret = getattr(self, "aws_secret_access_key", None) or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        token = getattr(self, "aws_session_token", None) or os.getenv(
            "AWS_SESSION_TOKEN"
        )
        region = getattr(self, "region_name", None) or os.getenv(
            "AWS_DEFAULT_REGION", "us-east-1"
        )

        # Spremi za _client() koji može dobiti override regije
        self._default_region: str = region
        self._key_id: Optional[str] = key_id
        self._secret: Optional[str] = secret
        self._token: Optional[str] = token
        self._s3_clients: dict = {}  # cache klijenata po regiji

        self.debug(
            msg=Event.Initialised.value,
            driver="S3Driver",
            cache_dir=str(self._resolved_cache_dir),
            region=region,
        )

    def read(self, identifier: str, **kwargs) -> str:
        """
        Preuzima datoteku s S3 u lokalni cache i vraća lokalni path (file URI).

        Args:
            identifier: S3 URI (s3://bucket/key ili HTTPS oblici)

        Returns:
            str — lokalni file:// URI preuzete datoteke

        Raises:
            IsADirectoryError: ako URI upućuje na prefiks, ne datoteku
            RuntimeError: ako preuzimanje ne uspije
        """
        self.debug(
            msg=Event.Read.value, step=Event.Started.value, identifier=identifier
        )

        info = S3UriParser.parse(identifier)

        if not info["is_file"]:
            raise IsADirectoryError(
                f"[S3Driver] URI upućuje na prefiks/direktorij, ne datoteku: "
                f"bucket={info['bucket']!r}, key={info['key']!r}."
            )

        bucket = info["bucket"]
        key = info["key"]
        filename = Path(key).name
        local_path = self._cache_filename(identifier, filename)

        if not local_path.exists():
            try:
                self._client(info["region"]).download_file(bucket, key, str(local_path))
                self.debug(
                    msg=Event.Read.value,
                    step=Event.Completed.value,
                    local_path=str(local_path),
                )
            except Exception as e:
                local_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"[S3Driver] Download failed: s3://{bucket}/{key} — {e}"
                ) from e
        else:
            self.info(
                msg=Event.Read.value,
                step="cache_hit",
                local=str(local_path),
            )

        return self._to_file_uri(local_path)

    def write(self, identifier: str, ftype, data: object, **kwargs) -> str:
        """
        Piše datoteku na S3. Usklađen potpis s LocalFileSystemDriver.write().

        Args:
            identifier  : destination S3 URI (s3://bucket/key)
            ftype       : FileTypes enum — određuje format serijalizacije
            data        : sadržaj za pisanje (str, DataFrame, Graph, ...)
            **kwargs    : proslijeđuju se metodama serijalizacije

        Returns:
            str — S3 URI uspješno uploadane datoteke

        Raises:
            FileNotFoundError: ako privremena datoteka ne postoji
            RuntimeError: ako upload ne uspije
        """
        self.debug(
            msg=Event.Write.value,
            step=Event.Started.value,
            identifier=identifier,
            ftype=ftype,
        )

        # Serijaliziraj u privremenu datoteku, zatim upload
        with tmp.NamedTemporaryFile(
            delete=False, suffix=Path(identifier).suffix or ".tmp"
        ) as tf:
            tmp_path = Path(tf.name)

        try:
            self._serialise(tmp_path, ftype, data, **kwargs)
            result_uri = self._upload(tmp_path, identifier)
        finally:
            tmp_path.unlink(missing_ok=True)

        self.debug(
            msg=Event.Write.value,
            step=Event.Completed.value,
            uri=result_uri,
        )

        return result_uri

    def search(
        self,
        pattern: str,
        uri: str,
        max_keys: int = 1000,
        case_sensitive: bool = False,
        recursive: bool = True,
    ) -> Generator[dict, None, None]:
        """
        Analogija LocalFileSystemDriver.search() za S3.

        Args:
            pattern       : substring ili glob za filtriranje po ključu
            uri           : S3 URI koji definira bucket i prefix
            max_keys      : maksimalan broj rezultata po stranici
            case_sensitive: osjetljivost na velika/mala slova
            recursive     : ako False, traži samo na prvoj razini prefiksa

        Yields:
            dict s ključevima: key, size, last_modified, uri, is_file
        """
        info = S3UriParser.parse(uri)
        bucket = info["bucket"]
        prefix = info["key"]

        self.debug(
            msg=Event.Search.value,
            step=Event.Started.value,
            bucket=bucket,
            prefix=prefix,
            pattern=pattern,
            recursive=recursive,
        )

        paginator = self._client(info["region"]).get_paginator("list_objects_v2")
        page_kwargs = dict(
            Bucket=bucket, Prefix=prefix, PaginationConfig={"MaxItems": max_keys}
        )

        if not recursive:
            page_kwargs["Delimiter"] = "/"

        for page in paginator.paginate(**page_kwargs):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                name = Path(key).name
                match = (
                    pattern.lower() in name.lower()
                    if not case_sensitive
                    else pattern in name
                )
                if pattern != "*" and not match:
                    continue
                yield {
                    "key": key,
                    "size": obj["Size"],
                    "last_modified": str(obj["LastModified"]),
                    "uri": f"s3://{bucket}/{key}",
                    "is_file": S3UriParser.parse(f"s3://{bucket}/{key}")["is_file"],
                }

        self.debug(msg=Event.Search.value, step=Event.Completed.value)

    def _client(self, region: Optional[str] = None):
        r = region or self._default_region
        if r not in self._s3_clients:
            try:
                import boto3
            except ImportError:
                raise ImportError("[S3Driver] boto3 is not installed.")

            self._s3_clients[r] = boto3.client(
                "s3",
                region_name=r,
                aws_access_key_id=self._key_id or None,
                aws_secret_access_key=self._secret or None,
                aws_session_token=self._token or None,
            )
        return self._s3_clients[r]

    def _cache_filename(self, uri: str, filename: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_\-.]", "_", uri)[:64]
        cache_subdir = self._resolved_cache_dir / safe
        cache_subdir.mkdir(parents=True, exist_ok=True)
        normalised = Normaliser.transform(filename)
        return cache_subdir / normalised

    @staticmethod
    def _to_file_uri(path: Path) -> str:
        return path.absolute().as_uri()

    def _upload(self, src: Path, destination_uri: str) -> str:
        info = S3UriParser.parse(destination_uri)
        bucket = info["bucket"]
        key = info["key"] or src.name

        s3_uri = f"s3://{bucket}/{key}"
        self.debug(msg=Event.Upload.value, source=str(src), uri=s3_uri)

        try:
            self._client(info["region"]).upload_file(str(src), bucket, key)
        except Exception as e:
            raise RuntimeError(f"[S3Driver] Upload failed: {s3_uri} — {e}") from e

        local_copy = self._cache_filename(destination_uri, src.name)
        shutil.copy2(src, local_copy)

        return s3_uri

    def _serialise(self, path: Path, ftype, data: object, **kwargs) -> None:

        if ftype == FileTypes.TEXT:
            path.write_text(str(data), encoding=kwargs.get("encoding", "utf-8"))

        elif ftype in (FileTypes.CSV, FileTypes.DATAFRAME):
            import pandas as pd

            if not isinstance(data, pd.DataFrame):
                raise TypeError(
                    f"[S3Driver] CSV/DATAFRAME requires DataFrame {type(data).__name__}"
                )
            data.to_csv(str(path), **{k: v for k, v in kwargs.items() if k != "suffix"})

        elif ftype == FileTypes.JSON:
            import pandas as pd

            if not isinstance(data, pd.DataFrame):
                raise TypeError(
                    f"[S3Driver] JSON requires DataFrame {type(data).__name__}"
                )
            data.to_json(
                str(path), **{k: v for k, v in kwargs.items() if k != "suffix"}
            )

        elif ftype == FileTypes.GRAPH:
            from rdflib import Graph as RDFGraph

            if not isinstance(data, RDFGraph):
                raise TypeError(
                    f"[S3Driver] GRAPH requires rdflib.Graph, {type(data).__name__}"
                )
            data.serialize(
                destination=str(path),
                format=kwargs.get("format", "json-ld"),
                indent=kwargs.get("indent", 2),
            )
        else:
            raise TypeError(f"[S3Driver] unknown FileType: {ftype}")

    def __repr__(self) -> str:
        cache = getattr(self, "_resolved_cache_dir", "uninitialised")
        return f"{self.__class__.__name__}:cache={cache}"
