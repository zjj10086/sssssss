#!/usr/bin/env python3
"""Detect suspected mainland-China TCP blocking and rotate EC2 public IPs.

The watcher runs on the EC2 instance itself. It probes several independent
mainland-China destinations and a small control group. A replacement is only
requested when the control group is reachable while a configurable majority of
the mainland targets fail for several consecutive rounds. IPv4 and IPv6 are
checked independently. A new IPv6 is confirmed before old IPv6 addresses are
removed.

Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import fcntl
import ipaddress
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable


# =============================================================================
# 用户配置区：填写分享 Token、确认服务端口，可选填写 Bark，然后执行 --install
# =============================================================================
SETTINGS: dict[str, Any] = {
    # 分享 Token，或带 ?sgt=... 的完整 AWS 小助理分享链接。
    "AWS_SB_SHARE_TOKEN": "https://aws.sb/#/ec2-instances?sgt=1e794c75779743338b6aa4920ef797f0",
    # 分享组不要求 API Token 时留空。
    "AWS_SB_AUTH_TOKEN": "",
    # 你的代理/Xray/HTTPS 服务对外监听端口。
    "REPLACEMENT_CHECK_PORT": 443,
    # Bark 完整地址，例如 https://api.day.app/你的Key；留空则不通知。
    "BARK_URL": "https://api.day.app/u9MeBe2wLUswZZpV5Ut6N",
    "BARK_GROUP": "AWS GFW 监控",
    "AWS_SB_API_BASE": "https://api.aws.sb",
    # 在 EC2 上留空即可通过 IMDSv2 自动识别。
    "AWS_INSTANCE_ID": "",
    "AWS_REGION": "",
    "CHINA_TCP_TARGETS": (
        "sx-cu-v4.ip.zstaticcdn.com:80,"
        "sx-cm-v4.ip.zstaticcdn.com:80,"
        "sx-ct-v4.ip.zstaticcdn.com:80"
    ),
    "CONTROL_TCP_TARGETS": "api.aws.sb:443,1.1.1.1:443",
    "CHINA_TCP_TARGETS_V6": (
        "sx-cu-v6.ip.zstaticcdn.com:80,"
        "sx-cm-v6.ip.zstaticcdn.com:80,"
        "sx-ct-v6.ip.zstaticcdn.com:80"
    ),
    "CONTROL_TCP_TARGETS_V6": (
        "api.aws.sb:443,[2606:4700:4700::1111]:443"
    ),
    "MIN_CONTROL_SUCCESS": 1,
    "TCP_TIMEOUT_SECONDS": 3,
    "TCP_ATTEMPTS": 2,
    "CHECK_INTERVAL_SECONDS": 120,
    "FAILURE_RATIO": 0.67,
    # 连续失败超过 9 轮，即第 10 轮触发换 IP。
    "FAILURE_CYCLES": 10,
    "REPLACE_COOLDOWN_SECONDS": 300,
    "POST_REPLACE_GRACE_SECONDS": 90,
    "POST_IPV6_REPLACE_GRACE_SECONDS": 180,
    "IPV4_UPDATE_WAIT_SECONDS": 60,
    "MAX_REPLACEMENTS_PER_HOUR": 3,
    "API_TIMEOUT_SECONDS": 30,
    "STATE_FILE": "/var/lib/aws-gfw-watch/state.json",
    "LOCK_FILE": "/run/aws-gfw-watch/aws-gfw-watch.lock",
}

IMDS_BASE = "http://169.254.169.254/latest"
IMDS_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
INSTALL_SCRIPT = Path("/root/1.py")
SYSTEMD_UNIT_PATH = Path("/etc/systemd/system/aws-gfw-watch.service")
SYSTEMD_UNIT = """[Unit]
Description=AWS GFW TCP probe and IP rotation watcher
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=root
ExecStart=/root/1.py
Restart=always
RestartSec=10
StateDirectory=aws-gfw-watch
RuntimeDirectory=aws-gfw-watch
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX

[Install]
WantedBy=multi-user.target
"""


class ConfigurationError(ValueError):
    """Raised when an environment setting is invalid."""


class ApiError(RuntimeError):
    """Raised for an explicit non-success response from aws.sb."""


class AmbiguousApiError(RuntimeError):
    """The replacement request may have succeeded before the connection dropped."""


@dataclasses.dataclass(frozen=True)
class Target:
    host: str
    port: int

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}"


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    target: Target
    ok: bool
    elapsed_ms: int
    error: str = ""


@dataclasses.dataclass(frozen=True)
class RoundDecision:
    suspected_blocked: bool
    control_healthy: bool
    china_failures: int
    required_china_failures: int
    control_successes: int


@dataclasses.dataclass
class WatchState:
    consecutive_failures: int = 0
    replacement_times: list[float] = dataclasses.field(default_factory=list)
    consecutive_failures_v6: int = 0
    replacement_times_v6: list[float] = dataclasses.field(default_factory=list)
    pending_ipv6_cleanup: dict[str, Any] = dataclasses.field(default_factory=dict)
    pending_ipv4_notification: dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def load(cls, path: Path, now: float) -> "WatchState":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            replacement_times = [
                float(item)
                for item in payload.get("replacement_times", [])
                if 0 <= now - float(item) <= 86400
            ]
            replacement_times_v6 = [
                float(item)
                for item in payload.get("replacement_times_v6", [])
                if 0 <= now - float(item) <= 86400
            ]
            return cls(
                consecutive_failures=max(0, int(payload.get("consecutive_failures", 0))),
                replacement_times=replacement_times,
                consecutive_failures_v6=max(
                    0, int(payload.get("consecutive_failures_v6", 0))
                ),
                replacement_times_v6=replacement_times_v6,
                pending_ipv6_cleanup=(
                    payload.get("pending_ipv6_cleanup", {})
                    if isinstance(payload.get("pending_ipv6_cleanup"), dict)
                    else {}
                ),
                pending_ipv4_notification=(
                    payload.get("pending_ipv4_notification", {})
                    if isinstance(payload.get("pending_ipv4_notification"), dict)
                    else {}
                ),
            )
        except (FileNotFoundError, PermissionError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "consecutive_failures": self.consecutive_failures,
            "replacement_times": self.replacement_times,
            "consecutive_failures_v6": self.consecutive_failures_v6,
            "replacement_times_v6": self.replacement_times_v6,
            "pending_ipv6_cleanup": self.pending_ipv6_cleanup,
            "pending_ipv4_notification": self.pending_ipv4_notification,
        }
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, separators=(",", ":"))
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


@dataclasses.dataclass(frozen=True)
class Config:
    api_base: str
    share_token: str
    auth_token: str
    instance_id: str
    region: str
    china_targets: tuple[Target, ...]
    control_targets: tuple[Target, ...]
    china_targets_v6: tuple[Target, ...]
    control_targets_v6: tuple[Target, ...]
    tcp_timeout: float
    tcp_attempts: int
    interval_seconds: float
    failure_ratio: float
    failure_cycles: int
    min_control_success: int
    cooldown_seconds: float
    post_replace_grace_seconds: float
    post_ipv6_replace_grace_seconds: float
    ipv4_update_wait_seconds: float
    max_replacements_per_hour: int
    api_timeout: float
    replacement_check_port: int | None
    state_file: Path
    bark_url: str = ""
    bark_group: str = "AWS GFW 监控"

    @classmethod
    def from_environment(cls) -> "Config":
        share_token = extract_share_token(setting("AWS_SB_SHARE_TOKEN"))
        if not share_token:
            raise ConfigurationError(
                "请先在脚本顶部 SETTINGS 中填写 AWS_SB_SHARE_TOKEN"
            )

        china_targets = parse_targets(setting("CHINA_TCP_TARGETS"))
        control_targets = parse_targets(setting("CONTROL_TCP_TARGETS"))
        china_targets_v6 = parse_targets(setting("CHINA_TCP_TARGETS_V6"))
        control_targets_v6 = parse_targets(setting("CONTROL_TCP_TARGETS_V6"))
        if not china_targets:
            raise ConfigurationError("CHINA_TCP_TARGETS 至少需要一个目标")
        if not control_targets:
            raise ConfigurationError("CONTROL_TCP_TARGETS 至少需要一个目标")
        if not china_targets_v6:
            raise ConfigurationError("CHINA_TCP_TARGETS_V6 至少需要一个目标")
        if not control_targets_v6:
            raise ConfigurationError("CONTROL_TCP_TARGETS_V6 至少需要一个目标")

        failure_ratio = env_float("FAILURE_RATIO", 0.67, minimum=0.01, maximum=1)
        min_control_success = env_int(
            "MIN_CONTROL_SUCCESS", 1, minimum=1, maximum=len(control_targets)
        )
        check_port_text = setting("REPLACEMENT_CHECK_PORT")
        replacement_check_port = (
            parse_port(check_port_text, "REPLACEMENT_CHECK_PORT") if check_port_text else None
        )
        return cls(
            api_base=setting("AWS_SB_API_BASE").strip().rstrip("/"),
            share_token=share_token,
            auth_token=setting("AWS_SB_AUTH_TOKEN").strip(),
            instance_id=setting("AWS_INSTANCE_ID").strip(),
            region=setting("AWS_REGION").strip(),
            china_targets=china_targets,
            control_targets=control_targets,
            china_targets_v6=china_targets_v6,
            control_targets_v6=control_targets_v6,
            tcp_timeout=env_float("TCP_TIMEOUT_SECONDS", 3, minimum=0.2, maximum=30),
            tcp_attempts=env_int("TCP_ATTEMPTS", 2, minimum=1, maximum=10),
            interval_seconds=env_float("CHECK_INTERVAL_SECONDS", 60, minimum=5),
            failure_ratio=failure_ratio,
            failure_cycles=env_int("FAILURE_CYCLES", 3, minimum=1, maximum=100),
            min_control_success=min_control_success,
            cooldown_seconds=env_float("REPLACE_COOLDOWN_SECONDS", 300, minimum=30),
            post_replace_grace_seconds=env_float(
                "POST_REPLACE_GRACE_SECONDS", 90, minimum=10
            ),
            post_ipv6_replace_grace_seconds=env_float(
                "POST_IPV6_REPLACE_GRACE_SECONDS", 180, minimum=30
            ),
            ipv4_update_wait_seconds=env_float(
                "IPV4_UPDATE_WAIT_SECONDS", 60, minimum=10, maximum=300
            ),
            max_replacements_per_hour=env_int(
                "MAX_REPLACEMENTS_PER_HOUR", 3, minimum=1, maximum=20
            ),
            api_timeout=env_float("API_TIMEOUT_SECONDS", 30, minimum=2, maximum=120),
            replacement_check_port=replacement_check_port,
            state_file=Path(setting("STATE_FILE")).expanduser(),
            bark_url=normalize_bark_url(setting("BARK_URL")),
            bark_group=setting("BARK_GROUP", "AWS GFW 监控"),
        )


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %z")
    print(f"[{timestamp}] {message}", flush=True)


def setting(name: str, default: Any = "") -> str:
    if name in os.environ:
        return os.environ[name].strip()
    return str(SETTINGS.get(name, default)).strip()


def env_float(
    name: str, default: float, *, minimum: float | None = None, maximum: float | None = None
) -> float:
    raw = setting(name, default)
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} 必须是数字") from error
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} 不能小于 {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} 不能大于 {maximum}")
    return value


def env_int(
    name: str, default: int, *, minimum: int | None = None, maximum: int | None = None
) -> int:
    raw = setting(name, default)
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} 必须是整数") from error
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} 不能小于 {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{name} 不能大于 {maximum}")
    return value


def parse_port(value: str, label: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{label} 的端口无效：{value}") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"{label} 的端口必须在 1-65535 之间")
    return port


def parse_target(value: str) -> Target:
    raw = value.strip()
    if not raw:
        raise ConfigurationError("TCP 目标不能为空")
    if raw.startswith("["):
        closing = raw.find("]")
        if closing < 1 or closing + 2 > len(raw) or raw[closing + 1] != ":":
            raise ConfigurationError(f"IPv6 TCP 目标格式无效：{raw}")
        host, port_text = raw[1:closing], raw[closing + 2 :]
    else:
        if ":" not in raw:
            raise ConfigurationError(f"TCP 目标缺少端口：{raw}")
        host, port_text = raw.rsplit(":", 1)
    host = host.strip()
    if not host:
        raise ConfigurationError(f"TCP 目标缺少主机名：{raw}")
    return Target(host=host, port=parse_port(port_text, raw))


def parse_targets(value: str) -> tuple[Target, ...]:
    return tuple(parse_target(item) for item in value.split(",") if item.strip())


def extract_share_token(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw)
        if parsed.scheme and parsed.netloc:
            query = urllib.parse.parse_qs(parsed.query)
            fragment_query = parsed.fragment.split("?", 1)[1] if "?" in parsed.fragment else ""
            fragment = urllib.parse.parse_qs(fragment_query)
            return (query.get("sgt") or fragment.get("sgt") or [raw])[0]
    except ValueError:
        pass
    return raw


def normalize_bark_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as error:
        raise ConfigurationError("BARK_URL 格式不正确") from error
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError("BARK_URL 必须是 http:// 或 https:// 完整地址")
    if not parsed.path.strip("/"):
        raise ConfigurationError("BARK_URL 缺少 Bark Key")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
    )


def _connect(target: Target, timeout: float, ip_version: int) -> tuple[bool, str]:
    family = socket.AF_INET6 if ip_version == 6 else socket.AF_INET
    try:
        addresses = socket.getaddrinfo(
            target.host, target.port, family, socket.SOCK_STREAM
        )
    except OSError as error:
        return False, f"DNS: {error}"
    last_error = f"没有 IPv{ip_version} 解析"
    for family, sock_type, protocol, _, address in addresses:
        try:
            sock = socket.socket(family, sock_type, protocol)
        except OSError as error:
            last_error = str(error)
            continue
        sock.settimeout(timeout)
        try:
            sock.connect(address)
            return True, ""
        except OSError as error:
            last_error = str(error)
        finally:
            sock.close()
    return False, last_error


def probe_target(
    target: Target, timeout: float, attempts: int, ip_version: int = 4
) -> ProbeResult:
    started = time.monotonic()
    last_error = ""
    for attempt in range(attempts):
        ok, last_error = _connect(target, timeout, ip_version)
        if ok:
            return ProbeResult(
                target=target,
                ok=True,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        if attempt + 1 < attempts:
            time.sleep(0.25)
    return ProbeResult(
        target=target,
        ok=False,
        elapsed_ms=round((time.monotonic() - started) * 1000),
        error=last_error[:160],
    )


def probe_targets(
    targets: Iterable[Target], timeout: float, attempts: int, ip_version: int = 4
) -> list[ProbeResult]:
    target_list = list(targets)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(target_list)) as executor:
        futures = [
            executor.submit(probe_target, target, timeout, attempts, ip_version)
            for target in target_list
        ]
        return [future.result() for future in futures]


def decide_round(
    china_results: list[ProbeResult],
    control_results: list[ProbeResult],
    failure_ratio: float,
    min_control_success: int,
) -> RoundDecision:
    china_failures = sum(not item.ok for item in china_results)
    required = max(1, math.ceil(len(china_results) * failure_ratio))
    control_successes = sum(item.ok for item in control_results)
    control_healthy = control_successes >= min_control_success
    return RoundDecision(
        suspected_blocked=control_healthy and china_failures >= required,
        control_healthy=control_healthy,
        china_failures=china_failures,
        required_china_failures=required,
        control_successes=control_successes,
    )


def imds_get(path: str, timeout: float = 1.5) -> str:
    token_request = urllib.request.Request(
        f"{IMDS_BASE}/api/token",
        method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
    )
    try:
        with IMDS_OPENER.open(token_request, timeout=timeout) as response:
            token = response.read().decode("utf-8")
        request = urllib.request.Request(
            f"{IMDS_BASE}/{path.lstrip('/')}",
            headers={"X-aws-ec2-metadata-token": token},
        )
        with IMDS_OPENER.open(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as error:
        raise ConfigurationError(f"无法从 EC2 IMDSv2 读取 {path}：{error}") from error


def resolve_instance_identity(config: Config) -> tuple[str, str]:
    metadata_instance_id = ""
    metadata_region = ""
    metadata_errors = []
    try:
        metadata_instance_id = imds_get("meta-data/instance-id").strip()
    except ConfigurationError as error:
        metadata_errors.append(str(error))
    try:
        document = json.loads(imds_get("dynamic/instance-identity/document"))
        metadata_region = str(document.get("region", "")).strip()
    except (ConfigurationError, json.JSONDecodeError) as error:
        metadata_errors.append(str(error))

    if (
        config.instance_id
        and metadata_instance_id
        and config.instance_id != metadata_instance_id
    ):
        raise ConfigurationError(
            f"安全校验失败：配置实例 {config.instance_id} 与本机 IMDS "
            f"实例 {metadata_instance_id} 不一致"
        )
    if config.region and metadata_region and config.region != metadata_region:
        raise ConfigurationError(
            f"安全校验失败：配置区域 {config.region} 与本机 IMDS "
            f"区域 {metadata_region} 不一致"
        )

    instance_id = metadata_instance_id or config.instance_id
    region = metadata_region or config.region
    if not instance_id or not region:
        details = f"；{'；'.join(metadata_errors)}" if metadata_errors else ""
        raise ConfigurationError(
            f"AWS_INSTANCE_ID 或 AWS_REGION 无法自动识别{details}"
        )
    return instance_id, region


class AwsSbClient:
    def __init__(
        self,
        config: Config,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.config = config
        self.opener = opener

    def _headers(self, region: str = "") -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "aws-gfw-watch/1.1",
            "X-Share-Group-Token": self.config.share_token,
        }
        if self.config.auth_token:
            headers["X-Auth-Token"] = self.config.auth_token
        if region:
            headers["X-Region-Name"] = region
        return headers

    def verify_target(self, instance_id: str, region: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.config.api_base}/ec2-instance-shares",
            headers=self._headers(),
        )
        try:
            with self.opener(request, timeout=self.config.api_timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                shares = json.loads(raw)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")[:500]
            raise ApiError(
                f"换 IP 安全校验失败，aws.sb 返回 HTTP {error.code}：{body}"
            ) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            raise ApiError(f"换 IP 安全校验无法读取分享组：{error}") from error
        except json.JSONDecodeError as error:
            raise ApiError("换 IP 安全校验失败：分享组清单不是有效 JSON") from error

        if not isinstance(shares, list):
            raise ApiError("换 IP 安全校验失败：分享组清单格式不正确")
        matches = []
        same_instance_regions = []
        for share in shares:
            if not isinstance(share, dict):
                continue
            share_instance_id = str(
                share.get("instanceId") or share.get("instance_id") or ""
            ).strip()
            share_region = str(
                share.get("regionName") or share.get("region_name") or ""
            ).strip()
            if share_instance_id == instance_id:
                same_instance_regions.append(share_region or "未知")
                if share_region == region:
                    matches.append(share)
        if len(matches) != 1:
            regions = ",".join(same_instance_regions) or "无匹配实例"
            raise ApiError(
                "换 IP 安全校验失败：分享组内必须且只能有一台机器同时精确匹配 "
                f"实例 {instance_id} 和区域 {region}（同实例 ID 区域：{regions}）"
            )
        log(f"换 IP 安全校验通过：唯一匹配 {instance_id} / {region}")
        return matches[0]

    def get_instance(self, instance_id: str, region: str) -> dict[str, Any]:
        path_id = urllib.parse.quote(instance_id, safe="")
        request = urllib.request.Request(
            f"{self.config.api_base}/ec2-instances/{path_id}",
            headers=self._headers(region),
        )
        try:
            with self.opener(request, timeout=self.config.api_timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                result = json.loads(raw)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")[:500]
            raise ApiError(
                f"读取实例详情失败，aws.sb 返回 HTTP {error.code}：{body}"
            ) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            raise ApiError(f"读取实例详情失败：{error}") from error
        except json.JSONDecodeError as error:
            raise ApiError("读取实例详情失败：返回内容不是有效 JSON") from error
        if not isinstance(result, dict):
            raise ApiError("读取实例详情失败：返回格式不正确")
        return result

    def change_ipv4(self, instance_id: str, region: str) -> Any:
        self.verify_target(instance_id, region)
        path_id = urllib.parse.quote(instance_id, safe="")
        url = f"{self.config.api_base}/ec2-instances/{path_id}/ip-address"
        payload: dict[str, Any] = {"gfw_blocked_check": True}
        if self.config.replacement_check_port is not None:
            payload["gfw_blocked_check_port"] = self.config.replacement_check_port
        headers = {**self._headers(region), "Content-Type": "application/json"}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="PATCH",
            headers=headers,
        )
        try:
            with self.opener(request, timeout=self.config.api_timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return {"ok": True}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"ok": True, "response": raw[:500]}
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")[:500]
            raise ApiError(f"aws.sb 返回 HTTP {error.code}：{body}") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            raise AmbiguousApiError(
                f"换 IP 请求后连接中断，IP 可能已经更换：{error}"
            ) from error

    def cleanup_ipv6_addresses(
        self,
        instance_id: str,
        region: str,
        old_addresses: Iterable[str],
        new_address: str,
    ) -> dict[str, Any]:
        self.verify_target(instance_id, region)
        requested = unique_ipv6_addresses((list(old_addresses),))
        current = unique_ipv6_addresses((self.get_instance(instance_id, region),))
        if new_address not in current:
            return {
                "requested": requested,
                "removed": [],
                "remaining": [address for address in requested if address in current],
                "error": (
                    f"安全保护：当前实例无法确认新 IPv6 {new_address}，"
                    "因此没有删除任何旧 IPv6"
                ),
            }

        remaining = [address for address in requested if address in current]
        cleanup: dict[str, Any] = {
            "requested": requested,
            "removed": [
                address for address in requested if address not in remaining
            ],
            "remaining": remaining,
            "attempts": 0,
        }
        if not remaining:
            return cleanup

        path_id = urllib.parse.quote(instance_id, safe="")
        address_url = (
            f"{self.config.api_base}/ec2-instances/{path_id}/ipv6/addresses"
        )
        for attempt in range(1, 4):
            cleanup["attempts"] = attempt
            query = urllib.parse.urlencode(
                [("address", address) for address in remaining]
            )
            delete_request = urllib.request.Request(
                f"{address_url}?{query}",
                method="DELETE",
                headers=self._headers(region),
            )
            try:
                with self.opener(
                    delete_request, timeout=self.config.api_timeout
                ) as response:
                    response.read()
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")[:500]
                cleanup["error"] = (
                    f"删除旧 IPv6 返回 HTTP {error.code}：{body}"
                )
                break
            except (
                urllib.error.URLError,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as error:
                cleanup["error"] = f"删除旧 IPv6 时连接中断，请确认清理结果：{error}"
                cleanup["ambiguous"] = True
                break

            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    latest = unique_ipv6_addresses(
                        (self.get_instance(instance_id, region),)
                    )
                except ApiError:
                    time.sleep(3)
                    continue
                if new_address not in latest:
                    cleanup["error"] = (
                        f"安全保护：删除过程中无法确认新 IPv6 {new_address}"
                    )
                    return cleanup
                remaining = [
                    address for address in requested if address in latest
                ]
                cleanup["remaining"] = remaining
                cleanup["removed"] = [
                    address for address in requested if address not in remaining
                ]
                if not remaining:
                    cleanup.pop("error", None)
                    return cleanup
                time.sleep(3)
        return cleanup

    def change_ipv6(
        self,
        instance_id: str,
        region: str,
        before_cleanup: Callable[[list[str], str], None] | None = None,
    ) -> dict[str, Any]:
        share = self.verify_target(instance_id, region)
        detail = self.get_instance(instance_id, region)
        old_addresses = unique_ipv6_addresses((share, detail))
        if not old_addresses:
            raise ApiError("当前实例没有可替换的 IPv6 地址")

        path_id = urllib.parse.quote(instance_id, safe="")
        address_url = (
            f"{self.config.api_base}/ec2-instances/{path_id}/ipv6/addresses"
        )
        assign_request = urllib.request.Request(
            address_url,
            data=b"",
            method="PUT",
            headers={**self._headers(region), "Content-Type": "application/json"},
        )
        try:
            with self.opener(
                assign_request, timeout=self.config.api_timeout
            ) as response:
                raw = response.read().decode("utf-8", errors="replace")
                assigned = json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")[:500]
            raise ApiError(
                f"分配新 IPv6 失败，aws.sb 返回 HTTP {error.code}：{body}"
            ) from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            raise AmbiguousApiError(
                f"分配新 IPv6 时连接中断，可能已经分配成功；旧 IPv6 未删除：{error}"
            ) from error
        except json.JSONDecodeError:
            assigned = {}

        new_candidates = [
            address
            for address in unique_ipv6_addresses((assigned,))
            if address not in old_addresses
        ]
        new_address = new_candidates[0] if new_candidates else ""
        deadline = time.monotonic() + 45
        while not new_address and time.monotonic() < deadline:
            time.sleep(2.5)
            try:
                latest = self.get_instance(instance_id, region)
            except ApiError:
                continue
            new_address = next(
                (
                    address
                    for address in unique_ipv6_addresses((latest,))
                    if address not in old_addresses
                ),
                "",
            )
        if not new_address:
            raise AmbiguousApiError(
                "新 IPv6 可能已经分配，但 45 秒内无法确认；为保护连通性，旧 IPv6 未删除"
            )

        old_to_delete = [
            address for address in old_addresses if address != new_address
        ]
        if before_cleanup:
            before_cleanup(old_to_delete, new_address)
        try:
            cleanup = self.cleanup_ipv6_addresses(
                instance_id,
                region,
                old_to_delete,
                new_address,
            )
        except ApiError as error:
            cleanup = {
                "requested": old_to_delete,
                "removed": [],
                "remaining": old_to_delete,
                "error": str(error),
            }

        return {
            "oldPublicIpv6": old_addresses[0],
            "oldIpv6Addresses": old_addresses,
            "newPublicIpv6": new_address,
            "assigned": assigned,
            "cleanup": cleanup,
        }


def send_bark(config: Config, title: str, body: str) -> bool:
    if not config.bark_url:
        return False
    path = (
        f"{config.bark_url}/"
        f"{urllib.parse.quote(title, safe='')}/"
        f"{urllib.parse.quote(body, safe='')}"
    )
    query = urllib.parse.urlencode({"group": config.bark_group})
    request = urllib.request.Request(
        f"{path}?{query}",
        headers={"Accept": "application/json", "User-Agent": "aws-gfw-watch/1.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=config.api_timeout) as response:
            response.read()
            return 200 <= int(response.status) < 300
    except urllib.error.HTTPError as error:
        body_text = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Bark 返回 HTTP {error.code}：{body_text}") from error
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
        raise RuntimeError(f"Bark 发送失败：{error}") from error


def ipv4_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    preferred_keys = (
        "publicIpAddress",
        "public_ip_address",
        "publicIp",
        "public_ip",
        "publicIpv4",
        "public_ipv4",
        "ipAddress",
        "ip_address",
    )
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, str):
            try:
                socket.inet_aton(value)
                return value
            except OSError:
                pass
    for value in payload.values():
        if isinstance(value, dict):
            found = ipv4_from_payload(value)
            if found:
                return found
    return ""


def unique_ipv6_addresses(payloads: Iterable[Any]) -> list[str]:
    addresses: list[str] = []
    seen_objects: set[int] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            try:
                address = ipaddress.ip_address(value.strip())
            except ValueError:
                return
            if address.version == 6:
                normalized = str(address)
                if normalized not in addresses:
                    addresses.append(normalized)
            return
        if not isinstance(value, (dict, list, tuple)) or id(value) in seen_objects:
            return
        seen_objects.add(id(value))
        items = value.values() if isinstance(value, dict) else value
        for item in items:
            visit(item)

    for payload in payloads:
        visit(payload)
    return addresses


def result_line(result: ProbeResult) -> str:
    if result.ok:
        return f"{result.target.label}=OK({result.elapsed_ms}ms)"
    return f"{result.target.label}=FAIL({result.error or 'timeout'})"


class Watcher:
    def __init__(
        self,
        config: Config,
        *,
        dry_run: bool = False,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.dry_run = dry_run
        self.clock = clock
        self.stop_event = threading.Event()
        self.state = WatchState.load(config.state_file, clock())
        self.client = AwsSbClient(config)
        self.instance_id = ""
        self.region = ""
        self.last_replacement_type = ""

    def stop(self, *_: Any) -> None:
        self.stop_event.set()

    def initialize(self) -> None:
        self.instance_id, self.region = resolve_instance_identity(self.config)
        log(
            f"监控实例 {self.instance_id} / {self.region}，"
            f"IPv4/IPv6 国内目标各 {len(self.config.china_targets)} / "
            f"{len(self.config.china_targets_v6)} 个"
        )

    def _notify_bark(self, title: str, body: str) -> bool:
        if not self.config.bark_url:
            return False
        try:
            if send_bark(self.config, title, body):
                log(f"Bark 已发送：{title}")
                return True
            else:
                log(f"Bark 未发送：{title}")
                return False
        except RuntimeError as error:
            log(str(error))
            return False

    def _replacement_times(self, address_type: str) -> list[float]:
        return (
            self.state.replacement_times_v6
            if address_type == "ipv6"
            else self.state.replacement_times
        )

    def _set_replacement_times(
        self, address_type: str, values: list[float]
    ) -> None:
        if address_type == "ipv6":
            self.state.replacement_times_v6 = values
        else:
            self.state.replacement_times = values

    def _failure_count(self, address_type: str) -> int:
        return (
            self.state.consecutive_failures_v6
            if address_type == "ipv6"
            else self.state.consecutive_failures
        )

    def _set_failure_count(self, address_type: str, value: int) -> None:
        if address_type == "ipv6":
            self.state.consecutive_failures_v6 = value
        else:
            self.state.consecutive_failures = value

    def _prune_replacements(self, address_type: str, now: float) -> list[float]:
        values = [
            item
            for item in self._replacement_times(address_type)
            if 0 <= now - item < 3600
        ]
        self._set_replacement_times(address_type, values)
        return values

    def _save_state(self) -> None:
        self.state.save(self.config.state_file)

    def _record_pending_ipv4_notification(self, old_address: str) -> None:
        self.state.pending_ipv4_notification = {
            "instanceId": self.instance_id,
            "region": self.region,
            "oldAddress": old_address,
            "time": self.clock(),
        }
        self._save_state()

    @staticmethod
    def _changed_ipv4(candidate: str, old_address: str) -> str:
        try:
            address = ipaddress.ip_address(candidate.strip())
        except ValueError:
            return ""
        if address.version != 4:
            return ""
        normalized = str(address)
        if normalized == old_address.strip():
            return ""
        return normalized

    def _find_new_ipv4(
        self, old_address: str, response_payload: Any = None
    ) -> str:
        response_address = ipv4_from_payload(response_payload)
        if response_address:
            # The replacement endpoint's returned address is authoritative,
            # including when the old address could not be read beforehand.
            changed = self._changed_ipv4(response_address, old_address)
            if changed or old_address == "未知":
                return response_address

        try:
            metadata_address = imds_get("meta-data/public-ipv4").strip()
        except ConfigurationError:
            metadata_address = ""
        changed = self._changed_ipv4(metadata_address, old_address)
        if changed:
            return changed

        try:
            instance = self.client.get_instance(self.instance_id, self.region)
        except ApiError:
            return ""
        return self._changed_ipv4(ipv4_from_payload(instance), old_address)

    def _finish_pending_ipv4_notification(self, new_address: str) -> bool:
        pending = self.state.pending_ipv4_notification
        if not pending:
            return False
        old_address = str(pending.get("oldAddress") or "未知").strip()
        body = (
            f"实例：{pending.get('instanceId') or self.instance_id}\n"
            f"区域：{pending.get('region') or self.region}\n"
            f"原 IPv4：{old_address}\n"
            f"新 IPv4：{new_address}"
        )
        if self.config.bark_url and not self._notify_bark("AWS IPv4 已更换", body):
            log(f"新 IPv4 已确认：{new_address}；Bark 发送失败，下轮重试")
            return False
        self.state.pending_ipv4_notification = {}
        self._save_state()
        if not self.config.bark_url:
            log(f"新 IPv4 已确认：{new_address}")
        return True

    def _wait_and_notify_new_ipv4(
        self, old_address: str, response_payload: Any
    ) -> bool:
        deadline = time.monotonic() + self.config.ipv4_update_wait_seconds
        while not self.stop_event.is_set():
            new_address = self._find_new_ipv4(old_address, response_payload)
            response_payload = None
            if new_address:
                return self._finish_pending_ipv4_notification(new_address)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self.stop_event.wait(min(5, remaining))
        log(
            "AWS 暂未返回新的 IPv4，已保存待通知任务；"
            "下一轮确认新地址后再发送 Bark"
        )
        return False

    def _resume_pending_ipv4_notification(self) -> bool:
        pending = self.state.pending_ipv4_notification
        if not pending:
            return False
        old_address = str(pending.get("oldAddress") or "未知").strip()
        if old_address == "未知":
            log("待通知任务缺少原 IPv4，无法安全确认地址已变化")
            return True
        new_address = self._find_new_ipv4(old_address)
        if not new_address:
            log(f"新 IPv4 尚未确认（原地址 {old_address}），下轮继续检查")
            return True
        self._finish_pending_ipv4_notification(new_address)
        return True

    def _record_pending_ipv6_cleanup(
        self, old_addresses: list[str], new_address: str
    ) -> None:
        self.state.pending_ipv6_cleanup = {
            "instanceId": self.instance_id,
            "region": self.region,
            "oldAddresses": old_addresses,
            "newAddress": new_address,
            "time": self.clock(),
        }
        self._save_state()
        log(
            f"已持久化旧 IPv6 清理任务：{','.join(old_addresses) or '无'} "
            f"-> 保留 {new_address}"
        )

    def _resume_pending_ipv6_cleanup(self) -> bool:
        pending = self.state.pending_ipv6_cleanup
        if not pending:
            return False
        old_addresses = unique_ipv6_addresses(
            (pending.get("oldAddresses", []),)
        )
        new_address = str(pending.get("newAddress") or "").strip()
        if not old_addresses:
            self.state.pending_ipv6_cleanup = {}
            self._save_state()
            return False
        if not new_address:
            log("旧 IPv6 清理任务缺少新地址，为安全起见不执行删除")
            return True
        log(f"继续未完成的旧 IPv6 清理：{','.join(old_addresses)}")
        try:
            cleanup = self.client.cleanup_ipv6_addresses(
                self.instance_id,
                self.region,
                old_addresses,
                new_address,
            )
        except ApiError as error:
            log(f"旧 IPv6 清理暂未完成：{error}")
            return True
        remaining = cleanup.get("remaining") or []
        if remaining:
            log(
                f"旧 IPv6 清理暂未完成：{','.join(remaining)}；"
                f"{cleanup.get('error') or '等待下轮重试'}"
            )
            return True
        self.state.pending_ipv6_cleanup = {}
        self._save_state()
        log(f"旧 IPv6 已确认删除：{','.join(old_addresses)}")
        self._notify_bark(
            "AWS 旧 IPv6 已清理",
            f"实例：{self.instance_id}\n"
            f"区域：{self.region}\n"
            f"已删除：{','.join(old_addresses)}\n"
            f"保留新 IPv6：{new_address}",
        )
        return False

    def _request_replacement(self, now: float, address_type: str) -> bool:
        label = "IPv6" if address_type == "ipv6" else "IPv4"
        replacement_times = self._prune_replacements(address_type, now)
        if replacement_times:
            age = now - replacement_times[-1]
            if age < self.config.cooldown_seconds:
                log(
                    f"{label} 仍在换 IP 冷却期，剩余约 "
                    f"{math.ceil(self.config.cooldown_seconds - age)} 秒"
                )
                return False
        if len(replacement_times) >= self.config.max_replacements_per_hour:
            log(
                f"{label} 已达到每小时换 IP 上限 "
                f"{self.config.max_replacements_per_hour} 次，本轮不操作"
            )
            return False

        if self.dry_run:
            log(f"DRY RUN：{label} 满足换 IP 条件，但未调用 aws.sb")
            self._set_failure_count(address_type, 0)
            self._save_state()
            return False

        old_public_ip = "未知"
        if address_type == "ipv4":
            try:
                old_public_ip = imds_get("meta-data/public-ipv4").strip()
            except ConfigurationError:
                try:
                    old_public_ip = (
                        ipv4_from_payload(
                            self.client.get_instance(self.instance_id, self.region)
                        )
                        or "未知"
                    )
                except ApiError:
                    pass

        # Record before making the non-idempotent request. A public-IP change can
        # tear down the response connection even though the API accepted it.
        replacement_times.append(now)
        self._set_replacement_times(address_type, replacement_times)
        self._set_failure_count(address_type, 0)
        if address_type == "ipv4":
            self._record_pending_ipv4_notification(old_public_ip)
        self._save_state()
        log(f"确认疑似被墙，正在请求更换公网 {label}……")
        try:
            result = (
                self.client.change_ipv6(
                    self.instance_id,
                    self.region,
                    before_cleanup=self._record_pending_ipv6_cleanup,
                )
                if address_type == "ipv6"
                else self.client.change_ipv4(self.instance_id, self.region)
            )
            rendered = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            log(f"aws.sb 已接受换 IP 请求：{rendered[:800]}")
            if address_type == "ipv6":
                cleanup = result.get("cleanup") or {}
                cleanup_text = (
                    "旧 IPv6 已删除"
                    if not cleanup.get("remaining")
                    else f"旧 IPv6 清理未完成：{','.join(cleanup.get('remaining', []))}"
                )
                if cleanup.get("error"):
                    cleanup_text += f"\n清理错误：{cleanup['error']}"
                if not cleanup.get("remaining"):
                    self.state.pending_ipv6_cleanup = {}
                    self._save_state()
                self._notify_bark(
                    "AWS IPv6 已更换",
                    f"实例：{self.instance_id}\n"
                    f"区域：{self.region}\n"
                    f"原 IPv6：{','.join(result.get('oldIpv6Addresses', [])) or '未知'}\n"
                    f"新 IPv6：{result.get('newPublicIpv6') or '等待更新'}\n"
                    f"{cleanup_text}",
                )
            else:
                self._wait_and_notify_new_ipv4(old_public_ip, result)
        except AmbiguousApiError as error:
            log(str(error))
            self._notify_bark(
                f"AWS {label} 换 IP 结果待确认",
                f"实例：{self.instance_id}\n"
                f"区域：{self.region}\n"
                f"换 {label} 时连接中断，请在 AWS 小助理确认新地址。\n"
                f"详情：{str(error)[:300]}",
            )
        except ApiError as error:
            # Explicit HTTP failures did not change the address, so they should
            # not consume the hourly replacement allowance.
            replacement_times.pop()
            self._set_replacement_times(address_type, replacement_times)
            if address_type == "ipv4":
                self.state.pending_ipv4_notification = {}
            self._save_state()
            self._notify_bark(
                f"AWS {label} 换 IP 失败",
                f"实例：{self.instance_id}\n"
                f"区域：{self.region}\n"
                f"错误：{str(error)[:300]}",
            )
            raise
        self.last_replacement_type = address_type
        return True

    def _evaluate_family(
        self,
        address_type: str,
        china_results: list[ProbeResult],
        control_results: list[ProbeResult],
    ) -> bool:
        label = "IPv6" if address_type == "ipv6" else "IPv4"
        log(
            f"{label} 国内 TCP："
            + "；".join(result_line(item) for item in china_results)
        )
        log(
            f"{label} 控制 TCP："
            + "；".join(result_line(item) for item in control_results)
        )
        decision = decide_round(
            china_results,
            control_results,
            self.config.failure_ratio,
            self.config.min_control_success,
        )

        if not decision.control_healthy:
            self._set_failure_count(address_type, 0)
            self._save_state()
            log(
                f"{label} 控制目标仅成功 {decision.control_successes} 个，"
                f"判断为本机/上游 {label} 网络异常，不换 IP"
            )
            return False
        if not decision.suspected_blocked:
            self._set_failure_count(address_type, 0)
            self._save_state()
            log(
                f"{label} 国内失败 {decision.china_failures}/{len(china_results)}，"
                "未达到疑似被墙阈值"
            )
            return False

        failure_count = self._failure_count(address_type) + 1
        self._set_failure_count(address_type, failure_count)
        self._save_state()
        log(
            f"{label} 国内失败 {decision.china_failures}/{len(china_results)}，"
            f"连续异常 {failure_count}/{self.config.failure_cycles}"
        )
        return failure_count >= self.config.failure_cycles

    def run_round(self) -> bool:
        self._resume_pending_ipv4_notification()
        pending_ipv6_cleanup = self._resume_pending_ipv6_cleanup()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            ipv4_future = executor.submit(
                probe_targets,
                (*self.config.china_targets, *self.config.control_targets),
                self.config.tcp_timeout,
                self.config.tcp_attempts,
                4,
            )
            ipv6_future = executor.submit(
                probe_targets,
                (*self.config.china_targets_v6, *self.config.control_targets_v6),
                self.config.tcp_timeout,
                self.config.tcp_attempts,
                6,
            )
            ipv4_results = ipv4_future.result()
            ipv6_results = ipv6_future.result()

        ipv4_count = len(self.config.china_targets)
        ipv6_count = len(self.config.china_targets_v6)
        replace_ipv4 = self._evaluate_family(
            "ipv4",
            ipv4_results[:ipv4_count],
            ipv4_results[ipv4_count:],
        )
        replace_ipv6 = self._evaluate_family(
            "ipv6",
            ipv6_results[:ipv6_count],
            ipv6_results[ipv6_count:],
        )
        # Never rotate both address families in the same round. If both need
        # replacement, IPv6 remains over threshold and is handled next round.
        if replace_ipv4:
            return self._request_replacement(self.clock(), "ipv4")
        if replace_ipv6 and not pending_ipv6_cleanup:
            return self._request_replacement(self.clock(), "ipv6")
        if replace_ipv6:
            log("仍有旧 IPv6 清理任务未完成，本轮不再申请新 IPv6")
        return False

    def run(self, once: bool = False) -> None:
        self.initialize()
        while not self.stop_event.is_set():
            replaced = False
            try:
                replaced = self.run_round()
            except ApiError as error:
                log(f"换 IP 失败：{error}")
            except Exception as error:  # Keep the daemon alive after transient probe failures.
                log(f"本轮检测异常：{type(error).__name__}: {error}")
            if once:
                return
            delay = (
                (
                    self.config.post_ipv6_replace_grace_seconds
                    if self.last_replacement_type == "ipv6"
                    else self.config.post_replace_grace_seconds
                )
                if replaced
                else self.config.interval_seconds
            )
            self.stop_event.wait(delay)


def acquire_lock(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        stream.close()
        raise RuntimeError(f"已有监控进程在运行（锁文件 {path}）") from error
    return stream


def install_service() -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("--install 只能在使用 systemd 的 Linux EC2 上执行")
    if os.geteuid() != 0:
        raise RuntimeError("安装服务需要 root 权限，请使用 sudo")
    if not shutil.which("systemctl"):
        raise RuntimeError("没有找到 systemctl")
    if not extract_share_token(str(SETTINGS.get("AWS_SB_SHARE_TOKEN", ""))):
        raise ConfigurationError(
            "--install 使用单文件配置，请先在脚本顶部 SETTINGS 中填写 AWS_SB_SHARE_TOKEN"
        )

    # Validate the embedded settings before replacing the installed copy.
    Config.from_environment()
    source = Path(__file__).resolve()
    source.chmod(0o700)
    if source != INSTALL_SCRIPT.resolve():
        fd, temporary_name = tempfile.mkstemp(prefix=".1.py.", dir=INSTALL_SCRIPT.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            shutil.copyfile(source, temporary)
            temporary.chmod(0o700)
            os.replace(temporary, INSTALL_SCRIPT)
        finally:
            temporary.unlink(missing_ok=True)
    INSTALL_SCRIPT.chmod(0o700)
    SYSTEMD_UNIT_PATH.write_text(SYSTEMD_UNIT, encoding="utf-8")
    SYSTEMD_UNIT_PATH.chmod(0o644)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "aws-gfw-watch"], check=True)
    subprocess.run(["systemctl", "restart", "aws-gfw-watch"], check=True)
    log(f"安装完成：{INSTALL_SCRIPT}")
    log("查看日志：journalctl -u aws-gfw-watch -f")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AWS 小助理 TCP 被墙检测与自动换 IP")
    parser.add_argument("--once", action="store_true", help="只执行一轮，适合 cron")
    parser.add_argument("--dry-run", action="store_true", help="仅检测，不实际换 IP")
    parser.add_argument(
        "--install",
        action="store_true",
        help="把当前脚本安装为 systemd 服务并立即启动",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.install:
            install_service()
            return 0
        config = Config.from_environment()
        lock_file = Path(
            setting("LOCK_FILE", f"{config.state_file}.lock")
        ).expanduser()
        lock_stream = acquire_lock(lock_file)
        watcher = Watcher(config, dry_run=args.dry_run)
        signal.signal(signal.SIGTERM, watcher.stop)
        signal.signal(signal.SIGINT, watcher.stop)
        watcher.run(once=args.once)
        lock_stream.close()
        return 0
    except (ConfigurationError, RuntimeError, OSError, json.JSONDecodeError) as error:
        log(f"启动失败：{error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
