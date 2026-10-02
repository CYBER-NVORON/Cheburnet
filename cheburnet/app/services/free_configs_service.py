from __future__ import annotations

import base64
import json
import urllib.parse
from typing import Any

from cheburnet.app.constants import FREE_CONFIG_SCHEMES
from cheburnet.app.models.profile import Profile


class FreeConfigsService:
    def parse_link(self, link: str, source: str = "") -> Profile | None:
        link = link.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "").strip()
        try:
            if link.startswith("vless://"): return self._parse_vless(link, source)
            if link.startswith("vmess://"): return self._parse_vmess(link, source)
            if link.startswith("trojan://"): return self._parse_trojan(link, source)
            if link.startswith("ss://"): return self._parse_shadowsocks(link, source)
            if link.startswith(("hysteria2://", "hy2://")): return self._parse_hysteria2(link, source)
        except Exception:
            pass
        return None

    def _parse_vless(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        query = self._query(parts.query)
        server, port = self._server_port(parts)
        uuid = urllib.parse.unquote(parts.username or "")
        if not uuid or not server or not port: return None
        
        proxy = {
            "name": "proxy",
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": uuid,
            "network": query.get("type", "tcp"),
            "udp": True,
            "tls": False
        }
        if query.get("flow"): proxy["flow"] = query["flow"]
        if query.get("packetEncoding") or query.get("packet_encoding") or query.get("xudp"): proxy["xudp"] = True

        security = query.get("security", "")
        if security in ("tls", "reality"):
            proxy["tls"] = True
            proxy["servername"] = query.get("sni", server)
            if query.get("fp"): proxy["client-fingerprint"] = query["fp"]
            if query.get("alpn"): proxy["alpn"] = [x.strip() for x in query["alpn"].split(",") if x.strip()]
            
            if security == "reality":
                opts = {}
                if query.get("pbk"): opts["public-key"] = query["pbk"]
                if query.get("sid"): opts["short-id"] = query["sid"]
                if query.get("spx"): opts["spider-x"] = query["spx"]
                proxy["reality-opts"] = opts

        return self._profile("vless", server, port, link, source, proxy)

    def _parse_vmess(self, link: str, source: str) -> Profile | None:
        b64 = link[8:]
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        data = json.loads(base64.b64decode(b64).decode("utf-8"))
        server, port = str(data.get("add", "")), int(data.get("port", 0))
        uuid = str(data.get("id", ""))
        if not uuid or not server or not port: return None
        
        proxy = {
            "name": "proxy",
            "type": "vmess",
            "server": server,
            "port": port,
            "uuid": uuid,
            "alterId": int(data.get("aid", 0)),
            "cipher": data.get("scy", "auto"),
            "network": data.get("net", "tcp"),
            "udp": True,
            "tls": data.get("tls", "") == "tls"
        }
        if proxy["tls"]:
            proxy["servername"] = data.get("sni", server)
            if data.get("fp"): proxy["client-fingerprint"] = data["fp"]
            if data.get("alpn"): proxy["alpn"] = [x.strip() for x in data["alpn"].split(",") if x.strip()]

        return self._profile("vmess", server, port, link, source, proxy)

    def _parse_trojan(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        query = self._query(parts.query)
        server, port = self._server_port(parts)
        password = urllib.parse.unquote(parts.username or "")
        if not password or not server or not port: return None
        
        proxy = {
            "name": "proxy",
            "type": "trojan",
            "server": server,
            "port": port,
            "password": password,
            "network": query.get("type", "tcp"),
            "udp": True,
            "tls": True
        }
        if query.get("sni"): proxy["sni"] = query["sni"]
        if query.get("fp"): proxy["client-fingerprint"] = query["fp"]
        if query.get("alpn"): proxy["alpn"] = [x.strip() for x in query["alpn"].split(",") if x.strip()]
        
        return self._profile("trojan", server, port, link, source, proxy)

    def _parse_shadowsocks(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        server, port = self._server_port(parts)
        user_info = urllib.parse.unquote(parts.username or "")
        if not user_info:
            b64 = parts.netloc.split("@")[0]
            b64 += "=" * ((4 - len(b64) % 4) % 4)
            user_info = base64.b64decode(b64).decode("utf-8")
        if ":" not in user_info: return None
        method, password = user_info.split(":", 1)
        
        proxy = {
            "name": "proxy",
            "type": "ss",
            "server": server,
            "port": port,
            "cipher": method,
            "password": password,
            "udp": True
        }
        return self._profile("shadowsocks", server, port, link, source, proxy)

    def _parse_hysteria2(self, link: str, source: str) -> Profile | None:
        parts = urllib.parse.urlsplit(link)
        query = self._query(parts.query)
        server, port = self._server_port(parts)
        password = urllib.parse.unquote(parts.username or "")
        if not password or not server or not port: return None
        
        proxy = {
            "name": "proxy",
            "type": "hysteria2",
            "server": server,
            "port": port,
            "password": password,
            "sni": query.get("sni", server)
        }
        if query.get("obfs"): proxy["obfs"] = query["obfs"]
        if query.get("obfs-password"): proxy["obfs-password"] = query["obfs-password"]
        
        return self._profile("hysteria2", server, port, link, source, proxy)

    def _profile(self, protocol: str, server: str, port: int, link: str, source: str, proxy: dict[str, Any]) -> Profile:
        parts = urllib.parse.urlsplit(link)
        name = urllib.parse.unquote(parts.fragment) if parts.fragment else f"{protocol.upper()} {server}:{port}"
        return Profile(
            id=Profile.make_id(link),
            name=name,
            protocol=protocol,
            host=server,
            port=port,
            source=source,
            raw=link,
            outbound=proxy,
            config_path="",
            favorite=False,
            status="unchecked",
        )

    def _server_port(self, parts: urllib.parse.SplitResult) -> tuple[str, int]:
        host = parts.hostname or ""
        port = parts.port or 443
        return host, port

    def _query(self, query_string: str) -> dict[str, str]:
        values = urllib.parse.parse_qs(query_string, keep_blank_values=True)
        return {key: urllib.parse.unquote(items[-1]) for key, items in values.items() if items}
