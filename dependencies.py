from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import jwt
import models
from database import get_db

JWT_SECRET = "your-jwt-secret-key"
JWT_ALGORITHM = "HS256"

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("userId")
        if not user_id:
             raise HTTPException(status_code=401, detail="无效Token")
             
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
            
        if user.status == "banned":
            raise HTTPException(status_code=403, detail="账户已封禁")
            
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效Token")
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="认证失败")

def get_current_admin(user: models.User = Depends(get_current_user)):
    if not user.is_admin and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="权限不足")
    return user

def get_current_super_admin(user: models.User = Depends(get_current_user)):
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return user
