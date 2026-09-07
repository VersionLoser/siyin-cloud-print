#!/usr/bin/env python3
"""司印云打印 MCP Server

把本地文档上传到司印云打印系统的打印队列。

设计目标：
- 标准 MCP Server，可被 CodeBuddy / Claude Desktop 等 AI client 直接调用
- 默认 stdio 传输：服务跑在用户本机，天然能访问内网司印服务器
- 也支持 streamable-http / sse，供内网集中部署
- 服务器地址、账号、solutionkey、打印机队列全部通过环境变量或工具参数传入，
  不硬编码任何内网信息，方便复用到任意司印环境

用法：
    # stdio（默认，本地 AI client 用）
    python server.py

    # 内网集中部署（HTTP）
    python server.py --transport streamable-http --host 0.0.0.0 --port 8110
"""

import hashlib
import json
import logging
import os
import sys
import time
from typing import Optional

import requests
import urllib3
from mcp.server.fastmcp import FastMCP

# 自动加载 server.py 同目录下的 .env 文件（带 # 注释的配置），
# 让每家司印客户只需改自己的 .env，不用动代码或 mcp.json 的 env。
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:  # 未安装 python-dotenv 时忽略，仍可用环境变量
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 司印服务器返回的 Content-Type 头不规范，会触发 urllib3 的 header 解析告警；
# 该告警无害（响应体仍可正常解析），这里静默掉，避免污染 MCP 的 stdio 输出。
logging.getLogger("urllib3").setLevel(logging.ERROR)

mcp = FastMCP("siyin-cloud-print")

ENV_PREFIX = "SIYIN_"

MIME_MAP = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(ENV_PREFIX + name, default)


def _mime(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    return MIME_MAP.get(ext, "application/octet-stream")


def _sign(uri: str, metadata_str: str, solutionkey: str, timestamp: str) -> str:
    source = uri + metadata_str + solutionkey + timestamp
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def _resolve(provided, env_key: str, default=""):
    """优先用工具参数，其次环境变量，最后默认值。"""
    if provided is not None and provided != "":
        return provided
    return _env(env_key, default)


def _do_upload(
    file_path: str,
    doc_name: str,
    jobset: dict,
    protocol: str,
    host: str,
    port: int,
    uri: str,
    login_account: str,
    login_domain: str,
    printer_queue: str,
    release_code_print: str,
    callback_url: str,
    solutionkey: str,
) -> dict:
    """核心上传逻辑，返回 {ok, jobId | error}。"""

    if not os.path.exists(file_path):
        return {"ok": False, "error": f"文件不存在：{file_path}"}

    jobset_obj = {
        "color": jobset.get("color", "Color"),
        "copy": str(jobset.get("copy", "1")),
        "duplex": str(jobset.get("duplex", "3")),
        "paperSize": jobset.get("paperSize", "A4"),
        "collate": str(jobset.get("collate", "0")),
        "range": jobset.get("range", ""),
        "docName": doc_name,
        "entireSheets": jobset.get("entireSheets", ""),
        "finishing": jobset.get("finishing", {}),
    }

    metadata_obj = {
        "loginAccount": login_account,
        "loginPassword": "",
        "loginDomain": login_domain,
        "printerQueue": printer_queue,
        "releaseCodePrint": release_code_print,
        "callbackURL": callback_url,
        "jobSet": jobset_obj,
    }
    metadata_str = json.dumps(metadata_obj, ensure_ascii=False, separators=(",", ":"))

    timestamp = str(int(time.time() * 1000))
    signature = _sign(uri, metadata_str, solutionkey, timestamp)

    base_url = f"{protocol}://{host}:{port}"
    filename = os.path.basename(file_path)

    headers = {
        "sdkTimestamp": timestamp,
        "sdkSignature": signature,
        "Charset": "utf-8",
    }

    try:
        resp = requests.post(
            f"{base_url}{uri}",
            headers=headers,
            data={"metadata": metadata_str},
            files={"file": (filename, open(file_path, "rb"), _mime(file_path))},
            verify=False,
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": f"无法连接到 {base_url}，请检查服务器地址和网络"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "请求超时，请检查网络连接"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"上传出错：{e}"}
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass

    try:
        result = resp.json()
    except json.JSONDecodeError:
        return {"ok": False, "error": f"响应解析失败：{resp.text}"}

    if result.get("result") == "OK":
        return {"ok": True, "jobId": result.get("jobId", "N/A")}
    return {"ok": False, "error": result.get("result", resp.text)}


@mcp.tool()
def upload_document(
    file_path: str,
    doc_name: Optional[str] = None,
    color: str = "Color",
    copy: str = "1",
    duplex: str = "3",
    paper_size: str = "A4",
    collate: str = "0",
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    uri: Optional[str] = None,
    login_account: Optional[str] = None,
    login_domain: Optional[str] = None,
    printer_queue: Optional[str] = None,
    solutionkey: Optional[str] = None,
) -> str:
    """上传文档到司印云打印系统队列（免密模式）。

    参数说明：
    - file_path: 本地文件的绝对路径（必填）
    - doc_name: 文档显示名称，默认取文件名（不含扩展名）
    - color: 彩色 Color / 黑白 Mono
    - copy: 打印份数（字符串，如 "2"）
    - duplex: 1=单面 / 2=短边翻转 / 3=长边翻转（默认 3）
    - paper_size: A3 / A4 / A5 等（仅对图片/PDF 生效，Word 纸张以文档页面设置为准）
    - collate: 0=不分页 / 1=分页

    其余连接参数（protocol/host/port/uri/login_account/login_domain/
    printer_queue/solutionkey）不传时从环境变量 SIYIN_* 读取，
    避免把内网地址硬编码在代码里。

    返回：JSON 字符串，成功含 jobId，失败含 error。
    """
    final_doc_name = doc_name or os.path.splitext(os.path.basename(file_path))[0]
    jobset = {
        "color": color,
        "copy": copy,
        "duplex": duplex,
        "paperSize": paper_size,
        "collate": collate,
        "range": "",
        "entireSheets": "",
        "finishing": {},
    }

    resolved = {
        "file_path": file_path,
        "doc_name": final_doc_name,
        "jobset": jobset,
        "protocol": _resolve(protocol, "PROTOCOL", "https"),
        "host": _resolve(host, "HOST", ""),
        "port": int(port) if port else int(_env("PORT", "8110")),
        "uri": _resolve(uri, "URI", "/mobileproxy/web_upload"),
        "login_account": _resolve(login_account, "LOGIN_ACCOUNT", ""),
        "login_domain": _resolve(login_domain, "LOGIN_DOMAIN", "Sysprint_Local"),
        "printer_queue": _resolve(printer_queue, "PRINTER_QUEUE", ""),
        "release_code_print": _env("RELEASE_CODE_PRINT", "0"),
        "callback_url": _env("CALLBACK_URL", ""),
        "solutionkey": _resolve(solutionkey, "SOLUTIONKEY", ""),
    }

    if not resolved["host"]:
        return json.dumps({"ok": False, "error": "缺少司印服务器地址：请传 host 参数或设置 SIYIN_HOST 环境变量"}, ensure_ascii=False)
    if not resolved["printer_queue"]:
        return json.dumps({"ok": False, "error": "缺少打印机队列：请传 printer_queue 参数或设置 SIYIN_PRINTER_QUEUE 环境变量"}, ensure_ascii=False)
    if not resolved["solutionkey"]:
        return json.dumps({"ok": False, "error": "缺少 solutionkey：请传 solutionkey 参数或设置 SIYIN_SOLUTIONKEY 环境变量"}, ensure_ascii=False)

    result = _do_upload(**resolved)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def check_server(
    protocol: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """检测司印服务器连通性。

    只做 TCP/HTTP 层连通性探测，不上传任何文件。
    返回 JSON 字符串，含是否可达及 HTTP 状态码。
    """
    proto = _resolve(protocol, "PROTOCOL", "https")
    h = _resolve(host, "HOST", "")
    p = int(port) if port else int(_env("PORT", "8110"))
    if not h:
        return json.dumps({"ok": False, "error": "缺少服务器地址"}, ensure_ascii=False)

    base_url = f"{proto}://{h}:{p}"
    try:
        resp = requests.get(base_url, verify=False, timeout=5)
        return json.dumps({"ok": True, "reachable": True, "status_code": resp.status_code, "url": base_url}, ensure_ascii=False)
    except requests.exceptions.ConnectionError:
        return json.dumps({"ok": False, "reachable": False, "error": f"无法连接到 {base_url}（Connection refused 或无监听）"}, ensure_ascii=False)
    except requests.exceptions.Timeout:
        return json.dumps({"ok": False, "reachable": False, "error": f"连接 {base_url} 超时（可能被防火墙拦截）"}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "reachable": False, "error": str(e)}, ensure_ascii=False)


def main():
    transport = "stdio"
    host = "0.0.0.0"
    port = 8110

    argv = sys.argv[1:]
    if "--transport" in argv:
        transport = argv[argv.index("--transport") + 1]
    if "--host" in argv:
        host = argv[argv.index("--host") + 1]
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])

    if transport == "stdio":
        mcp.run()
    else:
        # mcp.run() 不接受 host/port 参数，需通过 settings 设置
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
