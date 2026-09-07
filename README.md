# 司印云打印 MCP Server

将本地文档上传到司印云打印系统打印队列的标准 MCP Server，供 CodeBuddy、Claude Desktop 等 AI client 调用。

## 特性

- 标准 MCP 协议，工具化接口，AI 可用自然语言驱动打印
- 默认 **stdio** 传输，服务跑在用户本机，天然可访问内网司印服务器
- 也支持 **streamable-http / sse**，便于内网集中部署
- 服务器地址、账号、solutionkey、打印机队列全部走环境变量或工具参数，**不硬编码内网信息**
- 自动根据文件后缀识别 MIME 类型，支持 Word / Excel / PPT / PDF / 图片

## 安装

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 配置

把参数写进 `.env` 文件（支持 `#` 注释，每家司印参数不同，逐项确认）：

```bash
cp .env.example .env
# 然后用编辑器打开 .env，把值改成你自己司印环境的参数
```

`server.py` 启动时会自动读取同目录下的 `.env`。必填项：

| 变量 | 说明 |
|------|------|
| `SIYIN_HOST` | 司印服务器 IP（每家不同） |
| `SIYIN_PORT` | 端口（默认 8110） |
| `SIYIN_SOLUTIONKEY` | 司印分配的解决方案密钥（每家不同） |
| `SIYIN_PRINTER_QUEUE` | 打印机队列 ID（每家不同） |
| `SIYIN_LOGIN_ACCOUNT` | 登录账号 |

本服务为**免密打印**（需司印后台开启「不校验密码」），无需配置密码。

> 为什么用 `.env` 而不是写在 `mcp.json`？因为 JSON 不支持注释，而每家司印的参数都不同，`.env` 能带注释、易维护。每个客户只需维护自己的 `.env`。

## 运行

### 方式一：stdio（本地 AI client，推荐内网场景）

```bash
python server.py
```

CodeBuddy / Claude Desktop / WorkBuddy 配置示例（只需 command + args，参数在 .env 里）：

```json
{
  "mcpServers": {
    "siyin-cloud-print": {
      "command": "python",
      "args": ["/绝对路径/司印云打印MCP/server.py"]
    }
  }
}
```

### 方式二：streamable-http / sse（内网集中部署）

```bash
# streamable-http（推荐，端点 /mcp）
python server.py --transport streamable-http --host 0.0.0.0 --port 9000

# sse（端点 /sse）
python server.py --transport sse --host 0.0.0.0 --port 9000
```

client 侧配置为 streamable-http 地址 `http://内网IP:9000/mcp`（SSE 则用 `/sse`）。

> 端口别用 8110，那通常是司印服务自己的端口；换个空闲端口如 9000。

## 工具

### `upload_document`

上传文档到打印队列。

| 参数 | 说明 |
|------|------|
| `file_path` | 本地文件绝对路径（必填） |
| `doc_name` | 文档显示名，默认取文件名 |
| `color` | `Color` 彩色 / `Mono` 黑白 |
| `copy` | 份数（字符串） |
| `duplex` | `1` 单面 / `2` 短边翻转 / `3` 长边翻转 |
| `paper_size` | A3 / A4 / A5 等（仅图片/PDF 生效） |
| `collate` | `0` 不分页 / `1` 分页 |

连接参数（`protocol`/`host`/`port`/`uri`/`login_account`/`login_domain`/`printer_queue`/`solutionkey`）不传时从环境变量 `SIYIN_*` 读取。

### `check_server`

探测司印服务器连通性，不上传文件。

## 关于腾讯云 MCP 广场上架

本服务默认面向**内网部署**（接口在 `192.168.x` 内网网段）。上架腾讯云开发者 MCP 广场时：

1. 上架申请仅面向**企业级** MCP 开发者，需填写官方入驻申请表；
2. 广场默认「云托管」部署，但内网接口无法云托管，**请在申请/企微沟通时明确告知「仅支持本地/内网部署」**；
3. 建议以 stdio 本地运行形态上架，附 README、使用教程、应用案例。

## 项目结构

```
司印云打印MCP/
├── server.py          # MCP Server 主程序（stdio / http，自动读取 .env）
├── requirements.txt   # Python 依赖
├── .env.example       # 配置模板（带注释，复制为 .env 使用）
├── .env               # 本机真实配置（勿提交）
└── README.md          # 本文档
```
