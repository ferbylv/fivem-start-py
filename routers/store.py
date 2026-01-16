from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import models
from database import get_db
from dependencies import get_current_user, get_current_admin

router = APIRouter()

# --- Public Store APIs ---

@router.get("/store/products")
def get_store_products(db: Session = Depends(get_db)):
    # Get active products
    products = db.query(models.Product).filter(models.Product.is_active == True).order_by(models.Product.id.desc()).all()
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

# --- Admin Product APIs ---

@router.get("/admin/store/products")
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

@router.post("/admin/store/products")
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

@router.put("/admin/store/products/{product_id}")
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

@router.delete("/admin/store/products/{product_id}")
def admin_delete_product(product_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product:
        db.delete(product)
        db.commit()
    return {"success": True}

    return {"success": True}

# --- Admin Order APIs ---

@router.get("/admin/orders")
def admin_get_orders(
    page: int = 1, 
    limit: int = 10, 
    search: str = None, 
    status: str = None, 
    admin: models.User = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    query = db.query(models.Order)
    
    if search:
        # Search by order ID or user nickname (join needed for nickname)
        query = query.join(models.User).filter(
            (models.Order.id.like(f"%{search}%")) |
            (models.User.nickname.like(f"%{search}%"))
        )
        
    if status:
        query = query.filter(models.Order.status == status)
        
    total_count = query.count()
    
    # Pagination
    offset = (page - 1) * limit
    orders = query.order_by(models.Order.created_at.desc()).offset(offset).limit(limit).all()
    
    list_data = []
    for o in orders:
        # Determine item name from first item (simplified)
        item_name = "Multipie Items"
        if o.items and len(o.items) > 0:
            item_name = o.items[0].item_name
            if len(o.items) > 1:
                item_name += f" 等{len(o.items)}件"
        
        user_nickname = o.owner.nickname if o.owner else "Unknown"
        
        list_data.append({
            "id": o.id,
            "userId": o.user_id,
            "userNickname": user_nickname,
            "type": o.type,
            "itemName": item_name,
            "amount": o.total_amount,
            "status": o.status,
            "createdAt": o.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return {
        "success": True,
        "data": {
            "list": list_data,
            "totalPages": (total_count + limit - 1) // limit,
            "currentPage": page
        }
    }
