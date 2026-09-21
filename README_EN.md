<p align="center">
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

<p align="center">
  <img src="assets/brand/tg2cloud-logo.svg" alt="TG2Cloud" width="420">
</p>

<h1 align="center">TG2Cloud</h1>

<p align="center"><strong>From Telegram to Your Cloud</strong></p>

TG2Cloud is a self-hosted personal file transfer tool. Send a file to your own Telegram Bot, let a VPS persist and process the task, and write it through rclone and CloudDrive2 or OpenList WebDAV to cloud storage mounted by you.

```text
Telegram
    ↓
TG2Cloud
    ↓
CloudDrive2 / OpenList
    ↓
Your Cloud
```

115 is one of the primary test cases and documentation examples, but it is not the only supported destination. The cloud providers available to TG2Cloud are determined by the storage you mount in CloudDrive2 or OpenList.

This repository evolved from [whyhhh20/TG115](https://github.com/whyhhh20/TG115). It retains the original attribution and license while adding stronger task recovery, disk protection, streaming transfers, state semantics, rollback, VPS resource guidance, and operational diagnostics.

> Current version: **TG2Cloud v1.0.2**
>
> OpenList has passed real-VPS deployment and WebDAV acceptance testing with OpenList and 115 Open. CloudDrive2 keeps the stable workflow already accepted on a real VPS. Both official EXEs are built by GitHub Actions from the same `v1.0.2` tag.

> Only transfer content that you are authorized to save, back up, and use. Follow the laws and terms that apply to Telegram, your cloud provider, CloudDrive2/OpenList, the content source, and your jurisdiction.

## Downloads

Windows users should download the required edition and `SHA256SUMS.txt` from [GitHub Releases](https://github.com/LuoPoJunZi/TG2Cloud/releases):

- **CloudDrive2 Edition** — `TG2Cloud-CloudDrive2-Deployer.exe`

  For users who already use, or plan to use, CloudDrive2 to manage cloud storage and expose it as the WebDAV storage gateway.

- **OpenList Edition** — `TG2Cloud-OpenList-Deployer.exe`

  For users who want OpenList to mount and manage cloud storage and expose it as the WebDAV storage gateway.

Verify the downloaded files in Windows PowerShell:

```powershell
Get-FileHash ".\TG2Cloud-CloudDrive2-Deployer.exe" -Algorithm SHA256
Get-FileHash ".\TG2Cloud-OpenList-Deployer.exe" -Algorithm SHA256
```

The TG2Cloud v1.0.2 Windows EXEs are not commercially code-signed. Windows SmartScreen may show an “Unknown publisher” warning on first launch. Download only from this repository's Releases page, verify SHA-256, and do not disable Microsoft Defender or Windows Security.

## Contents

- [How It Works](#how-it-works)
- [Key Features](#key-features)
- [Important Boundaries](#important-boundaries)
- [Requirements](#requirements)
- [Windows GUI Deployment](#windows-gui-deployment)
- [CloudDrive2 Configuration](#clouddrive2-configuration)
- [OpenList and Cloud Storage Configuration](#openlist-and-cloud-storage-configuration)
- [Real WebDAV Acceptance Test](#real-webdav-acceptance-test)
- [Daily Use](#daily-use)
- [Bot Commands](#bot-commands)
- [VPS Operations and Upgrades](#vps-operations-and-upgrades)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Local Development and Testing](#local-development-and-testing)
- [Acknowledgements and Project Origin](#acknowledgements-and-project-origin)

## How It Works

```text
Private chat with your Telegram Bot
                ↓
       Persistent SQLite queue
                ↓
Regular files: fully downloaded to the VPS first
Large files: Telegram → rclone streaming pipeline
                ↓
CloudDrive2 WebDAV or OpenList WebDAV
                ↓
       Cloud storage mounted by you
```

TG2Cloud follows a “select manually, process automatically” model. You choose and forward a file to your private Bot; the VPS then handles queueing, downloading, uploading, verification, and local cleanup. This version does not automatically monitor channels or bulk-import channel history.

## Key Features

- Windows 10/11 GUI deployers with password and SSH private-key login;
- explicit VPS host-key fingerprint confirmation on first connection;
- read-only inspection of CPU, memory, installation disk, Docker storage, inodes, and FUSE;
- balanced and streaming-first storage recommendations based on the actual VPS;
- private-chat authorization restricted to one configured Telegram numeric ID;
- persistent SQLite queue, atomic disk-budget reservations, deduplication, and restart recovery;
- a real shared upload-concurrency window for regular and streaming tasks;
- adaptive concurrency based on CPU, memory, disk, stage throughput, error rate, and queue pressure;
- automatic streaming when a single file exceeds the local task budget;
- CloudDrive2 staging files, safe rename, and final-file revalidation;
- direct writes to reserved final names for OpenList, avoiding unreliable WebDAV MOVE behavior on affected backends;
- remote size verification and local cleanup for both editions;
- preservation of complete local files after regular-mode upload failures;
- persistent pause, bulk retry, progress subscriptions, read-only diagnostics, and orphaned-staging-file inspection;
- deployment preflight, consistent SQLite snapshots, code/config fingerprints, and automatic rollback on failed deployment validation;
- read-only backup inventory and explicit retention—deployment never silently deletes rollback points;
- a non-root Bot container with a read-only root filesystem, no capabilities, and `no-new-privileges`.

## Important Boundaries

- One TG2Cloud instance supports one configured user in a one-to-one private chat with one Bot. Group and channel messages do not create tasks.
- TG2Cloud verifies that the selected WebDAV destination received a file of the same size. It does not integrate with the cloud provider's official completion API.
- The Bot reports “Bot complete” after its workflow finishes. It does not ask for manual confirmation for every file.
- Remote integrity is primarily size-based; content hashes are not guaranteed.
- Streaming mode does not keep a complete VPS copy. An interrupted stream will usually restart from the beginning.
- CloudDrive2 and OpenList caches are not controlled directly by the Bot's local task budget.

## Current Version

TG2Cloud v1.0.2 provides two separate PySide6 editions:

- `TG2Cloud · CloudDrive2`
- `TG2Cloud · OpenList`

They share the stable task core and visual design, while using separate product entry points, storage gateways, deployment resources, and EXE artifacts.

## Requirements

### Recommended Environment

| Item | Baseline recommendation | Batch-use recommendation | Notes |
| --- | --- | --- | --- |
| VPS | 2 vCPU, 4 GB RAM, 50 GB SSD | 4 vCPU, 8 GB RAM, 80–100 GB SSD | The deployer's live probe is authoritative |
| OS | Ubuntu 22.04/24.04 or Debian 12, 64-bit | Same | x86_64 and ARM64 |
| Privileges | root or working sudo | Same | Managed CloudDrive2 requires `/dev/fuse` |
| Network | Access to Telegram, container registries, and the destination | 100 Mbps or faster with sufficient traffic | Public speed tests do not represent cloud-destination throughput |
| Local computer | Windows 10/11, 64-bit | Same | Runs the deployer and SSH tunnel |

The installer enforces roughly 1.8 GB of RAM and at least 8 GB free on the installation filesystem. The 50 GB figure is a recommendation, not a simple hard threshold. The deployer also considers existing downloads, the Docker filesystem, inode availability, and the configured local budget.

### Information You Need

VPS:

- IP address or hostname, SSH port, and SSH username;
- VPS password, or an SSH private key and optional key passphrase;
- sudo password for non-root users, unless passwordless sudo is enabled.

Telegram:

- a Bot Token from `@BotFather`;
- API ID and API Hash from [my.telegram.org](https://my.telegram.org);
- your own Telegram numeric user ID.

Storage gateway:

- choose the CloudDrive2 Edition or OpenList Edition;
- prepare a dedicated WebDAV username and password in that gateway;
- log in, authorize, or mount your cloud storage yourself in CloudDrive2 or OpenList;
- ensure the destination cloud storage has enough free space.

The deployer does not need your cloud-drive account password, cookies, OAuth tokens, CloudDrive2 membership password, Telegram personal-account password, or verification code. A more detailed preparation checklist is available in [the pre-deployment checklist (Chinese)](docs/填写信息清单.md).

## Windows GUI Deployment

### 1. Download or Build the Deployers

Official releases should be downloaded from [GitHub Releases](https://github.com/LuoPoJunZi/TG2Cloud/releases) together with `SHA256SUMS.txt`. You can also build from source in Windows PowerShell:

```powershell
git clone https://github.com/LuoPoJunZi/TG2Cloud.git
cd TG2Cloud
.\build.ps1
```

Build both products or select one:

```powershell
.\build.ps1 -Edition All
.\build.ps1 -Edition CloudDrive2
.\build.ps1 -Edition OpenList
```

Artifacts are written to:

```text
dist/TG2Cloud-CloudDrive2-Deployer.exe
dist/TG2Cloud-OpenList-Deployer.exe
```

Both EXEs use the same PySide6 interface and secure-connection infrastructure, but they do not offer an in-app backend switch. The retired Tkinter/Classic entry points and CMD launchers are no longer built, tested, or released.

`build.ps1` prepares the pinned dependencies from `requirements-build.txt`, checks the Qt GUI runtime, and isolates the DLL search path during packaging so unrelated libraries installed on the build machine cannot contaminate the EXE.

Verify the release SHA-256 before running a deployer. Unsigned, single-file PyInstaller applications may trigger heuristic warnings from some security products.

### 2. Complete the VPS Page

1. Enter the VPS address, SSH port, and username.
2. Select password or SSH private-key authentication.
3. Enter the sudo password if the account is non-root and does not have passwordless sudo.
4. Click **测试 SSH** (Test SSH).
5. On first connection, compare the displayed host-key fingerprint with the fingerprint in your VPS provider's console.

After a successful SSH test, the deployer reads VPS resources and produces storage recommendations for this instance.

### 3. Complete the Telegram Page

Enter the Bot Token, API ID, API Hash, and your Telegram numeric ID. Only that numeric ID can use the Bot in a private chat. Messages from groups or channels are ignored even when sent by the same person.

### 4. Complete the CloudDrive2 Page

This section and steps 5–7 describe the CloudDrive2 Edition. OpenList users should follow [OpenList and Cloud Storage Configuration](#openlist-and-cloud-storage-configuration).

When the deployer manages CloudDrive2 on the same VPS, keep this WebDAV URL:

```text
http://tg2cloud-clouddrive2:19798/dav
```

Complete the storage page as follows:

| Field | Required | Value |
| --- | --- | --- |
| WebDAV URL | Yes | Keep the default internal URL for managed CloudDrive2; do not use the VPS public address |
| WebDAV username | Yes | A dedicated username that you will also create in CloudDrive2 |
| WebDAV password | Yes | The password you will assign to that WebDAV user |
| Subdirectory below the WebDAV root | No | Leave empty when the user's root is already the destination; otherwise enter a relative path |

Do not enter a CloudDrive2 membership password or a cloud-drive account password here. Decide on a WebDAV username and password before deployment, then create the matching WebDAV user in CloudDrive2 after the base environment is ready. The Bot and managed CloudDrive2 communicate over the Docker network.

If you disable **在 VPS 上安装并管理 CloudDrive2 容器** (install and manage CloudDrive2 on this VPS), the Bot uses an existing external CloudDrive2. The WebDAV URL must then be reachable from inside the Bot container.

### 5. Choose a Storage Profile

Review these deployment options:

| Item | Recommendation |
| --- | --- |
| Install and manage CloudDrive2 on this VPS | Keep enabled when CloudDrive2 and the Bot share one VPS |
| Installation directory | Normally keep `/opt/tg2cloud-clouddrive2` |
| Local task budget | Probe the VPS, then apply the balanced or streaming-first recommendation |
| Minimum free disk | Use the recommendation; do not lower it merely to fit more files |
| Time zone | `Asia/Shanghai` is the default for mainland China; adjust explicitly elsewhere |

Source defaults are:

```text
Installation directory: /opt/tg2cloud-clouddrive2
Local task budget: 20 GB
Minimum free disk: 8 GB
Time zone: Asia/Shanghai
```

Available actions:

- **检测 VPS 并推荐** — re-run the read-only VPS probe;
- **应用均衡值** — reserve more space for regular downloads and retained files;
- **应用流式优先值** — reduce complete-file staging for smaller VPS disks.

Recommendations never overwrite defaults silently. Re-run the probe after changing the installation directory or CloudDrive2 management mode. TG2Cloud does not repartition, format, expand, mount, or migrate the Docker data path.

If a probe reports roughly 2 vCPU, 1.9 GB RAM, 33 GB free, and recommends streaming-first `8 GB / 8 GB`, explicitly apply that profile. Do not restore `20 GB / 8 GB` without a new resource assessment.

### 6. Deploy the Base Environment

Click **一键部署基础环境** (Deploy base environment). A normal first deployment may take 5–15 minutes while Docker is installed or checked, the Bot image is built, services are started, and health checks run. Resources are checked again before persistent writes; unsafe conditions stop the deployment.

While dependencies or container images are being downloaded, wait for an explicit success or failure. Do not repeatedly click deploy, network repair, or WebDAV acceptance.

When an installation for the current edition already exists, redeployment preserves the VPS `.env` by default, along with SQLite, `rclone.conf`, downloads, logs, and gateway data. Current form values are applied only after explicitly enabling **使用本页配置覆盖 VPS 当前 .env**. The upgrade builds a candidate in an isolated directory and creates code, configuration, and database rollback points before replacement. v1.0.2 does not provide a general-purpose Restore feature.

### 7. First-Installation Sequence

1. Enter VPS details, test SSH, and verify the host-key fingerprint.
2. Enter the Bot Token, Telegram API ID, API Hash, and your numeric user ID.
3. Enter the planned WebDAV username and password, plus an optional relative destination path.
4. Confirm the CloudDrive2 management mode, probe the VPS, and explicitly apply an appropriate storage profile.
5. Deploy the base environment and wait for success.
6. Open the CloudDrive2 management page, log in yourself, mount your cloud storage, and enable WebDAV.
7. Create a WebDAV user matching the values in step 3, disable read-only mode, and grant read, write, rename, and delete access.
8. Run **WebDAV 验收** and wait for `TG2CLOUD_DESTINATION=OK`.
9. Use **修复 CloudDrive2 网络** only when acceptance fails because of a container-network problem, then run acceptance again.
10. Send a small file to your Bot in a private chat to test the full path.

## CloudDrive2 Configuration

After base deployment, click **打开 CloudDrive2 管理页**. The deployer creates an SSH tunnel and opens:

```text
http://127.0.0.1:19798
```

CloudDrive2's management port is bound only to the VPS loopback interface and is not exposed publicly. The deployer makes a real HTTP request through the tunnel before opening the browser. It automatically replaces a stale tunnel. Local port 19798 is fixed; if another local process owns it, TG2Cloud reports the conflict rather than choosing a random port.

In CloudDrive2:

1. Log in.
2. Add and authenticate your cloud storage.
3. Confirm that the destination can be browsed.
4. Enable WebDAV.
5. Create a dedicated TG2Cloud WebDAV user.
6. Disable read-only mode and grant read, write, rename, and delete access.

Choose one path model. The examples below use 115; substitute the mount path for another provider:

| CloudDrive2 WebDAV user root | Deployer subdirectory | Final example |
| --- | --- | --- |
| `/115open/Telegram` | Empty | `/115open/Telegram/file-name` |
| `/` or a higher directory | `115open/Telegram` | `/115open/Telegram/file-name` |

Do not repeat `115open/Telegram` in both places, or you will create a duplicated nested path.

## OpenList and Cloud Storage Configuration

The OpenList Edition uses `/opt/tg2cloud-openlist`, the `tg2cloud-openlist` container, and the `tg2cloud-openlist-net` network. It can coexist with the CloudDrive2 Edition, but two instances must not continuously use the same Telegram Bot Token because they would compete for updates.

New installations use only TG2Cloud runtime names. A stopped or separate legacy TG115 installation is reported but never adopted, moved, overwritten, stopped, or deleted. An old service occupying fixed port 19798 or 5244 blocks the corresponding installation until you resolve it. Unknown target paths or container-name conflicts also fail closed. See [Migrating from TG115 (Chinese)](docs/MIGRATION_FROM_TG115.md).

First-installation sequence:

1. Enter VPS and Telegram details, test SSH, and apply a suitable storage profile. OpenList defaults to a 20 GB local task budget and 8 GB minimum free disk.
2. The OpenList deployment page generates an initial administrator password. It is masked by default and can be shown, copied, or explicitly regenerated before deployment. It applies only when initializing a brand-new OpenList data directory. Existing instances retain their administrator credentials; the deployer does not reset them automatically.
3. Deploy the base environment. At this stage only OpenList, the Bot, and their internal network must be healthy. Missing cloud mounts or a not-yet-created WebDAV user do not make base deployment fail.
4. Open the OpenList management page. The deployer establishes the fixed tunnel `127.0.0.1:5244 → VPS 127.0.0.1:5244` and opens `http://127.0.0.1:5244`. A local port conflict is reported; no random port is selected.
5. Log in to OpenList and add/authorize your cloud storage, such as 115 Open. Cookies, tokens, OAuth credentials, and login details go only to your own OpenList instance; TG2Cloud does not read or collect them.
6. Create a dedicated regular OpenList user using the exact values shown on the **配置 WebDAV** page. The username, locally generated 28-character random password, and suggested base path can be copied. The password changes only when you explicitly regenerate it during the current session.
7. Grant directory-list, read, create/write, and delete permissions. OpenList permission labels vary by version, but the actual capabilities are required.
8. Run WebDAV acceptance. Authentication, directory access, write, size check, final placement, and cleanup must all succeed, ending with `TG2CLOUD_DESTINATION=OK`.

The recommended WebDAV username for a new OpenList installation is `tg2cloud`. The target subdirectory defaults to empty, so files are written to that user's WebDAV root. To use a subdirectory, enter a relative path such as `Telegram` or `Media/Telegram`. Existing `tg115` users and explicit paths remain compatible and are not silently renamed.

Generated passwords are not saved after the deployer closes. Redeployment preserves the complete VPS `.env` by default. If you explicitly apply all form values, you can additionally choose to preserve the VPS's current WebDAV and administrator settings; those values are merged on the VPS and are never read back to Windows or printed in logs. To replace WebDAV credentials, do not select the preserve-WebDAV option, and make sure OpenList contains the same values.

The OpenList operations sidebar provides status, recent redacted logs, separate Bot/OpenList restart actions, a consistent safety backup, and administrator password recovery. A safety backup briefly stops both services to capture consistent program configuration, SQLite, and OpenList state, then restarts and checks them. Password recovery requires two confirmations; the new password is shown only in the current masked field and is not written to normal logs.

## Real WebDAV Acceptance Test

After configuring the gateway and destination cloud storage, click **WebDAV 验收**. The Bot container uses its actual runtime configuration to:

```text
Generate a random 256-byte file
→ write it to the selected WebDAV gateway
→ verify the remote size
→ CloudDrive2: rename remotely and revalidate
→ OpenList: write directly to the reserved final name (no MOVE)
→ delete the remote and local test files
```

Acceptance passes only when `TG2CLOUD_DESTINATION=OK` appears. This proves that the Bot has the WebDAV capabilities required by its backend, but you should still verify real file size and readability in the cloud provider's official client.

The OpenList UI reports Bot, OpenList service, authentication, target, write, size, final placement, and cleanup as Passed, Failed, Not required, or Not run. A failed step never causes later steps to be marked as passed. Friendly guidance is shown for authentication, path, permission, size, and cleanup errors; raw rclone/HTTP details remain in the redacted log area.

Before batch use, test:

1. a small 5–20 MB file;
2. a regular, locally staged file;
3. a file exceeding the local budget, or a task switched with `/stream`;
4. restart recovery during a test transfer;
5. `/cancel` cleanup on a disposable task.

## Daily Use

1. Select a file you are authorized to save in Telegram.
2. Forward it to a one-to-one private chat with your TG2Cloud Bot.
3. The Bot returns a task number and persists it in the queue.
4. Regular files are fully downloaded to the VPS before upload.
5. A single file exceeding the budget is streamed automatically.
6. CloudDrive2 validates a staging object and renames it; OpenList validates a direct write to a reserved final name.
7. The Bot records cleanup state before deleting the local copy.
8. The Bot reports completion for the selected storage gateway.
9. Check the file in CloudDrive2, OpenList, or the cloud provider's official client as appropriate.

### Task States

| State | Meaning |
| --- | --- |
| Queued | Persisted and waiting for resources and a healthy destination |
| Downloading from Telegram | Regular mode is writing a temporary VPS file |
| Streaming from Telegram to the destination | Data is entering the upload pipeline; this is not the cloud provider's ingest progress |
| Writing to the destination | A complete local file is being uploaded over WebDAV |
| Destination accepted; cleaning local file | Remote size was revalidated, but local cleanup is not complete |
| Bot transfer complete | The Bot workflow ended; this is not an official-provider integrity result |

## Bot Commands

| Command | Purpose |
| --- | --- |
| `/start`, `/help` | Show help |
| `/queue [page]` | Show five recent tasks per page |
| `/status`, `/performance` | Show the same single-page status, performance, and task summary |
| `/doctor` | Read-only diagnostics; does not create a remote test file |
| `/task <id>` | Show one task |
| `/watch <id>` | Edit one message every five seconds with progress; subscribe again after restart |
| `/pause`, `/resume` | Persistently pause or resume new scheduling without interrupting active transfers |
| `/retry <id>` | Retry one failed task |
| `/retry all` | Requeue up to 100 retryable tasks |
| `/cancel <id>` | Remove and recheck this task's remote paths before deleting the local copy |
| `/stream <id>` | Switch a queued or download-failed task to streaming mode |
| `/orphans` | Read-only scan for suspected `.uploading-*` staging objects |
| `/orphans clean` | Request a one-time confirmation code, then explicitly clean orphaned staging objects |

### Native Telegram Command Menu

At startup, the Bot registers a native command menu. The current UI uses these Chinese descriptions:

```text
/status   查看系统状态
/queue    查看最近任务
/pause    暂停任务调度
/resume   恢复任务调度
/doctor   运行系统诊断
/orphans  检查临时文件
/help     查看使用帮助
```

New responses are text-only and do not attach inline action buttons. Parameter commands can be typed manually, for example `/queue 2`, `/task <id>`, `/retry <id>`, `/stream <id>`, and `/cancel <id>`. Cancellation fails closed: the local copy is removed only after all recorded remote paths are confirmed absent.

A command-menu registration failure does not stop the Bot; all text commands remain available and the failure is logged.

## VPS Operations and Upgrades

CloudDrive2 installs to `/opt/tg2cloud-clouddrive2`. After connecting over SSH:

| Command | Purpose |
| --- | --- |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh status` | Show container status |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh logs` | Show recent Bot logs |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh check` | Check configuration, code fingerprints, and heartbeats |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh verify` | Run real WebDAV write/finalize/delete acceptance |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh restart` | Restart only the Bot without applying config changes |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh stop` | Stop the Bot |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh start` | Start and wait for Bot health |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh update` | Rebuild from the installed payload; does not download code or replace `.env` |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh backups` | Read-only backup inventory |
| `sudo /opt/tg2cloud-clouddrive2/manage.sh prune-backups 5` | Explicitly keep the newest five entries of each rollback type |

OpenList uses `/opt/tg2cloud-openlist/manage.sh`. Its `update` also pulls the OpenList image pinned by the current Compose file and validates both services. Each edition manages only its own TG2Cloud path and containers; legacy TG115 is reported separately and is not treated as an upgrade target.

### Applying Configuration

Place the new config outside the installation directory, then run:

```bash
sudo /opt/tg2cloud-clouddrive2/manage.sh apply-config /absolute/new-config.env
sudo /opt/tg2cloud-clouddrive2/manage.sh check
sudo /opt/tg2cloud-clouddrive2/manage.sh verify
```

`apply-config` backs up and validates the candidate before recreating the Bot; on failure it restores the old configuration. Finish or resolve existing queue items before changing the destination account or path.

### Upgrading

The recommended upgrade path is to run **一键部署基础环境** again with a newer Windows deployer. `manage.sh update` only uses the payload already installed on the VPS; it does not fetch new code from GitHub.

CloudDrive2 has no manual backup button. Its redeployment protection includes program files, `.env`, rclone configuration, and a consistent SQLite snapshot when available, but excludes downloads, logs, and CloudDrive2 state. OpenList's manual safety backup includes configuration, SQLite, and initialized OpenList state, excluding temporary files, logs, downloads, and cloud data.

Backups contain secrets. Directories are mode `700` and files are set to `600` where possible. Never upload them publicly.

CloudDrive2 upgrade backups are stored under `/opt/tg2cloud-clouddrive2-backups`; OpenList upgrade/manual backups are under `/opt/tg2cloud-openlist-backups`. Deployment reports usage and warns above 5 GB but does not delete rollback points automatically. `prune-backups` only removes recognized generated files inside the current edition's backup path. v1.0.2 does not provide a general Restore or Uninstall function.

## Troubleshooting

### SSH Connection Fails

Check the VPS address, port, username, password/private key, and provider firewall. On first connection, verify the host-key fingerprint. Never accept an unexplained fingerprint change.

`Host key for server ... does not match` means the stored SSH host key differs from the server's current key. This can follow a VPS reinstall, snapshot restore, regenerated SSH host keys, or IP reassignment—but can also indicate a wrong server or a man-in-the-middle attack.

Verify the current key through the provider console or VNC:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
sudo ssh-keygen -lf /etc/ssh/ssh_host_rsa_key.pub -E sha256
```

If the new fingerprint is unexplained or does not match, cancel. If it matches exactly, use the deployer's update-and-reconnect action. It replaces only the record for that host and port and retries once. Authentication failures after that point are separate username/password/key problems.

Known hosts are stored in `%APPDATA%\TG2Cloud-Deployer\known_hosts`. Legacy `%APPDATA%\TG115-Deployer\known_hosts` is not imported silently.

### `/dev/fuse` Is Missing

Managed CloudDrive2 Docker mounts require FUSE. Enable it in the VPS control panel or ask the provider whether the virtualization platform exposes `/dev/fuse`.

### Tasks Stay Queued

Check, in order:

1. whether `/status` shows a fresh resource sample;
2. whether the disk is near the safety threshold;
3. whether the storage gateway is logged in and the target is mounted;
4. whether WebDAV is enabled and the user is writable;
5. whether username, password, and target path match;
6. `sudo /opt/tg2cloud-clouddrive2/manage.sh verify`.

### `401 Unauthorized`

The running Bot's WebDAV credentials usually do not match the gateway user. Changing a form value does not change the VPS until you explicitly redeploy with form values or use `apply-config`. A plain restart does not apply new configuration. Run `check` and `verify` afterward instead of relying on old log entries.

### `429 Too Many Requests` in OpenList

Stop repeated acceptance attempts. A 429 does not prove that credentials are wrong and does not require another deployment. Allow the rate limit to clear, check the OpenList mount and upstream-provider state, then run acceptance once. Repeated clicks and periodic WebDAV probes can prolong the limit.

### Management Page Shows `ERR_EMPTY_RESPONSE`

The deployer validates the SSH tunnel before opening a browser. If SSH TCP forwarding is disabled, review `AllowTcpForwarding` and any `PermitOpen` rule for `127.0.0.1:19798` or `127.0.0.1:5244`. Keep the current SSH session open, run `sshd -t`, and reload safely after any server-side change.

A tunnel error and a WebDAV 401 are different. Network repair cannot correct a username/password mismatch.

### `lookup tg2cloud-clouddrive2`

Use **修复 CloudDrive2 网络**. It preserves CloudDrive2 login/mount data, repairs the Docker network alias, and then runs real WebDAV acceptance. The script refuses to modify an unknown process occupying fixed port 19798.

### Bot Is Healthy but Upload Still Fails

Container health checks scheduler/resource heartbeats, not WebDAV writability or official cloud ingestion. `manage.sh verify` performs the real WebDAV test.

### A File Exceeds the Local Budget

The task automatically uses streaming mode; do not raise the budget to the file size. Streaming still shares the upload window and obeys the real disk safety threshold. Use `/stream <id>` for a queued regular task when appropriate.

### Disk Looks Free but Deployment Is Refused

Docker data and `/opt/tg2cloud-*` may be on different filesystems. The deployer checks installation storage, Docker storage, existing downloads, backup usage, the reserve threshold, and inodes. Any unsafe critical filesystem stops the deployment.

### Do I Have to Confirm Every File?

No. After remote size verification, the Bot reports completion without asking for per-file manual confirmation. Historical compatibility states are merged into the same completed count.

## Security

- Never publish VPS passwords, SSH private keys, Bot Tokens, API Hashes, WebDAV passwords, cloud credentials, logs, databases, or Telegram sessions in a repository, Issue, screenshot, or chat.
- The deployer does not save form passwords. It stores only SSH host keys that you explicitly confirm.
- Base64 and `rclone obscure` are encoding/obfuscation, not encryption. VPS root can read service configuration.
- CloudDrive2 needs elevated container privileges for FUSE. Prefer a dedicated VPS that does not host wallets, databases, or other critical workloads.
- CloudDrive2 management binds to `127.0.0.1`; access it through the deployer's SSH tunnel.
- OpenList management also binds to `127.0.0.1:5244`. Cloud authorization occurs directly in your own OpenList; TG2Cloud has no credential telemetry or third-party callback.
- The Bot container uses UID/GID 10001, a read-only root filesystem, `no-new-privileges`, and no Linux capabilities.
- Official release artifacts include SHA-256. Do not run an EXE, script, or image whose origin and version cannot be verified.

See the [Security Policy](SECURITY.md) and [Third-Party Components (Chinese)](docs/第三方组件说明.md).

## Local Development and Testing

### Repository Layout

```text
installer.py                 shared PySide6 UI and SSH/deployment backend
installer_clouddrive2.py     CloudDrive2 PySide6 product entry point
installer_openlist.py        OpenList PySide6 product entry point
deployer_products.py         immutable product IDs and payload manifests
vps_resources.py             VPS resource probe and recommendations
payload_clouddrive2/         CloudDrive2 resources and shared Bot runtime
payload_clouddrive2/app/     Bot scheduler, queue, WebDAV/rclone adapters
payload_openlist/            OpenList-specific Compose/install/manage scripts
tests/                       unit, scenario, deployment, and WebDAV integration tests
```

### Full Python Regression Suite

```powershell
uv run --with-requirements requirements-build.txt `
  --with-requirements payload_clouddrive2/requirements.txt `
  python -m unittest discover -s tests -v
```

### Static and Dependency Checks

```powershell
uv run --with ruff==0.16.0 ruff check installer.py installer_clouddrive2.py installer_openlist.py deployer_products.py vps_resources.py payload_clouddrive2/app tests
uv run --with bandit==1.9.4 bandit -q -r payload_clouddrive2/app installer.py installer_clouddrive2.py installer_openlist.py deployer_products.py vps_resources.py
uv run --with pip-audit==2.10.1 pip-audit -r payload_clouddrive2/requirements.txt
uv run --with pip-audit==2.10.1 pip-audit -r requirements-build.txt
```

CI also runs ShellCheck, Compose validation, Python 3.12 regression, and a Bot image build on Linux. Windows CI builds and self-tests both PySide6 deployers. Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing.

GitHub forks may require Actions to be enabled manually before workflows run. This repository supports pushes to `main`, pull requests, and the Actions page's **Run workflow** control. See [GitHub's documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflows-in-forked-repositories).

## More Documentation

- [Beginner's Guide (Chinese)](docs/README-小白使用说明.md)
- [Pre-deployment Information Checklist (Chinese)](docs/填写信息清单.md)
- [Migrating from TG115 (Chinese)](docs/MIGRATION_FROM_TG115.md)
- [Brand Guide](docs/development/BRAND-GUIDE.md)
- [Third-Party Components (Chinese)](docs/第三方组件说明.md)
- [Changelog](CHANGELOG.md)
- [Release Notes](RELEASE_NOTES.md)

## Acknowledgements and Project Origin

Thanks to **whyhhh20** for creating and publishing TG115:

- Original repository: [whyhhh20/TG115](https://github.com/whyhhh20/TG115)

TG2Cloud evolved from that project, retains the MIT license, original copyright, and required attribution, and continues to improve the reliability, deployment safety, and operational experience of the Telegram → rclone → CloudDrive2/OpenList → user-owned-cloud path.

Thanks also to Telethon, rclone, Docker, Paramiko, and the other open-source projects involved, and to CloudDrive2 for its WebDAV and cloud-mount features. Each third-party component remains subject to its own license and terms.

## License and Disclaimer

This project is licensed under the [MIT License](LICENSE).

TG2Cloud is not affiliated with, authorized by, or officially partnered with Telegram, CloudDrive2, OpenList, any cloud-storage provider, or their operators. Users are responsible for evaluating account, data, network, VPS privilege, and third-party closed-source component risks.
