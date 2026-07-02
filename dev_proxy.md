# MarketANA

MarketANA 是一个前后端分离的期货市场文章分析项目。当前仓库已完成 pn01 技术基线：FastAPI 后端骨架、Vue 3 + Vite 前端骨架、MySQL 连接基础、定时任务接入、统一配置、统一日志、统一响应格式和基础测试。

## 项目结构

```text
back_end/app/
  api/             FastAPI 路由
  core/            配置、数据库、日志、响应、异常、状态码
  models/          SQLAlchemy 模型，后续阶段继续补充
  repositories/    数据访问层
  services/        业务服务和外部服务客户端
  tasks/           定时任务和后台任务
front_end/         Vue 3 + Vite 前端项目
tests/             后端基础测试
```

## 环境要求

推荐所有成员使用 WSL2 + Ubuntu 统一开发环境，减少 Windows、macOS 和 Linux 之间的依赖差异。

- Windows 10/11 + WSL2 + Ubuntu 22.04 或 24.04
- Python 3.11
- uv
- Node.js `^22.18.0` 或 `>=24.12.0`
- npm
- MySQL 8.x，当前阶段未配置数据库也可以先运行基础测试

## WSL 安装

在 Windows PowerShell 中以管理员身份执行：

```powershell
wsl --install
```

如果需要指定 Ubuntu 版本：

```powershell
wsl --install -d Ubuntu-22.04
```

安装完成后重启电脑，打开 Ubuntu，创建 Linux 用户。进入 WSL 后更新系统依赖：

```sh
sudo apt update
sudo apt upgrade -y
sudo apt install -y git curl ca-certificates build-essential
```

确认 WSL 版本：

```powershell
wsl -l -v
```

如果 Ubuntu 不是 WSL2，可在 PowerShell 中执行：

```powershell
wsl --set-version Ubuntu-22.04 2
```

建议把代码放在 WSL 的 Linux 文件系统中，例如 `~/projects/marketANA`，不要放在 `/mnt/c/...` 下，以免文件监听和依赖安装变慢。

## 获取代码

```sh
git clone <repo-url> marketANA
cd marketANA
```

如果已经拿到代码，先同步最新版本：

```sh
git pull
```

## uv 安装与后端依赖对齐

安装 uv：

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后重新加载 shell：

```sh
source ~/.bashrc
```

确认 uv 可用：

```sh
uv --version
```

安装 Python 3.11：

```sh
uv python install 3.11
```

按 `uv.lock` 对齐后端依赖：

```sh
uv sync --frozen
```

如果刚修改过 `pyproject.toml` 并需要更新锁文件，由负责依赖变更的成员执行：

```sh
uv lock
uv sync
```

日常开发中优先使用 `uv sync --frozen`，这样每个人安装到的后端依赖版本一致。

## Node.js 与前端依赖对齐

前端项目要求 Node.js `^22.18.0` 或 `>=24.12.0`。推荐使用 nvm 安装 Node.js。

安装 nvm：

```sh
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
```

安装并使用 Node.js 24 LTS：

```sh
nvm install 24
nvm use 24
node -v
npm -v
```

按 `front_end/package-lock.json` 对齐前端依赖：

```sh
cd front_end
npm ci
cd ..
```

日常开发中优先使用 `npm ci`，不要随意删除 `package-lock.json`。只有在确实新增或升级依赖时，才使用 `npm install <package>` 并提交更新后的 `package.json` 和 `package-lock.json`。

## 配置文件

复制 `.env.example` 为本地配置文件：

```sh
cp .env.example .env
```

`.env` 已被 Git 忽略，不要提交真实密钥和本地数据库密码。

重要配置项：

- `DATABASE_URL`：MySQL SQLAlchemy 连接地址，例如 `mysql+pymysql://user:password@127.0.0.1:3306/marketana?charset=utf8mb4`
- `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`：预留给后续大模型模块
- `LLM_TIMEOUT_SECONDS`：大模型调用超时时间，默认 `30`
- `TASK_BATCH_SIZE`：调度批量大小，默认 `20`
- `RULE_CONFIDENCE_THRESHOLD`：规则识别置信度阈值，默认 `0.7`
- `SCHEDULER_POLL_INTERVAL_SECONDS`：调度轮询间隔，默认 `300`
- `LOG_LEVEL`：后端日志级别，默认 `INFO`

当前 pn01 阶段未配置 MySQL 也可以运行健康检查和基础测试。配置了有效 `DATABASE_URL` 后，健康检查中的 `database` 会从 `unconfigured` 变为 `ok`。

## 后端启动

后端使用 Python 3.11 + FastAPI + uv。

```sh
uv run uvicorn back_end.app.main:app --reload
```

健康检查：

```sh
curl http://127.0.0.1:8000/health
```

预期响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok",
    "database": "unconfigured"
  }
}
```

## 前端启动

前端依赖位于 `front_end` 目录。

```sh
cd front_end
npm run dev
```

Vite 默认会输出本地访问地址，通常是：

```text
http://127.0.0.1:5173/
```

也可以在仓库根目录使用脚本：

```sh
npm run frontend:dev
```

## 构建与类型检查

前端：

```sh
cd front_end
npm run build
npm run type-check
```

或在仓库根目录执行：

```sh
npm run frontend:build
npm run frontend:type-check
```

后端基础测试：

```sh
uv run pytest
```

当前 pn01 测试覆盖：

- `/health` 响应格式
- 文章处理状态常量：`-1, 0, 1, 2, 3, 4, 5`
- 默认配置加载
- 未配置 MySQL 时的数据库健康状态

## 依赖变更规范

后端新增依赖：

```sh
uv add <package>
uv lock
uv sync
uv run pytest
```

提交时包含：

- `pyproject.toml`
- `uv.lock`

前端新增依赖：

```sh
cd front_end
npm install <package>
npm run build
npm run type-check
```

提交时包含：

- `front_end/package.json`
- `front_end/package-lock.json`

团队成员同步依赖时执行：

```sh
uv sync --frozen
cd front_end
npm ci
```

## 常见问题

### uv 命令找不到

先重新加载 shell：

```sh
source ~/.bashrc
```

如果仍然找不到，确认 `~/.local/bin` 在 `PATH` 中：

```sh
echo $PATH
```

### npm ci 失败

先确认 Node.js 版本符合前端要求：

```sh
node -v
```

如果版本不符合，使用 nvm 切换：

```sh
nvm install 24
nvm use 24
```

### 健康检查中 database 是 unconfigured

这是未配置 `DATABASE_URL` 时的正常结果。复制 `.env.example` 为 `.env`，并填入有效 MySQL 连接后重启后端即可。

## 文章处理状态

后端状态常量如下：

- `-1`：处理失败
- `0`：未处理
- `1`：解析完成
- `2`：清洗完成
- `3`：规则识别完成
- `4`：LLM 推理完成
- `5`：已入库
