# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 格式: mysql+pymysql://用户名:密码@主机:端口/数据库名
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://ferby:lvyang0.0@192.168.50.77:3306/fivem_online"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True, # 自动重连
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 依赖项：每个请求获取一个独立的数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()