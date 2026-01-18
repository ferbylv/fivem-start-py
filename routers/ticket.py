from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import models
import datetime
from database import get_db
from dependencies import get_current_user, get_current_admin

router = APIRouter()

# --- User APIs ---

@router.get("/ticket/list")
def get_ticket_list(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).filter(models.Ticket.user_id == user.id).order_by(models.Ticket.id.desc()).all()
    data = []
    for t in tickets:
        data.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "type": t.type,
            "createdAt": t.created_at.strftime("%Y-%m-%d")
        })
    return {"success": True, "data": data}

@router.post("/ticket/create")
def create_ticket(data: dict = Body(...), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_ticket = models.Ticket(
        user_id=user.id,
        title=data.get("title"),
        type=data.get("type", "bug"),
        content=data.get("content"),
        status="open"
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    
    # Optional: Add initial message? 
    # The requirement says "content" in create body.
    # Usually we add this as the first message or just keep it in Ticket.content.
    # The detail response has "messages". Let's add the first message for consistency if the UI expects it in the message list.
    # But current Detail logic below will fetch TicketMessage. 
    # The `content` column in Ticket table is good for summary, but if we want full conversational history, we should insert a message from User too.
    
    first_msg = models.TicketMessage(
        ticket_id=new_ticket.id,
        sender_role="user",
        content=data.get("content")
    )
    db.add(first_msg)
    db.commit()
    
    return {"success": True, "data": new_ticket.id}

@router.get("/ticket/{ticket_id}")
def get_ticket_detail(ticket_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id, models.Ticket.user_id == user.id).first()
    if not ticket:
        return {"success": False, "message": "Ticket not found"}
        
    messages = db.query(models.TicketMessage).filter(models.TicketMessage.ticket_id == ticket.id).order_by(models.TicketMessage.created_at).all()
    
    msg_list = []
    for m in messages:
        sender_name = "User"
        if m.sender_role == "admin":
            sender_name = "Support" # Or specific admin name if we tracked it, but schema only has role
            
        msg_list.append({
            "sender": m.sender_role, # frontend expects 'user' or 'admin' maybe? Docs say 'user'.
            "content": m.content,
            "time": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return {
        "success": True,
        "data": {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status,
            "type": ticket.type,
            "createdAt": ticket.created_at.strftime("%Y-%m-%d"),
            "messages": msg_list
        }
    }

@router.post("/ticket/{ticket_id}/reply")
def reply_ticket(ticket_id: int, data: dict = Body(...), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id, models.Ticket.user_id == user.id).first()
    if not ticket:
        return {"success": False, "message": "Ticket not found or closed"}
        
    if ticket.status == "closed":
        return {"success": False, "message": "Ticket is closed"}
        
    msg = models.TicketMessage(
        ticket_id=ticket.id,
        sender_role="user",
        content=data.get("content")
    )
    db.add(msg)
    
    # Update status? Maybe to 'open' if it was 'replied'?
    ticket.status = "open" 
    
    db.commit()
    return {"success": True}

# --- Admin APIs ---

@router.get("/admin/tickets")
def admin_get_tickets(admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).order_by(models.Ticket.id.desc()).all()
    data = []
    for t in tickets:
        user = db.query(models.User).filter(models.User.id == t.user_id).first()
        if user:
             nickname = user.nickname
             phone = user.phone
        else:
             nickname = "Unknown"
             phone = ""
             
        # Get Active Subscription for this user
        sub_name = "None"
        if user:
            active_sub = db.query(models.UserSubscription).join(models.SubscriptionPlan).filter(
                models.UserSubscription.user_id == user.id,
                models.UserSubscription.status == "active",
                models.UserSubscription.end_date > datetime.datetime.now()
            ).order_by(models.UserSubscription.end_date.desc()).first()
            
            if active_sub:
                 plan = db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.id == active_sub.plan_id).first()
                 if plan:
                    sub_name = plan.name
        
        data.append({
            "id": t.id,
            "title": t.title,
            "userNickname": nickname,
            "userPhone": phone,
            "userSubscription": sub_name,
            "status": t.status,
            "type": t.type,
            "createdAt": t.created_at.strftime("%Y-%m-%d")
        })
    return {"success": True, "data": data}

@router.get("/admin/tickets/{ticket_id}")
def admin_get_ticket_detail(ticket_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket: return {"success": False, "message": "Not Found"}
    
    messages = db.query(models.TicketMessage).filter(models.TicketMessage.ticket_id == ticket.id).order_by(models.TicketMessage.created_at).all()
    
    msg_list = []
    for m in messages:
        msg_list.append({
            "sender": m.sender_role,
            "content": m.content,
            "time": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return {
        "success": True,
        "data": {
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status,
            "type": ticket.type,
            "createdAt": ticket.created_at.strftime("%Y-%m-%d"),
            "messages": msg_list
        }
    }

@router.post("/admin/tickets/{ticket_id}/reply")
def admin_reply_ticket(ticket_id: int, data: dict = Body(...), admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket: return {"success": False, "message": "Not Found"}
    
    msg = models.TicketMessage(
        ticket_id=ticket.id,
        sender_role="admin",
        content=data.get("content")
    )
    db.add(msg)
    
    ticket.status = "replied"
    db.commit()
    return {"success": True}

@router.post("/admin/tickets/{ticket_id}/close")
def admin_close_ticket(ticket_id: int, admin: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if ticket:
        ticket.status = "closed"
        db.commit()
    return {"success": True}
