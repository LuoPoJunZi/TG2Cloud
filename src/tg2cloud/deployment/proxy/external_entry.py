"""Lifecycle for an explicitly authorized, existing single-hop Docker Nginx.

No operation stops, starts, recreates or changes the Compose of the external
container. Unsupported environments fail closed and can export a site plan.
"""
from __future__ import annotations

import copy
import json
import os
import re
import ssl
import time
import uuid
from dataclasses import replace
from pathlib import Path, PurePosixPath

from tg2cloud.deployment.profiles import PRODUCTS

from .docker_nginx import DockerNginx
from .external_config import (
    OWNER,
    absolute_path,
    checksum,
    compose_network,
    conflicting_names,
    directives,
    render_route,
    validate_entry,
)
from .external_transaction import SiteTransaction, atomic, canonical, read
from .state import (
    ProxyReport,
    certificate_domains,
    normalize_state,
    routes_from_state,
    state_with_route,
    state_without_route,
    validate_domain,
    validate_email,
)

CRON = Path("/etc/cron.d/tg2cloud-external-proxy")
CRON_CONTENT = ("# " + OWNER + "\nSHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
                "17 */12 * * * root /usr/local/bin/tg2cloud proxy maintain --yes --authorize-proxy >/dev/null 2>&1\n")


class ExternalEntry:
    def __init__(self, manager, entry: dict | None = None):
        from .manager import PROXY_ROOT
        self.manager = manager
        self.session, self.product, self.log = manager.session, manager.product, manager.log
        self.docker = DockerNginx(self.session)
        self.root = Path(PROXY_ROOT)
        self.entry = validate_entry(entry or manager.read_state()["entry"])
        self.directory = Path(self.entry["mount"]["host_dir"])
        self.assets = self.directory / "tg2cloud-assets"
        self.journal = self.root / "state/external-transaction.json"
        self.active_files: set[str] = set()

    def context(self):
        """Validate complete logical identity; permit verified Compose recreation."""
        item, fresh = self.docker.revalidate(self.entry, extra_owned=self.active_files)
        self.entry["identity"]["container_id"] = fresh["identity"]["container_id"]
        return item

    def preflight(self, domain: str = "") -> None:
        item = self.context()
        if self.journal.exists():
            raise ValueError("检测到未完成外部代理事务；先运行 proxy recover，不继续写入。")
        files = self.docker.config(item)
        owned = {self.entry["mount"]["conf_dir"] + "/" + name for name in set(self.entry["files"]) | self.active_files}
        if domain and conflicting_names(files, domain, owned):
            raise ValueError("目标域名与现有精确／通配符／正则站点冲突；不修改已有站点。")
        for name, expected in self.entry["files"].items():
            content = read(self.directory / name)
            if content is None or checksum(content) != expected:
                raise ValueError("受管 Nginx 配置发生外部漂移；先核对，不自动覆盖。")

    def environment(self, domain: str, environment):
        item = self.context()
        self.docker.check_ports(item)
        if environment.dns_aaaa and self.entry["network"]["mode"] == "bridge":
            for port in (80, 443):
                if not any(binding.get("HostIp") == "::" and binding.get("HostPort") == str(port)
                           for binding in (item.get("ports") or {}).get(str(port) + "/tcp") or []):
                    raise ValueError("域名有 AAAA，但外部 Nginx 未发布 IPv6 80/443；先修复，不绕过验证。")
        return replace(environment, port_80="OWN", port_443="OWN")

    def setup_assets(self):
        canonical(self.assets)
        marker = self.assets / "owner.json"
        expected = {"owner": OWNER, "mount_source": self.entry["mount"]["source"], "container_dir": self.entry["mount"]["conf_dir"]}
        if marker.exists():
            if json.loads(read(marker)) != expected:
                raise ValueError("同名外部入口资产目录归属不符。")
        elif self.assets.exists() and any(self.assets.iterdir()):
            raise ValueError("外部入口资产目录有未知内容；不接管。")
        else:
            self.assets.mkdir(mode=0o750, exist_ok=True)
            atomic(marker, json.dumps(expected, sort_keys=True).encode())
        if os.name == "posix":
            os.chown(self.assets, 0, self.entry["mount"]["worker_gid"])
        self.assets.chmod(0o750)
        for child in ("webroot", "auth", "letsencrypt", "work", "logs"):
            path = self.assets / child
            canonical(path)
            path.mkdir(mode=0o750 if child in {"webroot", "auth"} else 0o700, exist_ok=True)
            if child in {"webroot", "auth"} and os.name == "posix":
                os.chown(path, 0, self.entry["mount"]["worker_gid"])
            path.chmod(0o750 if child in {"webroot", "auth"} else 0o700)

    def cert_path(self, container_path: str) -> Path:
        """Resolve certbot live symlinks only inside a verified persistent mount."""
        absolute_path(container_path)
        item = self.context()
        for mount in sorted(item.get("mounts", []), key=lambda value: -len(value["Destination"])):
            if mount.get("Type") not in {"bind", "volume"}:
                continue
            try:
                relative = PurePosixPath(container_path).relative_to(mount["Destination"])
            except ValueError:
                continue
            source = Path(mount["Source"])
            canonical(source)
            if mount["Type"] == "volume":
                volume = json.loads(self.docker.command(["docker", "volume", "inspect", mount["Name"]]))[0]
                if volume.get("Driver") != "local" or volume.get("Options") or volume.get("Mountpoint") != str(source):
                    raise ValueError("证书卷不是已核验的本地持久化卷。")
            original = source.joinpath(*relative.parts)
            path = original.resolve()
            if not path.is_relative_to(source.resolve()) or not path.is_file():
                raise ValueError("证书缺失或链接越过持久化挂载范围。")
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("证书文件过大。")
            return path
        raise ValueError("证书不位于可验证的持久化挂载中。")

    def certificate_valid(self, domain: str, cert: dict) -> bool:
        try:
            chain, key = self.cert_path(cert["chain"]), self.cert_path(cert["key"])
            if os.name == "posix" and key.stat().st_mode & 0o077:
                return False
            for args in (["openssl", "x509", "-in", str(chain), "-noout", "-checkhost", domain, "-checkend", "604800"],
                         ["openssl", "verify", "-untrusted", str(chain), str(chain)]):
                self.docker.command(args)
            public = self.docker.command(["openssl", "x509", "-in", str(chain), "-pubkey", "-noout"])
            private_public = self.docker.command(["openssl", "pkey", "-in", str(key), "-pubout"])
            return bool(public.strip()) and public.strip() == private_public.strip()
        except (ValueError, OSError):
            return False

    def certificate_record(self, domain: str, *, existing: dict | None = None) -> dict:
        if existing:
            return copy.deepcopy(existing)
        item = self.context()
        # Existing certificate reuse never means adopting someone else's renewal.
        for text in self.docker.config(item).values():
            chain = key = ""
            for _, words in directives(text):
                if words[0] == "ssl_certificate" and len(words) == 2:
                    chain = words[1]
                elif words[0] == "ssl_certificate_key" and len(words) == 2:
                    key = words[1]
                if chain and key:
                    try:
                        absolute_path(chain)
                        absolute_path(key)
                    except ValueError:
                        continue
                    record = self.new_certificate(domain, "external", chain, key)
                    if self.certificate_valid(domain, record):
                        return record
        prefix = self.entry["mount"]["conf_dir"] + "/tg2cloud-assets/letsencrypt/live/" + domain
        return self.new_certificate(domain, "tg2cloud", prefix + "/fullchain.pem", prefix + "/privkey.pem")

    @staticmethod
    def new_certificate(domain, owner, chain, key):
        return {"owner": owner, "chain": chain, "key": key, "name": domain, "loaded": "", "pending_load": False,
                "last_attempt": 0, "last_success": 0, "last_change": 0}

    def certbot(self, arguments: list[str], *, timeout: int = 360) -> None:
        from tg2cloud.deployment import architecture

        from .manager import CERTBOT_IMAGE
        architecture.ensure_image(self.session, CERTBOT_IMAGE)
        # The temporary filesystem is container memory, not a shared host path.
        command = ["docker", "run", "--rm", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--tmpfs", "/tmp", "--entrypoint", "certbot"]  # nosec B108
        for host, inside in (("letsencrypt", "/etc/letsencrypt"), ("webroot", "/var/www/certbot"),
                             ("work", "/var/lib/letsencrypt"), ("logs", "/var/log/letsencrypt")):
            command += ["--mount", "type=bind,src=" + str(self.assets / host) + ",dst=" + inside]
        command += [CERTBOT_IMAGE, *arguments]
        self.docker.command(command, timeout=timeout)

    def obtain(self, domain, email):
        cert = self.entry["certificates"][domain]
        if self.certificate_valid(domain, cert):
            if cert["owner"] == "external":
                self.log("复用已有有效证书；续期仍由原工具负责，TG2Cloud 未验证或接管其调度。")
            return
        if cert["owner"] != "tg2cloud":
            raise ValueError("外部证书已失效；请通过原证书管理工具修复，不重复接管签发。")
        now = int(time.time())
        # Persist bounded retry information before ACME; no tight issuance loop.
        attempts = self.root / "state/external-acme-attempts.json"
        record = json.loads(read(attempts) or b"{}")
        previous = record.get(domain, 0)
        if type(previous) is not int or now - previous < 300:
            raise ValueError("该域名最近已尝试签发，请至少等待 5 分钟并先检查失败原因。")
        record[domain] = now
        atomic(attempts, json.dumps(record, sort_keys=True).encode())
        registration = ["--email", validate_email(email)] if email else ["--register-unsafely-without-email"]
        try:
            self.certbot(["certonly", "--webroot", "-w", "/var/www/certbot", "--non-interactive", "--agree-tos",
                          "--cert-name", domain, "-d", domain, *registration])
        except ValueError as exc:
            raise ValueError("Certbot Webroot 签发失败；检查 DNS、80 入站与私密证书日志，不反复申请或停止外部 Nginx。") from exc
        if not self.certificate_valid(domain, cert):
            raise ValueError("证书签发后域名、信任链或私钥匹配校验未通过。")

    def verify_webroot(self, domain):
        directory = self.assets / "webroot/.well-known/acme-challenge"
        for path in (directory.parent, directory):
            canonical(path)
            path.mkdir(mode=0o755, exist_ok=True)
        token = "tg2cloud-" + uuid.uuid4().hex
        path = directory / token
        atomic(path, token.encode(), mode=0o644)
        try:
            output = self.docker.command(["curl", "--noproxy", "*", "--resolve",
                domain + ":80:" + self.entry["network"]["listen_address"], "-fsS", "--max-time", "10",
                "http://" + domain + "/.well-known/acme-challenge/" + token])
            if output.strip() != token:
                raise ValueError("HTTP-01 引导配置未实际加载或持久化 Webroot 映射错误。")
        finally:
            path.unlink(missing_ok=True)

    def canaries(self, item):
        """Bounded status probes; no credentials or bodies are retained."""
        owned = {self.entry["mount"]["conf_dir"] + "/" + name for name in set(self.entry["files"]) | self.active_files}
        names = set()
        for path, text in self.docker.config(item).items():
            if path in owned:
                continue
            for _, words in directives(text):
                if words[0] == "server_name":
                    for word in words[1:]:
                        try:
                            names.add(validate_domain(word))
                        except ValueError:
                            continue
        result = {}
        for domain in sorted(names)[:8]:
            result[domain] = self.docker.command(["curl", "--noproxy", "*", "--resolve",
                domain + ":80:" + self.entry["network"]["listen_address"], "--max-time", "8", "-sS",
                "-o", "/dev/null", "-w", "%{http_code}", "http://" + domain + "/"]).strip()
        return result

    def files(self, state: dict, *, bootstrap: str = "") -> dict[str, bytes]:
        result = {}
        for route in routes_from_state(state):
            if route.domain != bootstrap:
                result["tg2cloud-" + route.edition + ".conf"] = render_route(route, self.entry).encode()
        for edition, route in state.get("external_webdav", {}).items():
            if route["domain"] != bootstrap:
                result["tg2cloud-webdav-" + edition + ".conf"] = render_route(route, self.entry).encode()
        if bootstrap:
            from .state import DomainRoute
            dav = next((key for key, route in state.get("external_webdav", {}).items() if route["domain"] == bootstrap), "")
            basename = "tg2cloud-webdav-" + dav if dav else "tg2cloud-" + self.product.key
            result[basename + ".conf"] = render_route(
                DomainRoute(self.product.key, bootstrap, self.product.management_port), self.entry, bootstrap=True).encode()
        return result

    def copy_auth(self, state):
        for edition in state.get("external_webdav", {}):
            self.sync_auth(edition)

    def sync_auth(self, edition):
        if edition not in PRODUCTS:
            raise ValueError("未知认证资源归属。")
        self.context()
        source = self.root / "external-auth" / (edition + ".htpasswd")
        content = read(source)
        if content is None or len(content) > 16384:
            raise ValueError("外部 WebDAV 认证文件缺失或过大。")
        # Directory mount observes atomic replacement immediately, even if a
        # later route reload fails. No old-password fallback on revocation.
        atomic(self.assets / "auth" / source.name, content, mode=0o640, gid=self.entry["mount"]["worker_gid"])

    def revoke_auth(self, edition):
        if edition not in PRODUCTS:
            raise ValueError("未知认证资源归属。")
        marker = json.loads(read(self.assets / "owner.json") or b"{}")
        if marker != {"owner": OWNER, "mount_source": self.entry["mount"]["source"], "container_dir": self.entry["mount"]["conf_dir"]}:
            raise ValueError("认证目录归属不能确认；请立即通过原入口管理员停用该外部站点。")
        # First revoke the known persistent copy, even if a later identity /
        # network check fails. Never silently keep the previous credential.
        atomic(self.assets / "auth" / (edition + ".htpasswd"), b"disabled:!\n", mode=0o640,
               gid=self.entry["mount"]["worker_gid"])
        self.context()
        self.verify_auth(edition)

    def verify_auth(self, edition):
        source = self.root / "external-auth" / (edition + ".htpasswd")
        target = self.assets / "auth" / source.name
        if read(source) != read(target):
            raise ValueError("外部入口未读取到本次认证文件。")
        output = self.docker.exec(self.context(), "sha256sum", self.entry["mount"]["conf_dir"] + "/tg2cloud-assets/auth/" + source.name)
        if not output.split() or output.split()[0] != checksum(read(source)):
            raise ValueError("Nginx 容器读取的认证哈希不匹配。")

    def check_backend(self, edition):
        product = PRODUCTS[edition]
        gateway = self.docker.inspect(product.storage_container)
        labels = gateway.get("labels") or {}
        if (labels.get("com.docker.compose.service") != edition or
                not labels.get("com.docker.compose.project") or
                labels.get("com.docker.compose.project.working_dir") != product.install_dir):
            raise ValueError("真实存储网关的 Compose 归属不匹配。")
        if self.entry["network"]["mode"] == "bridge":
            network = self.entry["network"]["name"]
            links = gateway.get("networks") or {}
            if network not in links or links[network].get("NetworkID") != self.entry["network"]["id"]:
                raise ValueError("存储网关缺少持久化入口网络，不能只用临时 network connect 修复。")
            source = Path(product.install_dir) / "docker-compose.yml"
            canonical(source)
            if "    name: " + network + "\n" not in source.read_text():
                raise ValueError("网络连接未写入受管 Compose；拒绝宣称可持久化。")
            info = json.loads(self.docker.command(["docker", "network", "inspect", network]))[0]
            for cid in info.get("Containers", {}):
                other = self.docker.inspect(cid)
                link = (other.get("networks") or {}).get(network, {})
                if product.storage_container in (link.get("Aliases") or []) and cid != gateway["id"]:
                    raise ValueError("网关 DNS 别名与网络中另一容器冲突。")
            target = "http://" + product.storage_container + ":" + str(product.management_port) + "/"
            item = self.context()
            has_curl = self.docker.command(["docker", "exec", item["id"], "curl", "--version"], optional=True)
            arguments = ("curl", "--noproxy", "*", "-fsS", "--max-time", "8", target) if has_curl else ("wget", "-q", "-T", "8", "-O", "-", target)
            output = self.docker.exec(item, *arguments)
        else:
            output = self.docker.command(["curl", "--noproxy", "*", "-fsS", "--max-time", "8",
                                          "http://127.0.0.1:" + str(product.management_port) + "/"])
        if not re.search("OpenList|openlist|CloudDrive|clouddrive", output[:262144]):
            raise ValueError("后端可连接但没有识别到目标网关页面；不以 HTTP 200 冒充验收。")
        bindings = gateway.get("ports") or {}
        for values in bindings.values():
            if any(value.get("HostIp") not in {"127.0.0.1", "::1"} for value in values or []):
                raise ValueError("网关管理端口存在非回环发布，拒绝开放新入口。")

    def served_fingerprint(self, domain):
        # No shell interpolation from remote output; domain is strictly checked.
        domain = validate_domain(domain)
        address = self.entry["network"]["listen_address"]
        connect = ("[" + address + "]" if ":" in address else address) + ":443"
        output = self.docker.command(["openssl", "s_client", "-connect", connect, "-servername", domain,
                                     "-verify_hostname", domain, "-verify_return_error", "-showcerts"], timeout=20)
        match = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", output, re.DOTALL)
        if not match:
            raise ValueError("没有读取到实际加载的 HTTPS 服务证书。")
        return checksum(ssl.PEM_cert_to_DER_cert(match[0]))

    def disk_fingerprint(self, cert):
        output = self.docker.command(["openssl", "x509", "-in", str(self.cert_path(cert["chain"])), "-outform", "PEM"])
        return checksum(ssl.PEM_cert_to_DER_cert(output))

    def check_route(self, domain, *, dav=False, enabled=True):
        resolve = domain + ":443:" + self.entry["network"]["listen_address"]
        base = ["curl", "--noproxy", "*", "--resolve", resolve, "--max-time", "12", "-sS"]
        if dav:
            for path, expected in (("/", "404"), ("/dav/", "401" if enabled else "403")):
                code = self.docker.command([*base, "-o", "/dev/null", "-w", "%{http_code}", "https://" + domain + path])
                if code.strip() != expected:
                    raise ValueError("外部只读入口的路径／未授权访问检查失败。")
        else:
            output = self.docker.command([*base, "-f", "https://" + domain + "/"])
            if not re.search("OpenList|openlist|CloudDrive|clouddrive", output[:262144]):
                raise ValueError("HTTPS 页面未识别为目标存储网关。")
            for path in ("/dav", "/dav/"):
                code = self.docker.command([*base, "-o", "/dev/null", "-w", "%{http_code}", "https://" + domain + path])
                if code.strip() != "403":
                    raise ValueError("管理域名公开 WebDAV 阻断未通过。")
        header = self.docker.command(["curl", "--noproxy", "*", "--resolve", domain + ":80:" + self.entry["network"]["listen_address"],
                                      "--max-time", "10", "-sS", "-D", "-", "-o", "/dev/null", "http://" + domain + "/"])
        if not re.search(r"(?im)^Location: https://" + re.escape(domain) + r"/\s*$", header):
            raise ValueError("HTTP 到 HTTPS 的域名跳转未通过。")
        cert = self.entry["certificates"][domain]
        if not self.certificate_valid(domain, cert):
            raise ValueError("证书域名、有效期、信任链或私钥匹配检查失败。")
        if self.served_fingerprint(domain) != self.disk_fingerprint(cert):
            raise ValueError("证书文件已更新，但当前 TLS 服务尚未加载该证书。")

    def verify(self, state, *, verify_remaining=True):
        self.docker.syntax(self.context())
        if not verify_remaining:
            # Revocation must not depend on a different backend being healthy.
            # Syntax + actual authentication hash are still checked by caller.
            return
        editions = set(state["domains"]) | set(state.get("external_webdav", {}))
        for edition in editions:
            self.check_backend(edition)
        for route in routes_from_state(state):
            self.check_route(route.domain)
        for route in state.get("external_webdav", {}).values():
            self.check_route(route["domain"], dav=True, enabled=route["enabled"])
        for domain in certificate_domains(state):
            cert = self.entry["certificates"][domain]
            cert["loaded"] = self.disk_fingerprint(cert)
            cert["pending_load"] = False

    def schedule_healthy(self):
        return (read(CRON) == CRON_CONTENT.encode() and any(
            self.docker.command(["systemctl", "is-active", service], optional=True).strip() == "active"
            for service in ("cron", "crond")))

    def install_schedule(self, state):
        self._schedule_before = read(CRON)
        active = any(self.entry["certificates"][name]["owner"] == "tg2cloud" for name in certificate_domains(state))
        if CRON.exists() and read(CRON) != CRON_CONTENT.encode():
            raise ValueError("同名续期调度文件归属或内容不符，拒绝覆盖。")
        if active:
            from tg2cloud.deployment import runtime
            runtime.install()
            if not any(self.docker.command(["systemctl", "is-active", service], optional=True).strip() == "active"
                       for service in ("cron", "crond")):
                raise ValueError("未确认活动 cron/crond 服务，未建立自动续期闭环；请先启用系统调度再重试。")
            atomic(CRON, CRON_CONTENT.encode(), mode=0o644)
        elif CRON.exists():
            CRON.unlink()

    def rollback_schedule(self):
        if not hasattr(self, "_schedule_before"):
            return
        current = read(CRON)
        if current == self._schedule_before:
            return
        if current not in {None, CRON_CONTENT.encode()}:
            raise ValueError("续期任务被并发修改，不覆盖。")
        if self._schedule_before is None:
            CRON.unlink(missing_ok=True)
        else:
            atomic(CRON, self._schedule_before, mode=0o644)

    def transaction(self, target, *, domain="", email="", verify=None, verify_remaining=True):
        """Called with the existing entry lock; state is committed only last."""
        from .manager import defer_interruptions
        baseline = self.manager.read_state()
        self.preflight(domain)
        item = self.context()
        canaries = self.canaries(item)
        self.setup_assets()
        self.backup(baseline)
        target = copy.deepcopy(target)
        target.update(version=3, external_webdav=target.get("external_webdav", {}))
        target["entry"] = self.entry
        active_domains = certificate_domains(target)
        self.entry["certificates"] = {name: cert for name, cert in self.entry["certificates"].items() if name in active_domains}
        for name in active_domains:
            if name not in self.entry["certificates"]:
                self.entry["certificates"][name] = self.certificate_record(name)
        self.copy_auth(target)
        # Private, file-scoped recovery material is durable before publication.
        previous_files = dict(self.entry["files"])
        desired = self.files(target, bootstrap=domain) if domain and not self.certificate_valid(domain, self.entry["certificates"][domain]) else self.files(target)
        transaction = SiteTransaction(self.directory, self.journal, previous_files, desired)
        self.active_files = set(previous_files) | set(desired)
        # Store the immutable candidate identity outside user Nginx directories.
        # A unique commit token distinguishes a no-op candidate from an old
        # committed state having exactly the same file hashes after a crash.
        self.entry["revision"] = uuid.uuid4().hex
        atomic(self.root / "state/external-context.json", json.dumps(self.entry, sort_keys=True).encode())
        committed = False
        try:
            transaction.publish()
            self.docker.reload(item)
            if domain:
                self.verify_webroot(domain)
                self.obtain(domain, email)
                final = self.files(target)
                # The same journal must cover the *final* candidate on crash.
                for name in set(final) | set(desired):
                    if name not in transaction.items:
                        raise ValueError("事务最终站点范围变化。")
                    from .external_transaction import encode
                    current = read(self.directory / name)
                    if current != desired.get(name):
                        raise ValueError("签发期间站点被并发修改，停止覆盖。")
                    transaction.items[name]["intermediate"].append(transaction.items[name]["after"])
                    transaction.items[name]["after"] = encode(final.get(name))
                transaction.save()
                for name, content in final.items():
                    atomic(self.directory / name, content, mode=0o644)
                self.docker.reload(item)
                desired = final
            self.verify(target, verify_remaining=verify_remaining)
            if self.canaries(item) != canaries:
                raise ValueError("原站点抽样 HTTP 状态发生变化；停止提交并回滚本站点。")
            if verify:
                verify()
            for name, content in desired.items():
                if read(self.directory / name) != content:
                    raise ValueError("验收期间受管站点发生漂移；不提交状态。")
            self.entry["files"] = {name: checksum(content) for name, content in desired.items()}
            validate_entry(self.entry)
            if self.manager.read_state() != baseline:
                raise ValueError("事务期间共享状态被另一写入端修改；不覆盖。")
            self.install_schedule(target)
            with defer_interruptions():
                self.manager._commit_state(normalize_state(json.dumps(target)))
                committed = True
                transaction.data["phase"] = "committed"
                transaction.save()
                transaction.finish()
            pending = self.root / "state" / ("external-pending-" + self.product.key + ".json")
            if pending.exists():
                pending.unlink()
        except BaseException:
            if not committed:
                try:
                    with defer_interruptions():
                        transaction.rollback()
                        self.docker.reload(item)
                        self.rollback_schedule()
                        transaction.finish()
                except (Exception, KeyboardInterrupt) as rollback_error:  # noqa: BLE001 - retain journal and original exception even if recovery fails
                    self.log("外部入口回滚未完成（" + type(rollback_error).__name__ + "），恢复日志已保留；不覆盖其他文件，不停止外部 Nginx。")
            raise

    def configure(self, domain, email, *, already_locked=False):
        from contextlib import nullcontext

        from .manager import proxy_lock_command
        domain, email = validate_domain(domain), validate_email(email)
        with nullcontext() if already_locked else self.session.hold_lock(proxy_lock_command()):
            previous = self.manager.read_state()
            target = state_with_route(previous, self.product, domain)
            self.manager._validate_environment(self.manager.probe(domain))
            self.transaction(target, domain=domain, email=email)
        return self.status(self.manager.read_state())

    def status(self, state):
        route = state["domains"].get(self.product.key)
        if not route:
            return ProxyReport("", "not_configured", "当前 Edition 尚未配置域名访问。", ())
        domain = route["domain"]
        try:
            self.preflight()
            self.manager._validate_environment(self.manager.probe(domain))
            self.verify(state)
            if any(self.entry["certificates"][name]["owner"] == "tg2cloud" for name in certificate_domains(state)) and not self.schedule_healthy():
                raise ValueError("证书续期调度缺失或 cron 服务未运行；请修复后重试。")
        except (ValueError, OSError, RuntimeError) as exc:
            return ProxyReport(domain, "running_error", str(exc), (("外部 Docker Nginx 入口", "失败"),))
        warnings = tuple("证书 " + name + " 由外部工具负责续期，自动续期机制未经 TG2Cloud 核验。"
                         for name in certificate_domains(state) if self.entry["certificates"][name]["owner"] == "external")
        for name in certificate_domains(state):
            record = self.entry["certificates"][name]
            if record["owner"] == "tg2cloud" and (record["last_attempt"] > record["last_success"] or
                    (record["last_attempt"] and time.time() - record["last_attempt"] > 26 * 3600)):
                warnings += ("证书 " + name + " 最近续期失败或超过 26 小时没有检查；当前 TLS 通过不代表调度正常。",)
        return ProxyReport(domain, "healthy", "外部 Docker Nginx 单层入口的本机 TLS、后端、跳转、证书加载与访问限制检查通过；公网仍需独立验收。",
                           (("外部容器／配置／网络身份", "通过"), ("HTTPS 与实际加载证书", "通过"),
                            ("管理域名 WebDAV 阻断", "通过")), warnings=warnings)

    def remove_locked(self):
        previous = self.manager.read_state()
        target = state_without_route(previous, self.product.key)
        if target != previous:
            self.transaction(target)
        return ProxyReport("", "not_configured", "已移除当前管理路由；外部 Nginx 和证书保持不动。", ())

    def backup(self, state):
        """File-scoped private snapshot, never copy another project's config tree."""
        import hashlib
        import io
        import tarfile
        files = {"state.json": (json.dumps(state, sort_keys=True) + "\n").encode()}
        for name, digest in self.entry["files"].items():
            data = read(self.directory / name)
            if data is None or checksum(data) != digest:
                raise ValueError("备份前站点发生漂移。")
            files["sites/" + name] = data
        # Keys are deliberately not duplicated: retain original persistent
        # certificate storage; record external ownership and paths in state.
        manifest = {"schema": 1, "owner": OWNER, "scope": "metadata-and-owned-sites",
                    "certificates_included": False,
                    "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        files["manifest.json"] = (json.dumps(manifest, sort_keys=True) + "\n").encode()
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name, data in sorted(files.items()):
                item = tarfile.TarInfo(name)
                item.size, item.mode = len(data), 0o600
                archive.addfile(item, io.BytesIO(data))
        path = self.root / "external-backups" / (str(time.time_ns()) + "-" + uuid.uuid4().hex + ".tar.gz")
        atomic(path, output.getvalue())
        return path

    def check_backup(self, *, archive="", drill=False):
        import io
        import tarfile
        import tempfile
        directory = self.root / "external-backups"
        canonical(directory)
        candidates = sorted(directory.glob("*.tar.gz")) if directory.exists() else []
        path = Path(archive) if archive else candidates[-1] if candidates else None
        if path is None or path.parent != directory or not re.fullmatch(r"[0-9]+-[0-9a-f]{32}\.tar\.gz", path.name):
            raise ValueError("没有选中归属可核验的外部入口备份。")
        raw = read(path)
        if raw is None:
            raise ValueError("备份文件不存在。")
        files = {}
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as package:
            for member in package:
                if (not member.isfile() or member.name in files or member.size > 512 * 1024
                        or len(files) >= 6 or not re.fullmatch(r"(?:state|manifest)\.json|sites/tg2cloud-(?:clouddrive2|openlist|webdav-clouddrive2|webdav-openlist)\.conf", member.name)):
                    raise ValueError("备份包含不受支持的类型／范围。")
                handle = package.extractfile(member)
                if handle is None:
                    raise ValueError("备份内容缺失。")
                files[member.name] = handle.read(512 * 1024 + 1)
        manifest = json.loads(files.pop("manifest.json", b"{}"))
        if (manifest != {"schema": 1, "owner": OWNER, "scope": "metadata-and-owned-sites", "certificates_included": False,
                         "files": {name: checksum(data) for name, data in files.items()}} or "state.json" not in files):
            raise ValueError("备份清单与内容摘要不符。")
        normalize_state(files["state.json"])
        if drill:
            with tempfile.TemporaryDirectory(prefix="tg2cloud-external-drill-") as temporary:
                root = Path(temporary).resolve()
                for name, data in files.items():
                    atomic(root / name, data)
                if any(read(root / name) != data for name, data in files.items()):
                    raise ValueError("隔离解包复验失败。")
        return str(path) + "；元数据／专属站点摘要" + ("及隔离解包" if drill else "") + "通过；不含私钥，不等于服务可恢复。"

    def maintain(self, *, dry_run=False):
        from .manager import proxy_lock_command
        with self.session.hold_lock(proxy_lock_command()):
            state = self.manager.read_state()
            self.preflight()
            item = self.context()
            failures = []
            for domain in certificate_domains(state):
                cert = self.entry["certificates"][domain]
                if cert["owner"] != "tg2cloud":
                    continue
                cert["last_attempt"] = int(time.time())
                try:
                    before = self.disk_fingerprint(cert)
                    args = ["renew", "--cert-name", domain, "--non-interactive", "--no-random-sleep-on-renew", "--no-directory-hooks"]
                    if dry_run:
                        args += ["--dry-run"]
                    self.certbot(args, timeout=540)
                    after = self.disk_fingerprint(cert)
                    cert["last_success"] = int(time.time())
                    if after != before:
                        cert["last_change"] = int(time.time())
                    cert["pending_load"] = after != cert["loaded"]
                except (ValueError, OSError, RuntimeError):
                    failures.append(domain)
            # Persist a pending-load state before reload, including on failure.
            state["entry"] = self.entry
            self.manager._commit_state(state)
            if any(self.entry["certificates"][name]["pending_load"] for name in certificate_domains(state)):
                self.docker.reload(item)
            self.verify(state)
            self.manager._commit_state(state)
            if failures:
                raise ValueError("部分证书续期失败；有效证书未删除，请检查证书日志。")
        return "证书检查／续期与实际加载检查完成；检查成功不等于本次发生续签。"


def selected_entry(manager, state=None):
    state = state if state is not None else manager.read_state()
    entry = state.get("entry") if state.get("version") == 3 else getattr(manager, "external_plan", None)
    return ExternalEntry(manager, entry) if entry else None


def apply_payload_network(manager, path: Path):
    adapter = selected_entry(manager)
    if adapter and adapter.entry["network"]["mode"] == "bridge":
        from .manager import proxy_lock_command
        # A failed base/HTTPS phase must remain recognizable on a later retry.
        # This is not a committed route and never authenticates unknown code.
        with manager.session.hold_lock(proxy_lock_command()):
            adapter.preflight()
            root = adapter.root / "state"
            record = {"schema": 1, "edition": manager.product.key,
                      "instance_dir": manager.product.install_dir, "entry": adapter.entry}
            pending = root / ("external-pending-" + manager.product.key + ".json")
            existing = read(pending)
            if existing and json.loads(existing) != record:
                raise ValueError("已有不同的待恢复网络计划；请先核对，不覆盖。")
            atomic(pending, (json.dumps(record, sort_keys=True) + "\n").encode())
        canonical(path)
        atomic(path, compose_network(path.read_text(), manager.product.key, adapter.entry["network"]["name"]).encode(), mode=0o644)


def retained_network(product, directory: Path, state: dict, root: Path) -> str:
    """Accept only an explicit private pending plan or schema-3 verified state."""
    entry = state.get("entry", {})
    if not entry:
        from tg2cloud.deployment.configuration import regular_private
        pending = root / "state" / ("external-pending-" + product.key + ".json")
        if not pending.exists():
            return ""
        record = json.loads(regular_private(pending))
        if (set(record) != {"schema", "edition", "instance_dir", "entry"} or record["schema"] != 1
                or record["edition"] != product.key or record["instance_dir"] != str(directory)):
            raise ValueError("待恢复网络计划归属不符。")
        entry = validate_entry(record["entry"])
    return entry["network"]["name"] if entry["network"]["mode"] == "bridge" else ""
