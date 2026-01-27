from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session
import models
from database import get_db
from dependencies import get_current_user
import uuid
import requests
import datetime

import os
import ssl
import config
import logging

logger = logging.getLogger("payment")

# MacOS SSL Fix for Dev/Sandbox
if os.environ.get("ALIPAY_DEBUG", "True") == "True":
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass

# Try to import Alipay, but handle if not installed (Simulating environment)
ALIPAY_IMPORT_ERROR = None
try:
    from alipay import AliPay
except ImportError as e:
    ALIPAY_IMPORT_ERROR = str(e)
    AliPay = None
    logger.error(f"Failed to import alipay: {e}")

router = APIRouter()

# Configuration (from config.py)

def get_alipay_client():
    if not AliPay:
        raise HTTPException(status_code=500, detail=f"alipay-sdk-python not installed or import error: {ALIPAY_IMPORT_ERROR}")
    
    # Read Keys
    # For robust code, we should check if files exist
    # todo: check if files exist
    # if not os.path.exists(APP_PRIVATE_KEY_PATH) or not os.path.exists(ALIPAY_PUBLIC_KEY_PATH):
    #    raise HTTPException(status_code=500, detail="Alipay Key files missing")
  

    # Cert Mode Configuration (Optional - if using Certificates instead of Public Key string)
    # If using Certs, you need:
    # 1. App Private Key (from your generation tool)
    # 2. App Public Cert (app_cert_public_key.crt)
    # 3. Alipay Public Cert (alipay_public_key_cert.crt)
    # 4. Alipay Root Cert (alipay_root_cert.crt)
    
    # For now, sticking to Public Key Mode (Easiest for Sandbox). 
    # If you have CSR, you likely have "Certificate Mode" enabled.
    # You MUST have the Private Key (often named app_private_key.pem or .txt). CSR is NOT a key.
    
    
    with open(config.ALIPAY_PRIVATE_KEY_PATH) as f:
        app_private_key_string = f.read()
        # Ensure Private Key has headers
        if "-----BEGIN" not in app_private_key_string:
            app_private_key_string = f"-----BEGIN RSA PRIVATE KEY-----\n{app_private_key_string}\n-----END RSA PRIVATE KEY-----"
        
    # If using Public Key Mode (Standard for Sandbox):
    with open(config.ALIPAY_PUBLIC_KEY_PATH) as f:
        alipay_public_key_string = f.read()
        # Ensure Public Key has headers
        if "-----BEGIN" not in alipay_public_key_string:
            alipay_public_key_string = f"-----BEGIN PUBLIC KEY-----\n{alipay_public_key_string}\n-----END PUBLIC KEY-----"
    
    # print(app_private_key_string)
    # print(alipay_public_key_string)
    alipay = AliPay(
        appid=config.ALIPAY_APPID,
        app_notify_url=None,
        app_private_key_string=app_private_key_string,
        alipay_public_key_string=alipay_public_key_string,
        sign_type="RSA2",
        debug=config.ALIPAY_DEBUG
    )
    
    # --- IF YOU WANT TO USE CERT MODE (CSR Workflow), UNCOMMENT BELOW AND COMMENT ABOVE ---
    # alipay = AliPay(
    #     appid=ALIPAY_APPID,
    #     app_notify_url=None,
    #     app_private_key_string=app_private_key_string,
    #     app_cert_public_key_string=open("keys/appCertPublicKey.crt").read(),
    #     alipay_public_key_cert_string=open("keys/alipayCertPublicKey_RSA2.crt").read(),
    #     alipay_root_cert_string=open("keys/alipayRootCert.crt").read(),
    #     sign_type="RSA2",
    #     debug=ALIPAY_DEBUG
    # )
    
    return alipay
    return alipay

@router.post("/payment/alipay/create")
def create_alipay_payment(data: dict = Body(...), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Creates an order and returns Alipay Pay URL (or QR code).
    Body: { "type": "subscription", "planId": 1 } or { "type": "product", "productId": 1, "quantity": 1}
    """
    pay_type = data.get("type")
    
    total_amount = 0
    order_items = []
    subject = "BuySomething Order"
    
    if pay_type == "subscription":
        plan_id = data.get("planId")
        plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == plan_id).first()
        if not plan: return {"success": False, "message": "Plan not found"}
        
        total_amount = plan.price
        subject = f"Subscription: {plan.name}"
        
        order_items.append({
            "plan_id": plan.id,
            "item_name": plan.name,
            "price": plan.price,
            "quantity": 1
        })
        
    elif pay_type == "product":
        product_id = data.get("productId")
        quantity = data.get("quantity", 1)
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product: return {"success": False, "message": "Product not found"}
        
        # Check Stock
        if product.stock < quantity:
            return {"success": False, "message": "库存不足"}
        
        total_amount = product.price * quantity
        subject = f"Product: {product.name}"
        
        order_items.append({
            "product_id": product.id,
            "item_name": product.name,
            "price": product.price,
            "quantity": quantity
        })
    else:
        return {"success": False, "message": "Unknown type"}
        
    # Create Order
    order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
    new_order = models.Order(
        id=order_id,
        user_id=user.id,
        type=pay_type,
        total_amount=total_amount,
        status="pending"
    )
    db.add(new_order)
    db.commit()
    
    # Add Items
    for item in order_items:
        new_item = models.OrderItem(
            order_id=order_id,
            product_id=item.get("product_id"),
            plan_id=item.get("plan_id"),
            item_name=item["item_name"],
            price=item["price"],
            quantity=item["quantity"]
        )
        db.add(new_item)
    db.commit()
    
    # Call Alipay
    try:
        alipay = get_alipay_client()
        
        # Make sure amount is formatted (Alipay expects string '0.01')
        amount_str = f"{total_amount / 100:.2f}" 

        # Using api_alipay_trade_page_pay for PC Web Redirect
        # User wants auto-redirect back to app.
        # return_url: User's frontend page to show "Success"
        # notify_url: Backend callback (handled globally in AliPay init or here if overridden, but SDK usually takes init)
        
        # Note: alipay-sdk's page_pay returns a query string or full URL depending on implementation versions, 
        # usually just the query params part of the URL if not specifying 'return_url' logic?
        # Actually it returns the full URL query string that you append to gateway.
        
        # In python-alipay-sdk:
        # order_string = alipay.api_alipay_trade_page_pay(...)
        # redirect_url = f"https://openapi.alipaydev.com/gateway.do?{order_string}" (Sandbox)
        
        order_string = alipay.api_alipay_trade_page_pay(
            subject=subject,
            out_trade_no=order_id,
            total_amount=amount_str,
            return_url=config.ALIPAY_RETURN_URL, # Frontend return page (Synchronous)
            notify_url=config.ALIPAY_NOTIFY_URL # Asynchronous Callback
        )
        
        gateway = "https://openapi-sandbox.dl.alipaydev.com/gateway.do" if config.ALIPAY_DEBUG else "https://openapi.alipay.com/gateway.do"
        pay_url = f"{gateway}?{order_string}"
        pay_url = f"{gateway}?{order_string}"
        logger.info(f"Generated Pay URL: {pay_url}")
        return {"success": True, "data": {"orderId": order_id, "payUrl": pay_url}}
            
    except Exception as e:
        logger.error(f"Alipay Create Error: {e}")
        return {"success": False, "message": str(e)}

@router.post("/payment/alipay/notify")
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    """
    Callback from Alipay
    """
    data = await request.form()
    data_dict = dict(data)
    
    signature = data_dict.pop("sign", None)
    
    # Verify
    try:
        alipay = get_alipay_client()
        success = alipay.verify(data_dict, signature)
        if success and data_dict.get("trade_status") in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            # Update Order
            order_id = data_dict.get("out_trade_no")
            order = db.query(models.Order).filter(models.Order.id == order_id).first()
            if order and order.status == "pending":
                order.status = "completed"
                # Fulfill
                fulfill_order(order, db)
                db.commit()
            return "success"
            return "success"
    except Exception as e:
        logger.error(f"Notify Error: {e}")
        
    return "failure"

def fulfill_order(order, db: Session):
    """
    Grant items/subscription logic
    """
    user = db.query(models.User).filter(models.User.id == order.user_id).first()
    if not user: return
    
    if order.type == "subscription":
        # Logic specific to subscription granting
        # Ideally import specific logic or copy small logic here
        # For simplicity, duplicate logic from subscription.py for now
        for item in order.items:
            if item.plan_id:
               plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == item.plan_id).first()
               if plan:
                   # Logic to extend/create sub
                   current_sub = db.query(models.UserSubscription).filter(
                        models.UserSubscription.user_id == user.id,
                        models.UserSubscription.status == "active",
                        models.UserSubscription.end_date > datetime.datetime.now()
                   ).order_by(models.UserSubscription.end_date.desc()).first()
    
                   start_date = datetime.datetime.now()
                   if current_sub:
                       start_date = current_sub.end_date
        
                   end_date = start_date + datetime.timedelta(days=plan.duration)
                   new_sub = models.UserSubscription(
                       user_id=user.id,
                       plan_id=plan.id,
                       start_date=start_date,
                       end_date=end_date,
                       status="active"
                   )
                   db.add(new_sub)

    elif order.type == "product":
        # Add to inventory logic
        all_delivered = True
        has_vehicle = False
        
        for item in order.items:
            # Decrement Stock
            if item.product_id:
                product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
                if product:
                    # Decrease stock
                    if product.stock >= item.quantity:
                         product.stock -= item.quantity
                         db.add(product)
                    else:
                         # Log error, stock insufficient at fulfillment time (race condition?)
                         # For now we just log it, but proceeding might be safer or refunding.
                         # Assuming strict check at creation reduces this risk.
                         logger.warning(f"Stock insufficient for product {product.id} during fulfillment. Stock: {product.stock}, Quantity: {item.quantity}")
                         product.stock = 0 # Or handle otherwise.
                         db.add(product)

                    # Grant Vehicle if applicable
                    if product.vehicle_model:
                        has_vehicle = True
                        # Call FiveM API
                        success = give_vehicle_to_fivem(user.license, product.vehicle_model, product.garage)
                        if not success:
                            all_delivered = False
                    
                    # Grant Normal Item (if implemented later in user_inventory)
                    # For now just stock decrement is requested.
                          
        if has_vehicle and all_delivered:
             order.is_delivered = True
             
        # Commit stock changes
        db.commit() 

def give_vehicle_to_fivem(license, vehicle, garage):
    """
    Call FiveM API to give vehicle
    """
    # url = "http://192.168.50.77:30120/api/give-vehicle"
    # Or use FIVEM_SERVER_BASE if we import

    url = config.FIVEM_GIVE_VEHICLE_URL
    payload = {
        "license": license,
        "vehicle": vehicle,
        "garage": garage or "pillboxgarage"
    }
    
    token = config.FIVEM_API_TOKEN 
    
    try:
        logger.info(f"[VehicleDelivery] Sending {vehicle} to {license}")
        resp = requests.post(url, json=payload, headers={"Authorization": token}, timeout=5)
        if resp.status_code == 200 and resp.json().get("success"):
             logger.info(f"[VehicleDelivery] Success: {resp.json()}")
             return True
        else:
             logger.error(f"[VehicleDelivery] Failed: {resp.text}")
             return False
    except Exception as e:
        logger.error(f"[VehicleDelivery] Exception: {e}")
        return False
