import sys

import uvicorn
from fastapi import FastAPI, HTTPException,Request,Response,APIRouter
from pydantic import BaseModel, Field
from typing import Optional
import requests
import json
import zlib
import os
from contextlib import asynccontextmanager
from typing import Any
from fastapi import Body

from routers.prepare_data import getAiResult

# ================= 配置 =================
TX_URL = os.getenv("TX_URL", "http://103.91.209.102:40120")
TX_USER = os.getenv("TX_USER", "api_bot")
# TX_PASS = os.getenv("TX_PASS", "RNpikmwdYyAtg4MKpAxg")
TX_PASS = os.getenv("TX_PASS", "zpA7FymhqeyHz6FtqUFj")

router = APIRouter()
# ================= Service =================
class TxAdminClient:
    def __init__(self, url, username, password):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.csrf_token = None
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive'
        })

    def _perform_login(self):
        print("🔄 [TxAdmin] 执行登录...")
        try:
            self.session.get(f"{self.url}/auth/login", timeout=5)
            login_payload = {"username": self.username, "password": self.password}
            resp = self.session.post(f"{self.url}/auth/password", data=login_payload, timeout=5)

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"

            try:
                self.csrf_token = json.loads(resp.text).get("csrfToken")
            except:
                self.csrf_token = self.session.cookies.get('txAdmin-csrf')

            if not self.csrf_token:
                return False, "无 Token"

            print(f"✅ [TxAdmin] 登录成功 Token: {self.csrf_token[:5]}...")
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def _send_request(self, endpoint, payload=None, retry_count=0, method="POST"):
        """通用请求发送，支持 POST 和 GET"""
        if not self.csrf_token:
            success, msg = self._perform_login()
            if not success: return {"success": False, "msg": msg}

        headers = {
            "X-TxAdmin-CsrfToken": self.csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.url,
            "Referer": f"{self.url}/legacy/whitelist"
        }

        try:
            if method == "GET":
                # GET 请求通常没有 data body
                resp = self.session.get(f"{self.url}{endpoint}", headers=headers, timeout=5)
            else:
                resp = self.session.post(f"{self.url}{endpoint}", data=payload, headers=headers, timeout=5)

            if resp.status_code in [401, 403] or "Missing HTTP header" in resp.text:
                if retry_count < 1:
                    print("⚠️ 会话失效重试...")
                    self.csrf_token = None
                    if self._perform_login()[0]:
                        return self._send_request(endpoint, payload, retry_count + 1, method)
                return {"success": False, "msg": "会话失效"}

            return {"success": True, "resp": resp}
        except Exception as e:
            return {"success": False, "msg": str(e)}

    def get_license_by_short_id(self, short_id):
        """核心逻辑：根据短 ID 查 License"""
        res = self._send_request("/whitelist/requests", None, method="GET")

        if not res["success"] or res["resp"].status_code != 200:
            return None

        try:
            data = res["resp"].json()
            # 遍历查找
            for req in data.get("requests", []):
                if req.get("id") == short_id:
                    # txAdmin 返回的是不带 license: 前缀的 hash，手动加上
                    return f"license:{req.get('license')}"
            return None
        except:
            return None

    def add_whitelist(self, identifier, player_name):
        payload = {"identifier": identifier, "playerName": player_name}
        res = self._send_request("/whitelist/approvals/add", payload, method="POST")

        if not res["success"]: return False, res["msg"]

        # 宽松的成功判断
        if res["resp"].status_code == 200:
            return True, "OK"
        return False, res["resp"].text


# ================= APP =================
tx_client = TxAdminClient(TX_URL, TX_USER, TX_PASS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tx_client._perform_login()
    yield


app = FastAPI(lifespan=lifespan)


class IDRequest(BaseModel):
    short_id: str = Field(..., description="例如 RZ3LB", examples=["RZ3LB"])
    name: str = Field(default="API Approved", examples=["玩家A"])


@router.post("/approve_id")
def api_approve_id(data: IDRequest):
    # 1. 查找
    print(f"data.short_id:{data.short_id}")
    license_str = tx_client.get_license_by_short_id(data.short_id)
    if not license_str:
        return {"status": "ok", "detail": "已通过"}
        # raise HTTPException(404, "ID未找到或不在等待列表中")

    # 2. 添加
    success, msg = tx_client.add_whitelist(license_str, data.name)
    if success:
        return {"status": "ok", "detail": license_str}
    raise HTTPException(500, msg)


# 定义请求体模型
class WhitelistRequest(BaseModel):
    identifier: str = Field(
        ...,
        description="玩家标识符",
        examples=["license:abcdef1234567890abcdef1234567890abcdef12"] # 注意这里是列表
    )
    playerName: str = Field(
        default="Unknown",
        description="玩家名称备注",
        examples=["测试玩家"] # 注意这里是列表
    )

@router.post("/whitelist/add")
def add_whitelist(data: WhitelistRequest):
    """
    添加白名单接口
    """
    # 简单的格式校验
    if not data.identifier.startswith("license:"):
        # 这是一个可选的校验，如果你确定只接受 license
        pass

    success, message = tx_client.add_whitelist(data.identifier, data.playerName)

    if success:
        return {"status": "success", "message": f"已添加 {data.playerName}", "identifier": data.identifier}
    else:
        # 返回 500 或 400 错误码
        raise HTTPException(status_code=500, detail=f"添加失败: {message}")

class WhiteListRequest(BaseModel):
    data: Any


@router.post("/push")
def add_whitelist(data: WhiteListRequest):
    print(f"data.data:{data.data}")
    # print(transform(data.data))
    aiResult=getAiResult(transform(data.data))
    result=json.loads(aiResult)
    if result.get("score") <= 9 and result.get("score") > 0:
        result["reason"]="驳回：错题过多"
    print(result.get("score"))
    print(result)
    return result
def transform(param):
    print(param)
    data=json.loads(param)
    # data=param
    print(data)
    # 2. 定义不需要放入文本的无关字段 (元数据)
    ignore_keys = ["白名单识别码", "邮箱联系方式"]

    # 3. 初始化列表，用于存放处理后的文本行
    lines = []

    # --- 步骤 A: 优先处理核心字段 (模仿图中顺序：先名字，后背景) ---



    # --- 步骤 B: 遍历并添加剩余的 RP 考题 ---

    for key, value in data.items():
        # 如果 key 不在黑名单里，说明是考题
        if key not in ignore_keys:
            clean_val = str(value).strip()
            lines.append(f"Q: {key}")
            lines.append(f"A: {clean_val}")

    # 4. 将所有行用换行符 (\n) 拼接成一个长字符串
    # 这就是图中 input_content 的最终值
    formatted_text = "\n".join(lines)
    print(formatted_text)
    # 5. 返回结果 (Coze/WPS 格式)
    return formatted_text

@router.post("/kookBot")
async def add_whitelist(request: Request):
    try:
        # 1. 获取原始二进制数据 (KOOK 默认会使用 zlib 压缩数据)
        body_bytes = await request.body()

        # 2. 尝试 zlib 解压
        # KOOK 的数据流通常是压缩过的，必须先解压
        try:
            decompressed_data = zlib.decompress(body_bytes)
            json_str = decompressed_data.decode('utf-8')
            data = json.loads(json_str)
        except Exception as e:
            # 如果解压失败，可能是未压缩的 JSON (极少见，但在调试时可能遇到)
            print(f"解压失败，尝试直接解析: {e}")
            data = await request.json()

        # 打印日志查看收到的数据结构
        # print(f"收到事件: {json.dumps(data, ensure_ascii=False)}")

        # 3. 获取核心数据字段 'd'
        # KOOK 的数据结构通常是 { "s": 0, "d": { ... }, "sn": ... }
        d_data = data.get('d', {})

        if not d_data:
            return {"msg": "No data"}

        # ==========================================
        # 4. 【关键步骤】处理 URL 验证 (Challenge)
        # ==========================================
        # 当你在后台点击“Verify”或者“保存”时，KOOK 会发这个包
        # type 255 代表系统级验证请求
        challenge_code=""
        if d_data.get('type') == 255 and d_data.get('channel_type') == 'WEBHOOK_CHALLENGE':
            challenge_code = d_data.get('challenge')
            print(f"收到验证请求，Challenge: {challenge_code}")
            # 必须返回包含 challenge 的 JSON
            return {"challenge": challenge_code}

        # ==========================================
        # 5. 处理正常消息 (例如文本消息)
        # ==========================================
        # type 1 代表文字消息, type 9 代表 Markdown
        if d_data.get('type') == 1 or d_data.get('type') == 9:
            sender_id = d_data.get('author_id')
            content = d_data.get('content')
            print(f"收到用户 {sender_id} 的消息: {content}")

            # 在这里调用你的业务逻辑
            # 注意：Webhook 仅用于接收，回复消息需要调用 KOOK 的 API (POST /api/v3/message/create)

        return {"Challenge": challenge_code}

    except Exception as e:
        print(f"处理异常: {e}")
        return Response(status_code=500)

class KookBotRequest(BaseModel):
    code: str
    name: str
@router.post("/sendKookWhitelist")
def send_kook_whitelist(data: KookBotRequest):
    url = "https://www.kookapp.cn/api/v3/message/create"

    # 注意：为了安全起见，实际使用时请检查你的 Token 是否泄漏
    # 你 curl 中的 Token 我已原样填入，建议在公开场合对 Token 进行打码处理
    headers = {
        'Authorization': 'Bot 1/MzgzMjQ=/H9Efttqm5M/Lhi4sbYYp6Q==',
        'Content-Type': 'application/json',
        'Cookie': 'PHPSESSID=5uip2ihbn0mqhcp8amm7ol51rd; _csrf_chuanyu=YvphMek4ptC09YGEznfpVDpUKw_Nbxa-; tgw_l7_route=c4fea55e65e7c4936b0846250c63583b'
    }
    card_structure = [
        {
            "type": "card",
            "theme": "secondary",  # 卡片左侧颜色条: primary(主色), secondary(次色), danger(红), etc.
            "size": "lg",
            "modules": [
                # 模块一：文字内容
                {
                    "type": "section",
                    "text": {
                        "type": "kmarkdown",
                        "content": "(met)all(met) **白名单审核提醒**\n您有一条新的白名单待审核。"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "kmarkdown",
                        "content": f"识别码:***{data.code}***\n角色名称:***{data.name}***"
                    }
                },
                # 模块二：按钮组
                {
                    "type": "action-group",
                    "elements": [
                        {
                            "type": "button",
                            "theme": "primary",  # 按钮颜色: primary(蓝), success(绿), danger(红), warning(黄)
                            "value": "https://www.kdocs.cn/l/crXNVxjeI6pD?R=L1MvNg==",  # 【关键】这里填你要跳转的链接
                            "click": "link",  # 【关键】代表点击后是打开链接
                            "text": {
                                "type": "plain-text",
                                "content": "前往审核后台"  # 按钮上的文字
                            }
                        },
                        # 如果需要第二个按钮，可以在这里继续添加
                        # { ... }
                    ]
                }
            ]
        }
    ]
    # 构造请求体数据
    # 注意：JSON 中的 true 在 Python 中需要写成 True
    payload = {
        "type": 10,
        "content": json.dumps(card_structure),
        "mention_all": True,
        "target_id": "1237361640883310",
        "mention_role_part": [
            {
                "role_id": 416603,
                "name": "管理员",
                "desc": "",
                "color": 0,
                "color_type": 1,
                "color_map": {},
                "position": 1,
                "hoist": 1,
                "mentionable": 0,
                "permissions": 1,
                "type": 0,
                "op_permissions": 0
            }
        ]
    }

    try:
        # 发送 POST 请求
        # 使用 json=payload 参数，requests 库会自动将字典转换为 JSON 字符串
        response = requests.post(url, headers=headers, json=payload)

        # 打印响应状态码和内容
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")

        # 如果需要解析返回的 JSON 数据
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                print("发送成功！")
            else:
                print(f"发送失败，错误信息: {data.get('message')}")

    except Exception as e:
        print(f"请求发生错误: {e}")
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)