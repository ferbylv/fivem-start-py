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
from Crypto.Util.Padding import unpad, pad
import jwt
from typing import Optional
# --- 数据库相关引入 ---
from sqlalchemy.orm import Session
from sqlalchemy import or_
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

# FiveM API Configuration
FIVEM_SERVER_BASE = "http://192.168.50.77:30120"
FIVEM_API_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/get-player-info"
FIVEM_API_TOKEN = "sk_your_secure_password_123456"

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


# AES 加密工具
def encrypt_data(data: dict):
    try:
        json_str = json.dumps(data)
        cipher = AES.new(AES_SECRET_KEY, AES.MODE_CBC, AES_IV)
        ct_bytes = cipher.encrypt(pad(json_str.encode('utf-8'), AES.block_size))
        return base64.b64encode(ct_bytes).decode('utf-8')
    except Exception as e:
        print(f"加密失败: {e}")
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





class EncryptedRequest(BaseModel):
    data: str

# --- 1. Web端点击开始游戏接口 ---
@app.post("/api/game/pre-auth")
def game_pre_auth(request: Request, req: EncryptedRequest,db: Session = Depends(get_db)):
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
# 1. 修改请求模型，增加 license 字段
class FiveMCheckRequest(BaseModel):
    ip: str
    license: Optional[str] = None # 新增：允许接收 license

# --- 2. FiveM端检查接口 ---
@app.post("/api/game/fivem-check")
def fivem_check_ip(req: FiveMCheckRequest, db: Session = Depends(get_db)):
    # payload = decrypt_data(req.data)
    # if not payload:
    #     return {"success": False, "message": "非法请求"}
    #
    client_ip = req.ip
    user_license = req.license
    
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
def player_joined(req: EncryptedRequest, db: Session = Depends(get_db)):
    payload = decrypt_data(req.data)
    if not payload:
        return {"success": False, "message": "非法请求"}

    user_id = payload.get("userId")
    fivem_license = payload.get("license")  # 从请求中获取 License
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
def api_send_code(req: EncryptedRequest):
    payload = decrypt_data(req.data)
    if not payload:
        raise HTTPException(status_code=400, detail="非法请求")
        
    phone = payload.get("phone")
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
def api_login(req: EncryptedRequest, db: Session = Depends(get_db)):
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
        "isBound": user.is_bound,
        "isAdmin": user.is_admin,
        "status": user.status,
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


# ================= 辅助函数：检查 FiveM 服务器状态 =================
def check_fivem_server_status():
    """
    仿照前端逻辑检查服务器状态
    """
    info_url = f"{FIVEM_SERVER_BASE}/info.json"
    players_url = f"{FIVEM_SERVER_BASE}/players.json"
    
    try:
        # 1. 请求 info.json (超时 2 秒)
        resp = requests.get(info_url, timeout=2)
        if resp.status_code == 200:
            # 在线
            player_count = 0
            try:
                # 2. 尝试获取在线人数
                p_resp = requests.get(players_url, timeout=2)
                if p_resp.status_code == 200:
                    data = p_resp.json()
                    if isinstance(data, list):
                        player_count = len(data)
            except:
                pass # 获取人数失败不影响在线判定
            
            return {
                "online": True,
                "playerCount": player_count
            }
    except:
        pass
        
    return {
        "online": False,
        "playerCount": 0,
        "error": "Timeout or Network Error"
    }


# --- 新增接口：获取服务器状态 ---
@app.get("/api/server/status")
def get_server_status(request: Request, db: Session = Depends(get_db)):
    # 1. Check Auth
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("userId")
            user = db.query(models.User).filter(models.User.id == user_id).first()
            
            if user and user.status == "banned":
                 return {
                     "success": False, 
                     "code": 503, 
                     "message": "当前账户已被封禁",
                     "isBanned": True
                 }
        except Exception as e:
            # Token invalid or expired, just ignore and return server status? 
            # Or fail? User requirement implies using token to judge status.
            # If token is bad, we can't judge status, so maybe just proceed or return 401.
            # For "Server Status" page (often public), we usually allow access but check ban if logged in.
            # But the requirement specifically says "use token to judge status".
            print(f"Status check auth error: {e}")
            pass

    return check_fivem_server_status()
# --- 3. 获取首页轮播图 (读 MySQL) ---
@app.get("/api/banners")
def get_banners(db: Session = Depends(get_db)):
    banners = db.query(models.Banner).filter(models.Banner.is_active == True).order_by(models.Banner.sort_order.desc()).all()
    return {"success": True, "data": banners}


# --- 3.1 获取最新公告 (公开) ---
@app.get("/api/announcement")
def get_public_announcement(db: Session = Depends(get_db)):
    # 获取最新一条且 enabled=True 的公告
    ann = db.query(models.Announcement).filter(models.Announcement.enabled == True).order_by(models.Announcement.id.desc()).first()
    if not ann:
        return {"success": True, "data": None}
    return {"success": True, "data": ann}


# --- 4. 获取我的资源 (读 MySQL - 包含车辆和物品) ---
# 这个接口前端 MySource 页面会用到
@app.get("/api/user/assets")
def get_user_assets(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"success": False, "message": "未登录"}
    token = auth_header.split(" ")[1]
    
    try:
        # 解码 Token 获取 UserID
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")
        print(payload)
        # 查询用户基础资产
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user: raise HTTPException(status_code=404, detail="User not found")
        
        if not user.license:
            return {"success": False, "message": "用户未绑定 FiveM 账号"}

        # === 0. 检查服务器在线状态 ===
        server_status = check_fivem_server_status()
        
        need_sync = False
        if server_status["online"]:
            need_sync = True
            
        if need_sync:
            # === 1. 在线 -> 调用 FiveM API 获取最新数据 ===
            try:
                print(f"[Sync] Fetching data for {user.phone} ({user.license})...")
                headers = {"Content-Type": "application/json", "Authorization": FIVEM_API_TOKEN}
                body = {"license": user.license}
                resp = requests.post(FIVEM_API_URL, json=body, headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    remote_data = resp.json()
                    if remote_data.get("success"):
                        r_data = remote_data["data"]
                        
                        # === 2. 同步用户基础信息 ===
                        money = r_data.get("money", {})
                        user.cash = money.get("cash", 0)
                        user.bank = money.get("bank", 0)
                        user.crypto = money.get("crypto", 0)
                        user.citizenid = r_data.get("citizenid")
                        user.charinfo = r_data.get("charinfo")
                        
                        # === 3. 同步背包物品 ===
                        # 清空旧背包
                        db.query(models.UserInventory).filter(models.UserInventory.user_id == user.id).delete()
                        
                        items_list = r_data.get("items", [])
                        new_inventory = []
                        
                        for item_data in items_list:
                            item_name = item_data.get("name")
                            if item_name:
                                db_item = db.query(models.Item).filter(models.Item.name == item_name).first()
                                if not db_item:
                                    db_item = models.Item(
                                        name=item_name,
                                        label=item_data.get("label"),
                                        type=item_data.get("type", "item"),
                                        image_url=item_data.get("image_url"),
                                        description="Auto synced from FiveM"
                                    )
                                    db.add(db_item)
                                    db.flush() 
                                else:
                                    if item_data.get("label"): db_item.label = item_data.get("label")
                                    if item_data.get("image_url"): db_item.image_url = item_data.get("image_url")
                                
                                inv_record = models.UserInventory(
                                    user_id=user.id,
                                    item_id=db_item.id,
                                    slot=item_data.get("slot", 1),
                                    count=item_data.get("amount", 1),
                                    info=item_data.get("info")
                                )
                                new_inventory.append(inv_record)
                        
                        if new_inventory:
                            db.add_all(new_inventory)
                        
                        db.commit() 
                        print(f"[Sync] Success for {user.phone}")
                        
                        # 直接返回远程数据
                        # return {"success": True, "data": encrypt_data(r_data)}
                        return {"success": True, "data": r_data}

                print(f"FiveM API Sync Failed: {resp.text}")
                
            except Exception as e:
                print(f"FiveM API Sync Error: {e}")
                db.rollback()

        # === Fallback: 离线 或 同步失败 -> 返回本地数据库数据 ===
        print(f"[Fallback] Returning local data for {user.phone}")
        
        # 查询车辆
        vehicles = db.query(models.UserVehicle).filter(models.UserVehicle.user_id == user_id).all() 
        
        # 查询背包
        inventory = db.query(models.UserInventory).filter(models.UserInventory.user_id == user_id).all()
        inventory_list = []
        for item in inventory:
            if item.item_info:
                inventory_list.append({
                    "type": "item", 
                    "label": item.item_info.label or item.item_info.name,
                    "slot": item.slot,
                    "name": item.item_info.name,
                    "image_url": item.item_info.image_url,
                    "amount": item.count,
                    "info": item.info or {}
                })
        
        local_data = {
            "is_online": False, 
            "money": {
                "cash": user.cash,
                "bank": user.bank,
                "crypto": user.crypto
            },
            "vehicles": [], 
            "license": user.license,
            "citizenid": user.citizenid,
            "charinfo": user.charinfo or {},
            "items": inventory_list
        }
        
        return {"success": True, "data": encrypt_data(local_data)}
        # return {"success": True, "data": local_data}

    except Exception as e:
        print(e)
        return {"success": False, "message": "认证失败"}


# --- 1. Web端获取绑定码 ---
@app.post("/api/bind/get-code")
def get_binding_code(req: EncryptedRequest, db: Session = Depends(get_db)):
    payload = decrypt_data(req.data)
    if not payload:
        return {"success": False, "message": "非法请求"}

    user_id = payload.get("userId")
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

class CodeRequest(BaseModel):
    code: str
    license: Optional[str] = None # 新增：允许接收 license

# --- 2. FiveM端使用绑定码查询用户 (给插件调用) ---
@app.post("/api/bind/verify-code")
def verify_binding_code(req: CodeRequest, db: Session = Depends(get_db)):
    payload = decrypt_data(req.data)
    if not payload:
        return {"success": False, "message": "非法请求"}
        
    code = req.code
    user_license = req.license
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


# --- 1.1 Store Public APIs ---
@app.get("/api/store/products")
def get_store_products(db: Session = Depends(get_db)):
    query = db.query(models.Product).filter(models.Product.is_active == True)
    
    products = query.order_by(models.Product.id.desc()).all()
    data = []
    for p in products:
        data.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description,
            "image": p.image_url,
            "stock": p.stock
        })
    return {"success": True, "data": data}
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


        # 4. 返回最新信息 (加密)
        # 查询背包关联物品
        inventory = db.query(models.UserInventory).filter(models.UserInventory.user_id == user_id).all()
        
        inventory_list = []
        for item in inventory:
            if item.item_info:
                inventory_list.append({
                    "type": "item",
                    "label": item.item_info.label or item.item_info.name,
                    "slot": item.slot,
                    "name": item.item_info.name,
                    "image_url": item.item_info.image_url,
                    "amount": item.count,
                    "info": item.info or {} # 默认为空字典
                })

        user_data = {
            "success": True, # 外层已有 success: True, 但 payload 内部一般不需要再包一层，不过用户示例中有 "success": true 在最外层。
            # 这里是 "data" 字段的内容。
            # 用户给的 JSON 示例：
            # {
            #    "data": { ... },
            #    "success": true
            # }
            # FastAPI 返回的也是 {"success": True, "data": ...}
            # 所以这里只需构造 data 的内容。
            "userId":user.id,
            "isBound":user.is_bound,
            "isAdmin":user.is_admin,
            "isSuperAdmin": user.is_super_admin,
            "permissions": user.admin_permissions or [],
            "phone":user.phone,
            "nickname":user.nickname,
            "is_online": False, # 暂且写死或预留
            "money": {
                "cash": user.cash,
                "crypto": user.crypto,
                "bank": user.bank
            },
            "vehicles": [], # 按照要求，先为空
            "license": user.license,
            "citizenid": user.citizenid,
            "charinfo": user.charinfo or {},
            "items": inventory_list
        }
        return {
            "success": True,
            "data": encrypt_data(user_data)
        }
    except Exception as e:
        print(f"Token验证失败: {e}")
        return {"success": False, "message": "Token无效"}


# ================= 后台管理 API (Admin) =================

def get_current_admin(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user or (not user.is_super_admin and not user.is_admin):
            raise HTTPException(status_code=403, detail="无权限")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Token无效")

def get_current_super_admin(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user or not user.is_super_admin:
            raise HTTPException(status_code=403, detail="无权限")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Token无效")


# --- 1. Dashboard Overview ---
@app.get("/api/admin/stats")
def admin_get_stats(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        total_users = db.query(models.User).count()
        # total_sales: 暂时mock，或者统计UserInventory消耗？还没交易记录表，暂且mock
        total_sales = 0
        
        # Check online count
        status = check_fivem_server_status()
        online_count = status.get("playerCount", 0)
        
        # active_today: 简单以updated_at为今天的用户? 暂且mock
        active_today = 0
        
        return {
            "success": True,
            "data": {
                "totalUsers": total_users,
                "activeToday": active_today,
                "totalSales": total_sales,
                "onlineCount": online_count
            }
        }
    except Exception as e:
        print(e)
        return {"success": False, "message": "获取统计失败"}


# --- 2. Store Management ---
# --- 2. Store Management (Products) ---
@app.get("/api/admin/store/products")
def admin_get_products(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    data = []
    for p in products:
        data.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "description": p.description,
            "image": p.image_url,
            "stock": p.stock,
            "isActive": p.is_active
        })
    return {"success": True, "data": data}

@app.post("/api/admin/store/products")
def admin_create_product(data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    new_product = models.Product(
        name=data.get("name"),
        price=data.get("price", 0),
        description=data.get("description"),
        image_url=data.get("image"),
        stock=data.get("stock", 0),
        is_active=data.get("isActive", True)
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return {"success": True, "data": new_product.id}

@app.put("/api/admin/store/products/{product_id}")
def admin_update_product(product_id: int, data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product: return {"success": False, "message": "商品不存在"}
    
    if "name" in data: product.name = data["name"]
    if "price" in data: product.price = data["price"]
    if "description" in data: product.description = data["description"]
    if "image" in data: product.image_url = data["image"]
    if "stock" in data: product.stock = data["stock"]
    if "isActive" in data: product.is_active = data["isActive"]
    
    db.commit()
    return {"success": True}

@app.delete("/api/admin/store/products/{product_id}")
def admin_delete_product(product_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product: return {"success": False, "message": "商品不存在"}
    
    db.delete(product)
    db.commit()
    return {"success": True}




# --- 3. Announcement Management ---
@app.get("/api/admin/announcement")
def admin_get_announcement(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    # 获取最新一条
    ann = db.query(models.Announcement).order_by(models.Announcement.id.desc()).first()
    if not ann:
        return {"success": True, "data": {"content": "", "enabled": False}}
    return {"success": True, "data": {"content": ann.content, "enabled": ann.enabled}}

@app.post("/api/admin/announcement")
def admin_update_announcement(data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    # 直接新增一条记录作为最新状态，或者更新最新那条
    # 这里选择：总是操作最新那条，如果没有则新增
    ann = db.query(models.Announcement).order_by(models.Announcement.id.desc()).first()
    if not ann:
        ann = models.Announcement(content=data.get("content", ""), enabled=data.get("enabled", True))
        db.add(ann)
    else:
        ann.content = data.get("content", "")
        ann.enabled = data.get("enabled", True)
    
    db.commit()
    return {"success": True}


# --- 4. Banner Management ---
@app.get("/api/admin/banners")
def admin_get_banners(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banners = db.query(models.Banner).order_by(models.Banner.sort_order.desc()).all()
    data = []
    for b in banners:
        data.append({
            "id": b.id,
            "title": b.title,
            "desc": b.desc,
            "src": b.image_url,
            "link": b.link_url,
            "active": b.is_active
        })
    return {"success": True, "data": data}

@app.post("/api/admin/banners")
def admin_create_banner(data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    new_banner = models.Banner(
        title=data.get("title"),
        desc=data.get("desc"),
        image_url=data.get("src"),
        link_url=data.get("link"),
        is_active=True
    )
    db.add(new_banner)
    db.commit()
    return {"success": True}

@app.delete("/api/admin/banners/{banner_id}")
def admin_delete_banner(banner_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banner = db.query(models.Banner).filter(models.Banner.id == banner_id).first()
    if banner:
        db.delete(banner)
        db.commit()
    return {"success": True}


# --- 5. User Management ---
@app.get("/api/admin/users")
def admin_get_users(q: str = None, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    query = db.query(models.User)
    if q:
        query = query.filter(or_(models.User.phone.like(f"{q}%"), models.User.nickname.like(f"%{q}%")))
    
    users = query.limit(50).all() # 限制返回数量
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "phone": u.phone,
            "nickname": u.nickname,
            "isAdmin": u.is_admin,
            "isSuperAdmin": u.is_super_admin,
            "permissions": u.admin_permissions or [],
            "status": u.status,
            "joinDate": u.created_at.strftime("%Y-%m-%d") if u.created_at else ""
        })
    return {"success": True, "data": data}

@app.post("/api/admin/users/{user_id}/grant-admin")
def admin_grant_role(user_id: int, permissions: list = Body(..., embed=True), admin: models.User = Depends(get_current_super_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_admin = True
        user.admin_permissions = permissions
        db.commit()
    return {"success": True}

@app.post("/api/admin/users/{user_id}/revoke-admin")
def admin_revoke_role(user_id: int, admin: models.User = Depends(get_current_super_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_admin = False
        user.admin_permissions = []
        db.commit()
    return {"success": True}

@app.put("/api/admin/users/{user_id}/permissions")
def admin_update_permissions(user_id: int, permissions: list = Body(..., embed=True), admin: models.User = Depends(get_current_super_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {"success": False, "message": "用户不存在"}
    if not user.is_admin:
        return {"success": False, "message": "该用户不是管理员"}
        
    user.admin_permissions = permissions
    db.commit()
    return {"success": True}

@app.post("/api/admin/users/{user_id}/ban")
def admin_ban_user(user_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.status = "banned"
        db.commit()
    return {"success": True}

@app.post("/api/admin/users/{user_id}/unban")
def admin_unban_user(user_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.status = "active"
        db.commit()
    return {"success": True}
# 启动命令: uvicorn main:app --reload