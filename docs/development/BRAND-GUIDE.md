# TG2Cloud Brand Guide — v1.0.0

## 1. 品牌资源状态

TG2Cloud 的正式 Logo、Icon 等资源**已经制作完成**。

正式资源目录：

```text
assets/brand/
```

该目录是 TG2Cloud 品牌资源的：

> Source of Truth

开发与发布过程应**使用这些资源**，而不是重新设计 Logo。

---

## 2. 预期资源结构

以仓库实际内容为准，预期类似：

```text
assets/brand/
├── tg2cloud-logo.svg
├── tg2cloud-icon.svg
├── tg2cloud-icon.png
├── tg2cloud-icon-32.png
├── tg2cloud-icon-64.png
├── tg2cloud-icon-128.png
├── tg2cloud-icon-256.png
├── tg2cloud-icon-512.png
├── tg2cloud.ico
├── tg2cloud-logo-preview.png
└── README.md
```

不要因为某个文件名和上面略有差异就擅自重新生成整套资源。

---

## 3. 正式名称

```text
TG2Cloud
```

大小写固定。

不要使用：

```text
TG2CLOUD
Tg2Cloud
TG 2 Cloud
```

---

## 4. 标语

正式英文方向：

```text
From Telegram to Your Cloud
```

核心表达：

```text
Telegram
→ TG2Cloud
→ Your Cloud
```

---

## 5. 品牌定位

TG2Cloud 是：

> 将 Telegram 中提交的文件自动转存到用户自有云存储的自托管工具。

TG2Cloud 不绑定 115。

CloudDrive2 和 OpenList 都是：

```text
Storage Gateway
```

用户可以在其中挂载不同的云存储。

---

## 6. Edition

两个 Edition：

```text
TG2Cloud · CloudDrive2
TG2Cloud · OpenList
```

正式 EXE：

```text
TG2Cloud-CloudDrive2-Deployer.exe
TG2Cloud-OpenList-Deployer.exe
```

两个 Edition 使用同一个主 Logo。

区别通过：

```text
CloudDrive2 Edition
OpenList Edition
```

文字表达。

---

## 7. 现有 Logo 视觉方向

当前正式 Logo 的视觉概念：

```text
云朵
+
纸飞机
+
环绕/上行传输轨迹
```

表达：

```text
Telegram 文件 → 用户的云端
```

整体视觉：

- 蓝色为主；
- 青色/青绿色辅助；
- 白色纸飞机；
- 现代科技风；
- 清晰；
- 适合 Windows / PySide6 / GitHub。

---

## 8. 正确的资源使用

### Windows EXE

优先：

```text
assets/brand/tg2cloud.ico
```

用于：

```text
TG2Cloud-CloudDrive2-Deployer.exe
TG2Cloud-OpenList-Deployer.exe
```

---

### PySide6

窗口图标、首页、About 等从：

```text
assets/brand/
```

选择适合的：

```text
tg2cloud-icon.svg
tg2cloud-icon-256.png
tg2cloud-icon-512.png
```

不要复制一套资源到多个目录造成后续版本不一致。

---

### README / GitHub

优先：

```text
assets/brand/tg2cloud-logo.svg
```

如果平台显示 SVG 有问题：

```text
assets/brand/tg2cloud-logo-preview.png
```

---

### 小尺寸

任务栏、菜单或小图标：

```text
tg2cloud-icon-32.png
tg2cloud-icon-64.png
```

---

## 9. 如果缺少尺寸

只允许：

```text
现有 SVG/PNG
↓
等比例派生
↓
新增尺寸
```

不允许：

```text
重新设计
重新生成另一个 Logo
修改主体造型
```

派生资源必须记录在：

```text
assets/brand/README.md
以及对应的变更说明
```

---

## 10. 禁止事项

开发和发布过程中不得：

- 重新设计 TG2Cloud 主 Logo；
- 调用图像生成工具生成另一版；
- 用 Telegram 官方 Logo 替代；
- 用 CloudDrive2 Logo 替代；
- 用 OpenList Logo 替代；
- 用 115 Logo 替代；
- 拼接多个第三方 Logo 作为 TG2Cloud Logo；
- 覆盖 `assets/brand/` 里的正式资源；
- 为 CloudDrive2 / OpenList 各制作一套不同主品牌；
- 把 115 写进 TG2Cloud 主 Logo。

---

## 11. 品牌迁移范围

需要把正式 TG2Cloud 资源应用到：

- PySide6 Window Icon；
- EXE Icon；
- 首页；
- About；
- README；
- 文档；
- Release；
- GitHub；
- Bot 用户可见品牌文案；
- 安装器标题；
- 部署日志中的产品名称。

---

## 12. TG115 保留场景

以下位置仍然可以保留 TG115：

- LICENSE；
- NOTICE；
- 原作者版权；
- 上游致谢；
- `docs/MIGRATION_FROM_TG115.md`；
- 必要的兼容代码说明。

不要为了品牌统一删除代码血缘信息。

---

## 13. 品牌验收

TG2Cloud v1.0.0 发布前确认：

```text
✅ assets/brand/ 是正式品牌唯一来源
✅ 两个 EXE 使用 tg2cloud.ico
✅ 两个 PySide6 使用同一主品牌
✅ README 使用正式 Logo
✅ About 使用正式 Logo
✅ 用户可见位置 TG2Cloud 名称一致
✅ 没有错误重新生成另一套 Logo
✅ 没有把 115 作为唯一项目定位
```
