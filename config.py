
import os

# Database
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://ferby:lvyang0.0@192.168.50.77:3306/fivem_online"

# Spug Push
SPUG_SMS_URL = "https://push.spug.cc/sms/3RtZpmNURwKzVgQRbzpd6w"

# Security (AES)
AES_SECRET_KEY = b"12345678901234567890123456789012"
AES_IV = b"1234567890123456"

# Security (JWT)
JWT_SECRET = "your-jwt-secret-key"
JWT_ALGORITHM = "HS256"

# FiveM API
FIVEM_SERVER_BASE = "http://192.168.50.77:30120"
FIVEM_API_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/get-player-info"
FIVEM_BAN_API_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/ban-player"
FIVEM_GIVE_VEHICLE_URL = f"{FIVEM_SERVER_BASE}/qb-qrlogin/api/give-vehicle"
FIVEM_API_TOKEN = "sk_your_secure_password_123456"

# Alipay
ALIPAY_APPID = "your_alipay_appid"
ALIPAY_DEBUG = True  # True for Sandbox
ALIPAY_PRIVATE_KEY_PATH = "routers/keys/app-privare-key.txt"
ALIPAY_PUBLIC_KEY_PATH = "routers/keys/alipay_public_key.txt"
ALIPAY_NOTIFY_URL = "https://6696819b56da.ngrok-free.app/api/payment/alipay/notify" # Updated to ngrok
ALIPAY_RETURN_URL = "http://your-domain.com/payment/result"
