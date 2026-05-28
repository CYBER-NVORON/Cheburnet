from __future__ import annotations

import base64
import json
import urllib.parse
from typing import Iterable

from cheburnet.app.constants import FREE_CONFIG_SCHEMES
from cheburnet.app.core.downloader import get_text
from cheburnet.app.models.profile import Profile


class FreeConfigsService:
    def fetch(self, sources: Iterable[str] | None = None, limit_per_source: int = 80) -> list[Profile]:
        source_list = [str(source).strip() for source in (sources or []) if str(source).strip()]
        if not source_list:
            return []
        profiles: list[Profile] = []
        seen: set[str] = set()
        for source in source_list:
            try:
                text = get_text(source)
            except Exception:
                continue
            for profile in self.parse_text(text, source, limit=limit_per_source):
                if profile.id not in seen:
                    seen.add(profile.id)
                    profiles.append(profile)
        return profiles

    def parse_text(self, text: str, source: str = "manual", limit: int | None = None) -> list[Profile]:
        profiles: list[Profile] = []
        seen: set[str] = set()
        for link in self.extract_links(text):
            profile = self.parse_link(link, source)
            if not profile or profile.id in seen:
                continue
            seen.add(profile.id)
            profiles.append(profile)
            if limit is not None and len(profiles) >= limit:
                break
        return profiles

    def extract_links(self, text: str) -> list[str]:
        chunks = [text]
        if "://" not in text:
            decoded = self._decode_base64_text(text)
            if decoded:
                chunks.append(decoded)
        for line in text.splitlines():
            stripped = line.strip()
            if "://" in stripped or len(stripped) < 32:
                continue
            decoded = self._decode_base64_text(stripped)
            if decoded:
                chunks.append(decoded)

        links: list[str] = []
        seen: set[str] = set()
        for chunk in chunks:
            for raw in chunk.replace("\r", "\n").splitlines():
                value = raw.strip()
                if not value:
                    continue
                if not value.startswith(FREE_CONFIG_SCHEMES):
                    for scheme in FREE_CONFIG_SCHEMES:
                        index = value.find(scheme)
                        if index >= 0:
                            value = value[index:]
                            break
                if not value.startswith(FREE_CONFIG_SCHEMES):
                    continue
                value = value.split()[0].strip()
                if value and value not in seen:
                    seen.add(value)
                    links.append(value)
        return links

    def parse_link(self, link: str, source: str = "") -> Profile | None:
        link = link.strip()
        try:
            if link.startswith("vless://"):
                return self._parse_vless(link, source)
            if link.startswith("vmess://"):
                return self._parse_vmess(link, source)
            if link.startswith("trojan://"):
                return self._parse_trojan(link, source)
            if link.startswith("ss://"):
                return self._parse_shadowsocks(link, source)
            if link.startswith(("hysteria2://", "hy2://")):
                return self._parse_hysteria2(link, source)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        return None

    def _parse_vless(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        query = self._query(parts.query)
        server, port = self._server_port(parts)
        uuid = urllib.parse.unquote(parts.username or "")
        if not uuid or not server or not port:
            return None
        outbound = {"type": "vless", "server": server, "server_port": port, "uuid": uuid}
        if query.get("flow"):
            outbound["flow"] = query["flow"]
        if query.get("packetEncoding") or query.get("packet_encoding"):
            outbound["packet_encoding"] = query.get("packetEncoding") or query.get("packet_encoding")
        self._apply_tls(outbound, query, server)
        if not self._apply_transport(outbound, query):
            return None
        return self._profile(link, source, parts, "vless", server, port, outbound)

    def _parse_trojan(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        query = self._query(parts.query)
        server, port = self._server_port(parts)
        password = urllib.parse.unquote(parts.username or "")
        if not password or not server or not port:
            return None
        outbound = {"type": "trojan", "server": server, "server_port": port, "password": password}
        if query.get("security", "tls").lower() != "none":
            self._apply_tls(outbound, query, server, default_enabled=True)
        if not self._apply_transport(outbound, query):
            return None
        return self._profile(link, source, parts, "trojan", server, port, outbound)

    def _parse_hysteria2(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        query = self._query(parts.query)
        server, port = self._server_port(parts)
        password = urllib.parse.unquote(parts.username or "")
        if not password or not server or not port:
            return None
        outbound = {"type": "hysteria2", "server": server, "server_port": port, "password": password}
        self._apply_tls(outbound, query, server, default_enabled=True)
        return self._profile(link, source, parts, "hysteria2", server, port, outbound)

    def _parse_vmess(self, link: str, source: str) -> Profile | None:
        payload = self._decode_base64_text(link.removeprefix("vmess://"))
        if not payload:
            return None
        data = json.loads(payload)
        server = str(data.get("add", "")).strip()
        port = int(str(data.get("port", "0") or 0))
        uuid = str(data.get("id", "")).strip()
        if not server or not port or not uuid:
            return None
        outbound = {
            "type": "vmess",
            "server": server,
            "server_port": port,
            "uuid": uuid,
            "security": str(data.get("scy") or data.get("security") or "auto"),
            "alter_id": int(str(data.get("aid", "0") or 0)),
        }
        query = {
            "security": str(data.get("tls", "none") or "none"),
            "sni": str(data.get("sni", "") or ""),
            "type": str(data.get("net", "") or ""),
            "host": str(data.get("host", "") or ""),
            "path": str(data.get("path", "") or ""),
        }
        self._apply_tls(outbound, query, server)
        if not self._apply_transport(outbound, query):
            return None
        name = self._clean_name(str(data.get("ps") or "")) or f"VMess {server}:{port}"
        return Profile(Profile.make_id(link), name, "vmess", server, port, source=source, raw=link, outbound=outbound)

    def _parse_shadowsocks(self, link: str, source: str) -> Profile | None:
        body = link.removeprefix("ss://")
        fragment = ""
        if "#" in body:
            body, fragment = body.split("#", 1)
        if "?" in body:
            body = body.split("?", 1)[0]

        if "@" in body:
            user_info, host_info = body.rsplit("@", 1)
            decoded_user = self._decode_base64_text(user_info) or urllib.parse.unquote(user_info)
            if ":" not in decoded_user:
                return None
            method, password = decoded_user.split(":", 1)
            server, port = self._split_host_port(host_info)
        else:
            decoded = self._decode_base64_text(body)
            if not decoded or "@" not in decoded:
                return None
            user_info, host_info = decoded.rsplit("@", 1)
            if ":" not in user_info:
                return None
            method, password = user_info.split(":", 1)
            server, port = self._split_host_port(host_info)
        if not method or not password or not server or not port:
            return None
        outbound = {"type": "shadowsocks", "server": server, "server_port": port, "method": method, "password": password}
        name = self._clean_name(urllib.parse.unquote(fragment)) or f"SS {server}:{port}"
        return Profile(Profile.make_id(link), name, "ss", server, port, source=source, raw=link, outbound=outbound)

    def _profile(
        self,
        link: str,
        source: str,
        parts: urllib.parse.SplitResult,
        protocol: str,
        server: str,
        port: int,
        outbound: dict[str, object],
    ) -> Profile:
        name = self._clean_name(urllib.parse.unquote(parts.fragment)) or f"{protocol.upper()} {server}:{port}"
        return Profile(Profile.make_id(link), name, protocol, server, port, source=source, raw=link, outbound=dict(outbound))

    @staticmethod
    def _apply_tls(
        outbound: dict[str, object],
        query: dict[str, str],
        server: str,
        default_enabled: bool = False,
    ) -> None:
        security = query.get("security", query.get("tls", "")).lower()
        enabled = default_enabled or security in {"tls", "reality"}
        if not enabled:
            return
        tls: dict[str, object] = {
            "enabled": True,
            "server_name": query.get("sni") or query.get("peer") or query.get("host") or server,
            "insecure": str(query.get("allowInsecure") or query.get("insecure") or "").lower() in {"1", "true", "yes"},
        }
        fingerprint = query.get("fp") or query.get("fingerprint")
        if fingerprint:
            tls["utls"] = {"enabled": True, "fingerprint": fingerprint}
        if security == "reality":
            reality: dict[str, object] = {"enabled": True}
            if query.get("pbk"):
                reality["public_key"] = query["pbk"]
            if query.get("sid"):
                reality["short_id"] = query["sid"]
            tls["reality"] = reality
        outbound["tls"] = tls

    @staticmethod
    def _apply_transport(outbound: dict[str, object], query: dict[str, str]) -> bool:
        transport_type = (query.get("type") or query.get("net") or "").lower()
        if transport_type in {"", "tcp", "raw"}:
            return True
        if transport_type in {"ws", "websocket"}:
            transport: dict[str, object] = {"type": "ws"}
            if query.get("path"):
                transport["path"] = query["path"]
            if query.get("host"):
                transport["headers"] = {"Host": query["host"]}
            outbound["transport"] = transport
            return True
        if transport_type == "grpc":
            service_name = query.get("serviceName") or query.get("service_name") or query.get("path", "").lstrip("/")
            outbound["transport"] = {"type": "grpc", "service_name": service_name}
            return True
        if transport_type in {"httpupgrade", "http_upgrade"}:
            transport = {"type": "httpupgrade"}
            if query.get("path"):
                transport["path"] = query["path"]
            if query.get("host"):
                transport["headers"] = {"Host": query["host"]}
            outbound["transport"] = transport
            return True
        return False

    @staticmethod
    def _query(query_string: str) -> dict[str, str]:
        values = urllib.parse.parse_qs(query_string, keep_blank_values=True)
        return {key: urllib.parse.unquote(items[-1]) for key, items in values.items() if items}

    @staticmethod
    def _server_port(parts: urllib.parse.SplitResult) -> tuple[str, int]:
        return parts.hostname or "", int(parts.port or 0)

    @staticmethod
    def _split_host_port(value: str) -> tuple[str, int]:
        decoded = urllib.parse.unquote(value)
        if decoded.startswith("["):
            host, _, rest = decoded[1:].partition("]")
            return host, int(rest.lstrip(":"))
        host, port = decoded.rsplit(":", 1)
        return host.strip(), int(port)

    @staticmethod
    def _decode_base64_text(value: str) -> str:
        compact = "".join(value.strip().split())
        if not compact:
            return ""
        padding = "=" * (-len(compact) % 4)
        try:
            return base64.urlsafe_b64decode(compact + padding).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError):
            return ""

    @staticmethod
    def _clean_name(value: str) -> str:
        return " ".join(value.replace("\r", " ").replace("\n", " ").split())[:90]
