# Alembic 嵌入式迁移与日志（关键改动备忘）

## 背景

应用在启动时通过 [`app/db/bootstrap.py`](../backend/app/db/bootstrap.py) 调用 `alembic.command.upgrade`，会加载 [`alembic/env.py`](../backend/alembic/env.py)。原先 `env.py` 无条件执行 `logging.config.fileConfig(alembic.ini)`，而 [`alembic.ini`](../backend/alembic.ini) 中 `[logger_root]` 曾设为 `WARN`。

这会导致：**根 logger 的级别/处理器被改掉**，同一进程内的 **`uvicorn.access`（每条 HTTP 访问日志）** 以及应用里大量 **`logger.info`** 不再输出，看起来像「服务卡住」或「没有请求日志」，实则为日志配置冲突。

## 做法（方案 A + C）

1. **嵌入式迁移**（`python -m app.db.bootstrap`、以及 `main.py` 的 `on_startup` 里调用的 `db_bootstrap()`）  
   - 在 `bootstrap.main()` 进入时设置环境变量 **`ALEMBIC_EMBEDDED=1`**，在 **`finally` 中 `pop` 掉**。  
   - `env.py` 检测到该标志时：**不调用 `fileConfig`**，仅为 **`alembic` logger** 挂载窄范围 handler（`propagate=False`），并把 **`sqlalchemy.engine`** 设为 `WARNING`，避免 SQL 刷屏。

2. **CLI 单独跑 Alembic**（如 `alembic upgrade head`）  
   - 不设 `ALEMBIC_EMBEDDED`，仍使用 **`fileConfig`**；并传入 **`disable_existing_loggers=False`**，减轻对已有 logger 的冲击。

3. **`alembic.ini`**  
   - `[logger_root]` 从 **`WARN` 调整为 `INFO`**，仅影响 **CLI + fileConfig** 路径，便于保留迁移过程可见度。

## 注意

- **勿**在本地 shell **长期保留** `ALEMBIC_EMBEDDED=1` 再跑 `alembic` CLI，否则会误走嵌入式分支。正常只由 bootstrap 设置并在结束时清除。  
- 生产若不希望启动时跑迁移，仍可使用已有 **`FIXMEAPP_SKIP_STARTUP_BOOTSTRAP`**，与本文日志改动相互独立。

## 相关文件

| 文件 | 作用 |
|------|------|
| [`backend/app/db/bootstrap.py`](../backend/app/db/bootstrap.py) | 设置/清除 `ALEMBIC_EMBEDDED` |
| [`backend/alembic/env.py`](../backend/alembic/env.py) | 嵌入式 vs CLI 的 logging 分支 |
| [`backend/alembic.ini`](../backend/alembic.ini) | CLI 路径下 root 日志级别 |

---

*记录日期：与「嵌入式迁移不调用 fileConfig」合入同一时期。*
