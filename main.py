# main.py
import json
import time
import random
import base64
import requests  # 1. 引入 requests 库
from fastapi import Request
from fastapi import FastAPI, HTTPException,Body,Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import jwt
# --- 数据库相关引入 ---
from sqlalchemy.orm import Session
from database import get_db, engine
import models
# ================= 配置区域 =================

# Spug 推送助手 URL (请替换为你自己的真实 URL)
# 类似于: https://push.spug.cc/sms/A27Lsf3fs2bgEY
SPUG_SMS_URL = "https://push.spug.cc/sms/3RtZpmNURwKzVgQRbzpd6w"

# 加密配置 (必须与前端一致)
AES_SECRET_KEY = b"12345678901234567890123456789012"
AES_IV = b"1234567890123456"

# JWT 配置
JWT_SECRET = "your-jwt-secret-key"
JWT_ALGORITHM = "HS256"

# 模拟数据库
verification_codes_db = {}
ip_auth_db = {}
manual_bind_db = {}
app = FastAPI()
verification_codes_db["15143933787"] = {
            "code": "123456",
            # -------------------------------------------------
            # ★★★ 修改点：将 60 改为 300 ★★★
            # -------------------------------------------------
            "expire_at": time.time() + 300
        }
# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def get_client_ip(request: Request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host

# AES 解密工具
def decrypt_data(encrypted_text: str):
    try:
        enc = base64.b64decode(encrypted_text)
        cipher = AES.new(AES_SECRET_KEY, AES.MODE_CBC, AES_IV)
        decrypted_bytes = unpad(cipher.decrypt(enc), AES.block_size)
        return json.loads(decrypted_bytes.decode('utf-8'))
    except Exception as e:
        print(f"解密失败: {e}")
        return None


# ================= 2. Spug 短信发送工具 (新) =================
def send_spug_sms(phone: str, code: str):
    """
    使用 Spug 推送助手发送短信验证码
    """
    try:
        # 构造请求体
        body = {
            'number': '5',  # 这个名字通常显示在短信开头，如 【推送助手】
            'code': code,  # 验证码
            'to': phone  # 接收手机号
        }

        # 发送 POST 请求
        response = requests.post(SPUG_SMS_URL, json=body, timeout=5)

        # 打印响应以便调试
        print(f"Spug响应: {response.text}")

        # Spug 如果成功通常返回 HTTP 200
        if response.status_code == 200:
            return True
        else:
            print(f"短信发送失败: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"请求异常: {e}")
        return False


# 请求体模型
class SendCodeRequest(BaseModel):
    phone: str


class LoginRequest(BaseModel):
    data: str

# --- 1. Web端点击开始游戏接口 ---
@app.post("/api/game/pre-auth")
def game_pre_auth(request: Request, req: LoginRequest,db: Session = Depends(get_db)):
    # 1. 解密用户信息
    payload = decrypt_data(req.data)
    if not payload:
        return {"success": False, "message": "非法请求"}

    # 假设 payload 里有 phone, nickname 等信息
    phone = payload.get("phone")

    # 2. 获取用户 IP
    client_ip = get_client_ip(request)
    print(f"Web端预授权 -> 用户:{phone}, IP:{client_ip}")
    # 查数据库获取最新用户信息
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user: return {"success": False, "message": "用户不存在"}
    # 构造要传给 FiveM 的数据
    auth_data = {
        "userId": user.id,
        "phone": user.phone,
        "isBound": user.is_bound,
        # 可以把数据库里的车牌号也传过去，方便游戏内发放钥匙
    }

    # 3. ★★★ 存入内存字典 (有效期 5 分钟) ★★★
    ip_auth_db[client_ip] = {
        "user_info": auth_data,  # 存储完整的用户信息
        "expire_at": time.time() + 300  # 5分钟后过期
    }

    return {"success": True, "message": "预授权成功"}


# --- 2. FiveM端检查接口 ---
class FiveMCheckRequest(BaseModel):
    ip: str
    license:str


@app.post("/api/game/fivem-check")
def fivem_check_ip(req: FiveMCheckRequest, db: Session = Depends(get_db)):
    print(f"Web<UNK> -> <UNK>:{req.ip}, IP:{req}")
    client_ip = req.ip
    user_license=req.license
    print(f"Web<UNK> -> <UNK>:{client_ip}")
    # 1. 在字典里查找这个 IP
    record = ip_auth_db.get(client_ip)

    # 2. 判断是否存在 且 未过期
    if record and time.time() < record["expire_at"]:
        # === 匹配成功 ===
        print(f"FiveM匹配成功 -> IP:{client_ip}")
        if user_license:
            try:
                # 从缓存记录中获取用户 ID
                user_id = record["user_info"].get("userId")

                # 查询数据库
                user = db.query(models.User).filter(models.User.id == user_id).first()
                if user:
                    # 更新字段
                    user.license = user_license
                    user.is_bound = True
                    db.commit()  # 提交保存
                    print(f"自动绑定成功 -> 用户:{user.nickname}, License:{user_license}")
                    del ip_auth_db[client_ip]
            except Exception as e:
                print(f"自动绑定更新失败: {e}")
        return {"success": True, "data": record["user_info"]}
    else:
        # === 匹配失败 (不存在 或 已过期) ===
        # 如果过期了，顺手清理一下内存 (可选)
        if record:
            del ip_auth_db[client_ip]

        # 生成一个随机 4 位验证码 (用于 fallback 卡片展示)
        # random_code = str(random.randint(1000, 9999))

        # 这里你可以把 random_code 也存到一个临时字典里，用于后续“手动绑定”流程
        # manual_bind_db[random_code] = ... (暂略)

        return {
            "success": False
        }


# --- 3. 玩家入服持久化接口 ---
@app.post("/api/game/player-joined")
def player_joined(req: dict = Body(...), db: Session = Depends(get_db)):
    # 假设 FiveM 传来了: {"userId": 1, "license": "license:xxxx"}
    user_id = req.get("userId")
    fivem_license = req.get("license")  # 从请求中获取 License
    if user_id:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.is_bound = True  # 标记为已绑定
            user.license = fivem_license
            db.commit()
            print(f"用户 {user.nickname} 已绑定 FiveM")
            return {"success": True}

    return {"success": False}
# --- 发送验证码接口 ---
@app.post("/api/send-code")
def api_send_code(req: SendCodeRequest):
    phone = req.phone
    if not phone:
        raise HTTPException(status_code=400, detail="手机号不能为空")

    # 生成 6 位随机验证码
    code = str(random.randint(100000, 999999))

    # === 调用 Spug 发送 ===
    success = send_spug_sms(phone, code)

    print(f"尝试发送短信 -> 手机: {phone}, 验证码: {code}, 结果: {success}")

    if success:
        # 存入内存 (有效期改为 5 分钟 = 300 秒)
        verification_codes_db[phone] = {
            "code": code,
            # -------------------------------------------------
            # ★★★ 修改点：将 60 改为 300 ★★★
            # -------------------------------------------------
            "expire_at": time.time() + 300
        }
        return {"success": True, "message": "验证码已发送"}
    else:
        # 如果是测试阶段，发送失败也可以暂时返回 True 让流程走下去，这里视你的需求而定
        return {"success": False, "message": "短信发送失败，请检查后台日志"}


# --- 登录接口 (保持不变) ---
@app.post("/api/login")
def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    # 1. 解密前端数据
    payload = decrypt_data(req.data)
    if not payload:
        return {"success": False, "message": "非法请求：数据解密失败"}

    phone = payload.get("phone")
    user_code = payload.get("code")

    # 2. 校验验证码 (先检查内存/Redis中的验证码是否正确)
    record = verification_codes_db.get(phone)
    if not record:
        return {"success": False, "message": "请先获取验证码"}
    if time.time() > record["expire_at"]:
        del verification_codes_db[phone]
        return {"success": False, "message": "验证码已过期"}
    if record["code"] != user_code:
        return {"success": False, "message": "验证码错误"}

    # ============================================================
    # ★★★ 核心逻辑：数据库 查询或注册 ★★★
    # ============================================================

    # 3. 去数据库查询这个手机号是否存在
    user = db.query(models.User).filter(models.User.phone == phone).first()

    # 4. 判断结果
    if not user:
        # --- 情况 A: 用户不存在 -> 执行注册新增 ---
        print(f"新用户注册: {phone}")
        new_user = models.User(
            phone=phone,
            nickname=f"用户{phone[-4:]}",  # 默认昵称：用户8888
            license=None,
            cash=5000,  # 新手启动资金
            bank=10000,  # 新手银行存款
            is_bound=False
        )
        db.add(new_user)  # 添加到会话
        db.commit()  # 提交到数据库
        db.refresh(new_user)  # 刷新对象，获取自动生成的 ID
        user = new_user  # 将新用户赋值给 user 变量，方便后面统一处理
    else:
        # --- 情况 B: 用户已存在 -> 直接使用 ---
        print(f"老用户登录: {user.nickname}")

    # 5. 生成 Token (使用数据库里的真实 ID 和信息)
    user_info = {
        "userId": user.id,
        "phone": user.phone,
        "nickname": user.nickname,

        "isBound": user.is_bound
    }
    # 生成 JWT
    token = jwt.encode(user_info, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # 6. 登录成功后，清除验证码
    del verification_codes_db[phone]

    return {
        "success": True,
        "message": "登录成功",
        "token": token,
        "userInfo": user_info
    }
# --- 3. 获取首页轮播图 (读 MySQL) ---
@app.get("/api/banners")
def get_banners(db: Session = Depends(get_db)):
    banners = db.query(models.Banner).filter(models.Banner.is_active == True).order_by(models.Banner.sort_order.desc()).all()
    return {"success": True, "data": banners}


# --- 4. 获取我的资源 (读 MySQL - 包含车辆和物品) ---
# 这个接口前端 MySource 页面会用到
@app.get("/api/user/assets")
def get_user_assets(token: str, db: Session = Depends(get_db)):
    try:
        # 解码 Token 获取 UserID
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")

        # 查询用户基础资产
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")

        # 查询车辆
        vehicles = db.query(models.UserVehicle).filter(models.UserVehicle.user_id == user_id).all()

        # 查询背包 (关联查询物品详情)
        inventory = db.query(models.UserInventory).filter(models.UserInventory.user_id == user_id).all()

        # 格式化背包数据
        inventory_list = []
        for item in inventory:
            if item.item_info:  # 确保有关联的物品信息
                inventory_list.append({
                    "id": item.item_info.id,
                    "name": item.item_info.name,
                    "type": item.item_info.type,
                    "image": item.item_info.image_url,
                    "count": item.count
                })

        return {
            "success": True,
            "data": {
                "assets": {"cash": user.cash, "bank": user.bank},
                "vehicles": vehicles,
                "items": inventory_list
            }
        }
    except Exception as e:
        print(e)
        return {"success": False, "message": "认证失败"}


# --- 1. Web端获取绑定码 ---
@app.post("/api/bind/get-code")
def get_binding_code(req: dict = Body(...), db: Session = Depends(get_db)):
    user_id = req.get("userId")
    if not user_id:
        return {"success": False, "message": "用户ID不能为空"}

    # 查询用户信息
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {"success": False, "message": "用户不存在"}

    # 生成 6 位随机数字码
    code = str(random.randint(100000, 999999))

    # 构造要传给 FiveM 的数据
    user_data = {
        "userId": user.id,
        "phone": user.phone,
        "nickname": user.nickname,
        "license": user.license,
        "isBound": user.is_bound
    }

    # 存入内存 (5分钟有效)
    manual_bind_db[code] = {
        "user_info": user_data,
        "expire_at": time.time() + 300
    }

    print(f"生成绑定码 -> User:{user.nickname}, Code:{code}")
    return {"success": True, "code": code}


# --- 2. FiveM端使用绑定码查询用户 (给插件调用) ---
class VerifyBindCodeRequest(BaseModel):
    code: str
    license:str

@app.post("/api/bind/verify-code")
def verify_binding_code(req: VerifyBindCodeRequest, db: Session = Depends(get_db)):
    code = req.code
    user_license=req.license
    record = manual_bind_db.get(code)

    # 检查是否存在且未过期
    if record and time.time() < record["expire_at"]:
        # 验证成功，返回用户信息
        user_info = record["user_info"]
        if user_license:
            try:
                # 从缓存记录中获取用户 ID
                user_id = record["user_info"].get("userId")

                # 查询数据库
                user = db.query(models.User).filter(models.User.id == user_id).first()
                if user:
                    # 更新字段
                    user.license = user_license
                    user.is_bound = True
                    db.commit()  # 提交保存
                    print(f"自动绑定成功 -> 用户:{user.nickname}, License:{user_license}")
            except Exception as e:
                print(f"自动绑定更新失败: {e}")
        # ★ 重要：获取一次后立即删除，防止重复使用
        del manual_bind_db[code]

        return {"success": True, "data": user_info}
    else:
        # 如果过期了顺手清理
        if record: del manual_bind_db[code]
        return {"success": False, "message": "绑定码无效或已过期"}


# --- 新增：获取当前登录用户信息的专用接口 ---
@app.get("/api/user/info")
def api_get_user_info(request: Request, db: Session = Depends(get_db)):
    # 1. 从 Header 获取 Token (Authorization: Bearer <token>)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"success": False, "message": "未登录"}

    token = auth_header.split(" ")[1]

    try:
        # 2. 解码 Token 获取 UserID
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")

        # 3. 查最新数据库
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return {"success": False, "message": "用户不存在"}

        # 4. 返回最新信息
        return {
            "success": True,
            "data": {
                "userId": user.id,
                "phone": user.phone,
                "nickname": user.nickname,
                "license": user.license,
                "isBound": user.is_bound,
                # 如果你想在导航栏显示钱，也可以加上
                "cash": user.cash,
                "bank": user.bank
            }
        }
    except Exception as e:
        print(f"Token验证失败: {e}")
        return {"success": False, "message": "Token无效"}
# 启动命令: uvicorn main:app --reload