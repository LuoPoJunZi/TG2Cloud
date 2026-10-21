"""Read-only Docker Nginx discovery and persistent mount/network verification."""
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path, PurePosixPath

from .external_config import (
    HEX,
    OWNER,
    absolute_path,
    configuration_files,
    global_digest,
    http_includes,
    identifier,
)

TEMPLATE = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Config.Image}},'
            '"image_id":{{json .Image}},"running":{{json .State.Running}},'
            '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}},'
            '"user":{{json .Config.User}},"cmd":{{json .Config.Cmd}},'
            '"network_mode":{{json .HostConfig.NetworkMode}},"networks":{{json .NetworkSettings.Networks}},'
            '"ports":{{json .NetworkSettings.Ports}},"userns":{{json .HostConfig.UsernsMode}}}')


class DockerNginx:
    def __init__(self, session):
        self.session = session

    def command(self, args: list[str], *, timeout: int = 30, optional: bool = False) -> str:
        code, output = self.session.run(shlex.join(args), timeout=timeout)
        if code and not optional:
            # nginx -T / Compose errors can contain credentials. Never echo them.
            raise ValueError("外部入口命令未通过：" + " ".join(args[:2]) + "；未显示可能含敏感信息的原始输出。")
        return "" if code else output

    def inspect(self, target: str) -> dict:
        identifier(target)
        output = self.command(["docker", "container", "inspect", "--format", TEMPLATE, target])
        try:
            item = json.loads(output)
            if not HEX.fullmatch(item["id"]):
                raise ValueError
            item["name"] = identifier(item["name"].removeprefix("/"))
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("外部容器元数据无效。") from exc
        return item

    def exec(self, item: dict, *arguments: str, timeout: int = 30) -> str:
        if not item.get("running"):
            raise ValueError("所选外部 Nginx 容器已停止；不会自动启动或重建。")
        return self.command(["docker", "exec", item["id"], *arguments], timeout=timeout)

    def nginx_args(self, item: dict) -> list[str]:
        cmd = item.get("cmd") or []
        config = []
        if "-c" in cmd:
            pos = cmd.index("-c")
            if pos + 1 >= len(cmd):
                raise ValueError("Nginx 主配置参数无效。")
            config = ["-c", absolute_path(cmd[pos + 1])]
        if "-p" in cmd or "-s" in cmd:
            raise ValueError("自定义 prefix／信号入口不支持自动接入；请使用配置导出。")
        return config

    def config(self, item: dict) -> dict[str, str]:
        return configuration_files(self.exec(item, "nginx", "-T", *self.nginx_args(item)))

    def syntax(self, item: dict) -> None:
        try:
            self.exec(item, "nginx", "-t", *self.nginx_args(item))
        except ValueError as exc:
            raise ValueError("外部 Nginx 完整配置检查失败；尚未执行本次 reload，原始配置输出不公开。") from exc

    def reload(self, item: dict) -> None:
        self.syntax(item)
        try:
            self.exec(item, "nginx", "-s", "reload", *self.nginx_args(item))
        except ValueError as exc:
            raise ValueError("外部 Nginx 平滑重载失败；不会改用 restart，请核对事务恢复日志。") from exc

    def candidates(self) -> list[dict]:
        output = self.command(["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}}"])
        result = []
        for cid in output.splitlines():
            if not HEX.fullmatch(cid):
                raise ValueError("Docker 清单无法解析；不猜测端口归属。")
            item = self.inspect(cid)
            if item["name"] == "tg2cloud-proxy-nginx":
                result.append({"name": item["name"], "kind": "managed", "reason": "TG2Cloud 独立入口"})
                continue
            top = self.command(["docker", "top", cid, "-eo", "pid,args"], optional=True)
            if not re.search(r"nginx: (?:master|worker) process|(?:^|\s)(?:/\S*/)?nginx(?:\s|$)", top):
                continue
            reason = ""
            try:
                self.check_supported(item)
                self.check_ports(item)
                files = self.config(item)
                mount = self.choose_mount(item, files)
                self.network(item)
                self.persistent_mount(item, mount)
            except ValueError as exc:
                reason = str(exc)
            result.append({"name": item["name"], "kind": "unsupported" if reason else "external_docker",
                           "reason": reason, "network": item["network_mode"], "running": item["running"]})
        return result

    def check_supported(self, item: dict) -> None:
        if not item.get("running"):
            raise ValueError("Nginx 容器已停止。")
        if item.get("user") not in {"", "root", "0", "0:0", "root:root"} or item.get("userns"):
            raise ValueError("非 root master 或 userns 映射不支持自动写入证书；请导出配置。")
        labels = item.get("labels") or {}
        hint = " ".join((item["image"], item["name"], *labels.keys())).lower()
        if any(word in hint for word in ("nginx-proxy-manager", "nginxproxymanager", "swag", "coolify", "traefik", "kubernetes", "nginx-proxy", "kpanel", "1panel", "aapanel", "dokploy")):
            raise ValueError("配置由面板／控制器管理；不直接写入其生成目录，请通过原管理工具接入。")
        version = self.exec(item, "nginx", "-v")
        if not re.search(r"nginx version: nginx/\d+\.\d+", version):
            raise ValueError("未识别到普通 Nginx；OpenResty／Tengine 等需独立适配。")
        top = self.command(["docker", "top", item["id"], "-eo", "pid,args"])
        if "nginx: master process" not in top:
            raise ValueError("未确认真实 Nginx master 进程。")
        if re.search(r"(?:^|\s)-c\s", top) and "-c" not in (item.get("cmd") or []):
            raise ValueError("实际 master 的配置入口与 Docker 命令不一致。")

    def check_ports(self, item: dict) -> str:
        """Reconcile real Docker publishes, listeners and host-network PIDs."""
        self.check_supported(item)
        cid = item["id"]
        listeners = self.command(["ss", "-H", "-ltnp"])
        ports = {port: [line for line in listeners.splitlines()
                        if len(line.split()) >= 4 and line.split()[3].rsplit(":", 1)[-1] == str(port)]
                 for port in (80, 443)}
        if item["network_mode"] == "host":
            top = self.command(["docker", "top", cid, "-eo", "pid,args"])
            pids = {int(line.split()[0]) for line in top.splitlines()
                    if line.split() and line.split()[0].isdigit() and "nginx" in line}
            for lines in ports.values():
                if not lines or any(not (found := set(map(int, re.findall(r"pid=(\d+)", line)))) or not found <= pids for line in lines):
                    raise ValueError("80/443 的实际监听进程不完全属于所选 host Nginx。")
            return "127.0.0.1"
        bindings = item.get("ports") or {}
        for port in (80, 443):
            bound = bindings.get(f"{port}/tcp") or []
            # Inspect an existing publish; this never binds a socket.
            if not any(entry.get("HostPort") == str(port) and entry.get("HostIp") == "0.0.0.0" for entry in bound):  # nosec B104
                raise ValueError("仅自动支持 Nginx 容器 80/443 到宿主同端口的 IPv4 通配发布，可另含 IPv6；EXPOSE 不能代替发布。")
            # If a userspace listener is present, it must be Docker's verified
            # publish process. Kernel DNAT may have no ss listener at all.
            for line in ports[port]:
                if not any(name in line for name in ('"docker-proxy"', '"dockerd"')):
                    raise ValueError("公网端口同时出现无法归属的监听者。")
        # Check actual HostPort on every running container. A port filter may
        # also select a different container's port 80 published as e.g. 8080.
        output = self.command(["docker", "ps", "--no-trunc", "--format", "{{.ID}}"])
        running = output.split()
        if len(running) > 256 or any(not HEX.fullmatch(value) for value in running):
            raise ValueError("容器清单超出安全范围或无法解析；不猜测端口归属。")
        owners = {80: set(), 443: set()}
        for candidate in running:
            inspected = item if candidate == cid else self.inspect(candidate)
            for values in (inspected.get("ports") or {}).values():
                for binding in values or []:
                    for port, owners_of_port in owners.items():
                        if binding.get("HostPort") == str(port):
                            owners_of_port.add(candidate)
        for owned in owners.values():
            if owned != {cid}:
                raise ValueError("公网端口发布关系不唯一，停止自动接入。")
        return "127.0.0.1"

    def network(self, item: dict) -> dict:
        mode = item["network_mode"]
        if mode == "host":
            return {"mode": "host", "name": "", "id": "", "listen_address": "127.0.0.1"}
        project, service, config = self.compose_config(item)
        declarations = config.get("services", {}).get(service, {}).get("networks", {})
        if isinstance(declarations, list):
            declarations = dict.fromkeys(declarations)
        candidates = []
        for logical in declarations:
            actual = config.get("networks", {}).get(logical, {}).get("name", project + "_" + logical)
            if actual == "bridge" or actual not in (item.get("networks") or {}):
                continue
            identifier(actual)
            info = json.loads(self.command(["docker", "network", "inspect", actual]))[0]
            if info.get("Driver") == "bridge" and info.get("Scope") == "local" and not info.get("Internal"):
                candidates.append({"mode": "bridge", "name": actual, "id": info["Id"], "listen_address": "127.0.0.1"})
        if not candidates:
            raise ValueError("缺少已声明且已连接的本机自定义 bridge 网络。")
        return min(candidates, key=lambda entry: entry["name"])

    def compose_config(self, item):
        labels = item.get("labels") or {}
        project = labels.get("com.docker.compose.project", "")
        service = labels.get("com.docker.compose.service", "")
        paths = labels.get("com.docker.compose.project.config_files", "").split(",")
        if not project or not service or not paths or any(not path for path in paths):
            raise ValueError("bridge 模式需可验证的外部 Compose 与持久化自定义网络；不使用一次性 network connect。")
        identifier(project)
        identifier(service)
        safe_host_path(Path(absolute_path(labels.get("com.docker.compose.project.working_dir", ""))))
        command = ["docker", "compose", "-p", project]
        for path in paths:
            safe_host_path(Path(absolute_path(path)), directory=False)
            command += ["-f", path]
        # Parse privately; this may include interpolated secrets. Never log it.
        config = json.loads(self.command([*command, "config", "--format", "json"]))
        if not isinstance(config.get("services", {}).get(service), dict):
            raise ValueError("原 Compose 中缺少实际服务。")  # noqa: TRY004 - invalid external configuration, not a Python argument type
        return project, service, config

    def persistent_mount(self, item, mount):
        if not (item.get("labels") or {}).get("com.docker.compose.project"):
            return  # Non-Compose host recreation is rejected separately.
        project, name, config = self.compose_config(item)
        service = config["services"][name]
        if service.get("image") != item["image"]:
            raise ValueError("Compose 声明镜像与运行容器不一致。")
        matches = []
        for volume in service.get("volumes", []):
            if not isinstance(volume, dict) or volume.get("target") != mount["destination"] or volume.get("type") != mount["type"]:
                continue
            source = volume.get("source")
            if mount["type"] == "volume":
                source = config.get("volumes", {}).get(source, {}).get("name", project + "_" + str(source))
            if source == (mount["name"] if mount["type"] == "volume" else mount["source"]):
                matches.append(volume)
        if len(matches) != 1:
            raise ValueError("运行挂载未在原 Compose 中唯一持久化；不重建原容器。")
        if item["network_mode"] == "host":
            if service.get("network_mode") != "host":
                raise ValueError("host 网络未在原 Compose 中持久化。")
        else:
            for port in (80, 443):
                if not any(isinstance(publish, dict) and publish.get("target") == port and str(publish.get("published")) == str(port)
                           and publish.get("protocol", "tcp") == "tcp" for publish in service.get("ports", [])):
                    raise ValueError("公网端口未在原 Compose 中持久化。")

    def choose_mount(self, item: dict, files: dict) -> dict:
        targets = http_includes(files)
        matches = []
        for directory in targets:
            for mount in item.get("mounts", []):
                destination = mount.get("Destination", "")
                try:
                    relative = PurePosixPath(directory).relative_to(destination)
                except ValueError:
                    continue
                if mount.get("Type") not in {"bind", "volume"}:
                    continue
                source = Path(absolute_path(mount["Source"]))
                safe_host_path(source)
                host = source.joinpath(*relative.parts)
                safe_host_path(host)
                if mount["Type"] == "volume":
                    name = identifier(mount.get("Name", ""))
                    volume = json.loads(self.command(["docker", "volume", "inspect", name]))[0]
                    if volume.get("Driver") != "local" or volume.get("Options") or volume.get("Mountpoint") != str(source):
                        raise ValueError("只自动支持本机 local、无外部驱动选项的 named volume。")
                else:
                    name = ""
                worker = next((words[1] for text in files.values() for _, words in _directives(text)
                               if words[0] == "user" and len(words) >= 2), "nginx")
                if not re.fullmatch(r"[A-Za-z0-9_-]+", worker):
                    raise ValueError("无法确认 Nginx worker 用户。")
                gid = self.exec(item, "id", "-g", worker).strip()
                if not gid.isdigit() or not 0 <= int(gid) < 65536:
                    raise ValueError("无法确认 Nginx worker 读取组。")
                matches.append({"source": str(source), "destination": destination, "type": mount["Type"],
                                "name": name, "conf_dir": directory, "host_dir": str(host), "worker_gid": int(gid)})
        if not matches:
            raise ValueError("缺少加载于 http 上下文的持久化 *.conf 目录挂载；不会重建原 Nginx。")
        return min(matches, key=lambda entry: (-len(entry["destination"]), entry["conf_dir"]))

    def plan(self, name: str, *, owned: set[str] | None = None) -> dict:
        from tg2cloud.deployment import architecture
        architecture.check_docker(self.session)
        security = json.loads(self.command(["docker", "info", "--format", "{{json .SecurityOptions}}"]))
        if not isinstance(security, list) or any("userns" in str(option).lower() for option in security):
            raise ValueError("Docker daemon 用户命名空间映射不支持自动挂载权限核验。")
        item = self.inspect(name)
        self.check_supported(item)
        listen = self.check_ports(item)
        files = self.config(item)
        mount, network = self.choose_mount(item, files), self.network(item)
        self.persistent_mount(item, mount)
        network["listen_address"] = listen
        labels = item.get("labels") or {}
        identity = {"name": item["name"], "container_id": item["id"], "image": item["image"], "image_id": item["image_id"],
                    "project": labels.get("com.docker.compose.project", ""),
                    "service": labels.get("com.docker.compose.service", ""),
                    "working_dir": labels.get("com.docker.compose.project.working_dir", ""),
                    "config_files": [p for p in labels.get("com.docker.compose.project.config_files", "").split(",") if p],
                    "config_digest": global_digest(files, owned or set())}
        return {"mode": "external_docker", "owner": OWNER, "identity": identity, "mount": mount,
                "network": network, "files": {}, "certificates": {}, "revision": "0" * 32}

    def revalidate(self, saved: dict, *, extra_owned=()) -> tuple[dict, dict]:
        owned = {saved["mount"]["conf_dir"] + "/" + name for name in set(saved["files"]) | set(extra_owned)}
        fresh = self.plan(saved["identity"]["name"], owned=owned)
        for field in ("image", "image_id", "project", "service", "working_dir", "config_files", "config_digest"):
            if fresh["identity"][field] != saved["identity"][field]:
                raise ValueError("外部 Nginx 身份或非受管配置发生漂移；停止自动覆盖。")
        if fresh["mount"] != saved["mount"] or fresh["network"] != saved["network"]:
            raise ValueError("外部挂载或持久化网络发生变化；停止，请重新确认接入计划。")
        if fresh["identity"]["container_id"] != saved["identity"]["container_id"] and not saved["identity"]["project"]:
            raise ValueError("非 Compose 容器被重建，无法仅凭名字确认原归属。")
        return self.inspect(fresh["identity"]["container_id"]), fresh


def _directives(text):
    from .external_config import directives
    return directives(text)


def safe_host_path(path: Path, *, directory: bool = True) -> None:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError("外部路径经过符号链接或不是规范绝对位置。")
    for parent in (*reversed(path.parents), path):
        if parent.exists() and parent.is_symlink():
            raise ValueError("外部路径父目录经过符号链接。")
        if os.name == "posix" and parent.exists():
            info = parent.stat()
            # A root-owned sticky ancestor cannot replace our root-owned child;
            # the actual selected directory must never be world writable.
            sticky_ancestor = parent != path and info.st_uid == 0 and info.st_mode & 0o1000
            if info.st_mode & 0o022 and not sticky_ancestor:
                raise ValueError("外部路径允许非所有者写入，拒绝自动接入。")
        if os.name == "posix" and parent.exists() and parent.stat().st_uid != 0:
            raise ValueError("外部路径不是 root 所有；不以 root 覆盖用户管理目录。")
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("外部持久化目录／Compose 文件缺失。")
