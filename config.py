
import os

from sqlalchemy import false

# Database
#SQLALCHEMY_DATABASE_URL = "mysql+pymysql://fivem_online:xnrRcWaTimpTbWLs@127.0.0.1:3306/fivem_online"

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://fivem_online:lvyang0.0@192.168.50.77:3306/fivem_online"

# Spug Push
SPUG_SMS_URL = "https://push.spug.cc/sms/3RtZpmNURwKzVgQRbzpd6w"

# Security (AES)
AES_SECRET_KEY = b"12345678901234567890123456789012"
AES_IV = b"1234567890123456"

# Security (JWT)
JWT_SECRET = "your-jwt-secret-key"
JWT_ALGORITHM = "HS256"

# FiveM API
FIVEM_SERVER_BASE = "http://103.91.209.102:30120"
FIVEM_API_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/get-player-info"
FIVEM_BAN_API_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/ban-player"
FIVEM_GIVE_VEHICLE_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/give-vehicle"
FIVEM_API_TOKEN = "sk_your_secure_password_123456"

# Alipay
ALIPAY_APPID = "2021005169687001"
ALIPAY_DEBUG = False  # True for Sandbox
ALIPAY_PRIVATE_KEY_PATH = "routers/keys/app-private-key-pro.txt"
ALIPAY_PUBLIC_KEY_PATH = "routers/keys/alipay_public_key_pro.txt"
ALIPAY_NOTIFY_URL = "https://fivempy.lvyoung.top/api/payment/alipay/notify" # Updated to ngrok
ALIPAY_RETURN_URL = "https://fivem.lvyoung.top/home"
