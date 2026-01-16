from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
import models
from database import get_db
from dependencies import get_current_user, get_current_admin

router = APIRouter()

# --- Public/User APIs ---

@router.get("/subscription/plans")
def get_subscription_plans(db: Session = Depends(get_db)):
    plans = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.is_active == True).all()
    data = []
    for p in plans:
        data.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "duration": p.duration,
            "description": p.description
        })
    return {"success": True, "data": data}

@router.get("/subscription/my")
def get_my_subscription(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Find active subscription
    sub = db.query(models.UserSubscription).filter(
        models.UserSubscription.user_id == user.id,
        models.UserSubscription.status == "active",
        models.UserSubscription.end_date > datetime.now()
    ).order_by(desc(models.UserSubscription.end_date)).first()
    
    if sub:
        # Get plan name
        plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == sub.plan_id).first()
        plan_name = plan.name if plan else "Unknown Plan"
        
        return {
            "success": True,
            "data": {
                "isActive": True,
                "planName": plan_name,
                "expiryDate": sub.end_date.strftime("%Y-%m-%d")
            }
        }
    else:
        return {
            "success": True,
            "data": {
                "isActive": False,
                "planName": None,
                "expiryDate": None
            }
        }

@router.post("/subscription/subscribe")
def subscribe_to_plan(data: dict = Body(...), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan_id = data.get("planId")
    if not plan_id:
        return {"success": False, "message": "参数错误"}
        
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
    if not plan or not plan.is_active:
        return {"success": False, "message": "订阅计划不存在或已下架"}
        
    # Check Balance (Assist user pays with Bank)
    if user.bank < plan.price:
       return {"success": False, "message": "银行余额不足"}
       
    # Deduct Money
    user.bank -= plan.price
    
    # Create Subscription
    # Check if already active? (Extend or Add New?) 
    # Logic: If active, extend end_date. If not, start now.
    current_sub = db.query(models.UserSubscription).filter(
        models.UserSubscription.user_id == user.id,
        models.UserSubscription.status == "active",
        models.UserSubscription.end_date > datetime.now()
    ).order_by(desc(models.UserSubscription.end_date)).first()
    
    start_date = datetime.now()
    if current_sub:
        start_date = current_sub.end_date
        
    end_date = start_date + timedelta(days=plan.duration)
    
    new_sub = models.UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        start_date=start_date,
        end_date=end_date,
        status="active"
    )
    
    db.add(new_sub)
    db.commit()
    
    return {"success": True, "message": "订阅成功"}


# --- Admin APIs ---

@router.get("/admin/subscription/plans")
def admin_get_plans(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    plans = db.query(models.SubscriptionPlan).all()
    data = []
    for p in plans:
        data.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "duration": p.duration,
            "description": p.description,
            "isActive": p.is_active
        })
    return {"success": True, "data": data}

@router.post("/admin/subscription/plans")
def admin_create_plan(data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    new_plan = models.SubscriptionPlan(
        name=data.get("name"),
        price=data.get("price", 0),
        duration=data.get("duration", 30),
        description=data.get("description"),
        is_active=True
    )
    db.add(new_plan)
    db.commit()
    return {"success": True}

@router.put("/admin/subscription/plans/{plan_id}")
def admin_update_plan(plan_id: int, data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
    if not plan: return {"success": False, "message": "Plan Not Found"}
    
    if "name" in data: plan.name = data["name"]
    if "price" in data: plan.price = data["price"]
    if "duration" in data: plan.duration = data["duration"]
    if "description" in data: plan.description = data["description"]
    if "isActive" in data: plan.is_active = data["isActive"]
    
    db.commit()
    return {"success": True}   

@router.delete("/admin/subscription/plans/{plan_id}")
def admin_delete_plan(plan_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
    if plan:
        db.delete(plan)
        db.commit()
    return {"success": True}
