# 团队协作与提交规范

## 1. 开始工作前

```powershell
git status -sb
git pull --rebase
```

先确认工作区是否有队友未提交的修改。不要使用 `git reset --hard`、`git checkout --` 覆盖他人工作；需要清理时先沟通并保留可恢复副本。

## 2. 分支

从最新 `main` 创建短生命周期分支：

```text
feature/<short-name>   新功能
fix/<short-name>       缺陷修复
docs/<short-name>      文档
refactor/<short-name>  重构
```

一个分支尽量只解决一个主题。不要把格式化、依赖升级和业务改动混在同一个提交中。

## 3. 提交信息

统一使用简短、可检索的类型前缀：

```text
feat: add subtitle task status
fix: handle duplicate video upload
docs: update local setup guide
refactor: split video task service
test: cover transcode permission
chore: update frontend lockfile
```

已有历史提交不要求重写；从新提交开始遵守即可。

## 4. 代码边界

### 后端

- View/ViewSet 负责 HTTP 编排，Serializer 负责输入/输出校验，模型负责数据约束。
- 长耗时的视频、OCR、语音和 AI 工作放入 Celery task，不要阻塞请求。
- 权限必须在后端校验；前端隐藏按钮不是授权机制。
- 新增或修改数据库字段必须包含迁移文件。
- 日志记录任务 ID、业务 ID 和失败原因，不记录密码、token、API Key 或私钥。

### 前端

- API 请求集中放在 `frontend/video-ui/src/api/`，不要在多个页面复制请求逻辑。
- 页面只负责展示和交互，复杂状态放入现有 store 或组合式逻辑。
- 修改 API 字段时同时检查 loading、空数据、错误和重复提交状态。
- 不要提交 `dist/`、`dist-electron/` 或手工修改的 `node_modules/`。

## 5. 提交前检查

```powershell
git diff --check

Push-Location backend\video
..\venv\Scripts\python.exe manage.py check
Pop-Location

Push-Location frontend\video-ui
npm run build
Pop-Location
```

后端有数据库依赖的测试在数据库权限准备好后运行：

```powershell
Push-Location backend\video
..\venv\Scripts\python.exe manage.py test
Pop-Location
```

如果检查失败，提交说明中要写清楚失败命令、错误位置和是否与本次改动有关。当前基线的前端构建已知会被搜索页重复 `response` 声明阻断，修复后再把构建标为通过。

## 6. Pull Request / 合并说明

PR 至少包含：

- 背景和改动目的
- 影响的后端接口、数据库迁移、异步任务或前端页面
- 本地验证命令和结果
- 配置、迁移、回滚注意事项
- 截图或接口示例（不包含真实账号、token 和密钥）

合并前确认没有 `.env`、凭据、日志、媒体文件、模型文件和构建产物。依赖变更必须说明原因、运行时影响和锁文件变化。
