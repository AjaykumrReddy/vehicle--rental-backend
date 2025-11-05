from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, and_, or_
from uuid import UUID
from datetime import datetime, timezone
from typing import List
from ..db import get_db
from ..models import Conversation, Message, Booking, VehicleModel, User
from ..schemas import SendMessageRequest, MessageResponse, ConversationSummary
from ..auth import get_current_user
from .websocket import notify_new_message, notify_message_read
from ..logging_config import get_logger, log_error

logger = get_logger(__name__)

router = APIRouter(prefix="/messages", tags=["messaging"])

@router.post("/send")
async def send_message(
    message_data: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in a booking conversation"""
    try:
        user_id = UUID(current_user["user_id"])
        booking_id = message_data.booking_id
        
        # Verify booking exists and user is part of it
        booking = db.query(Booking).join(VehicleModel).filter(
            Booking.id == booking_id,
            or_(
                Booking.renter_id == user_id,
                VehicleModel.owner_id == user_id
            )
        ).first()
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied"
            )
        
        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.booking_id == booking_id
        ).first()
        
        if not conversation:
            # Create new conversation
            conversation = Conversation(
                booking_id=booking_id,
                owner_id=booking.vehicle.owner_id,
                renter_id=booking.renter_id
            )
            db.add(conversation)
            db.flush()
        
        # Create message
        message = Message(
            conversation_id=conversation.id,
            sender_id=user_id,
            message_text=message_data.message_text,
            message_type=message_data.message_type,
            attachment_url=message_data.attachment_url
        )
        db.add(message)
        
        # Update conversation
        conversation.last_message_at = datetime.now(timezone.utc)
        
        # Update unread counts
        if user_id == conversation.owner_id:
            conversation.renter_unread_count += 1
        else:
            conversation.owner_unread_count += 1
        
        db.commit()
        db.refresh(message)
        
        # Send real-time notification
        recipient_id = conversation.renter_id if user_id == conversation.owner_id else conversation.owner_id
        sender = db.query(User).filter(User.id == user_id).first()
        
        await notify_new_message(str(recipient_id), sender.full_name, {
            "id": str(message.id),
            "booking_id": str(booking_id),
            "sender_id": str(user_id),
            "sender_name": sender.full_name,
            "message_text": message.message_text,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat()
        })
        
        logger.info(f"Message sent successfully", extra={
            "message_id": str(message.id),
            "sender_id": str(user_id),
            "recipient_id": str(recipient_id),
            "booking_id": str(booking_id),
            "message_type": message.message_type,
            "message_length": len(message.message_text)
        })
        
        return {
            "success": True,
            "message_id": str(message.id),
            "message": "Message sent successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_error(logger, e, {
            "user_id": current_user.get("user_id"),
            "booking_id": str(message_data.booking_id),
            "message_type": message_data.message_type
        }, "send_message_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )

@router.get("/conversations")
def get_conversations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all conversations for current user"""
    try:
        user_id = UUID(current_user["user_id"])
        
        sql = """
            SELECT 
                c.id, c.booking_id, c.last_message_at,
                CASE 
                    WHEN c.owner_id = :user_id THEN c.owner_unread_count
                    ELSE c.renter_unread_count
                END as unread_count,
                CASE 
                    WHEN c.owner_id = :user_id THEN u_renter.full_name
                    ELSE u_owner.full_name
                END as other_user_name,
                CONCAT(v.brand, ' ', v.model, ' (', v.license_plate, ')') as vehicle_info,
                COALESCE(m.message_text, 'No messages yet') as last_message,
                CASE WHEN c.owner_id = :user_id THEN true ELSE false END as is_owner
            FROM conversations c
            JOIN bookings b ON c.booking_id = b.id
            JOIN vehicles v ON b.vehicle_id = v.id
            JOIN users u_owner ON c.owner_id = u_owner.id
            JOIN users u_renter ON c.renter_id = u_renter.id
            LEFT JOIN messages m ON m.id = (
                SELECT id FROM messages 
                WHERE conversation_id = c.id 
                ORDER BY created_at DESC 
                LIMIT 1
            )
            WHERE c.owner_id = :user_id OR c.renter_id = :user_id
            ORDER BY c.last_message_at DESC
        """
        
        result = db.execute(text(sql), {"user_id": str(user_id)}).fetchall()
        
        conversations = [
            {
                "id": str(row.id),
                "booking_id": str(row.booking_id),
                "other_user_name": row.other_user_name,
                "vehicle_info": row.vehicle_info,
                "last_message": row.last_message,
                "last_message_at": row.last_message_at.isoformat(),
                "unread_count": row.unread_count,
                "is_owner": row.is_owner
            }
            for row in result
        ]
        
        total_unread = sum(conv["unread_count"] for conv in conversations)
        
        return {
            "conversations": conversations,
            "total_unread": total_unread
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversations"
        )

@router.get("/conversations/{booking_id}/messages")
async def get_messages(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get messages for a specific booking conversation"""
    try:
        user_id = UUID(current_user["user_id"])
        booking_uuid = UUID(booking_id)
        
        # Verify booking exists and user has access
        booking = db.query(Booking).join(VehicleModel).filter(
            Booking.id == booking_uuid,
            or_(
                Booking.renter_id == user_id,
                VehicleModel.owner_id == user_id
            )
        ).first()
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or access denied"
            )
        
        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.booking_id == booking_uuid
        ).first()
        
        if not conversation:
            # Create new conversation
            conversation = Conversation(
                booking_id=booking_uuid,
                owner_id=booking.vehicle.owner_id,
                renter_id=booking.renter_id
            )
            db.add(conversation)
            db.flush()
        
        offset = (page - 1) * limit
        
        sql = """
            SELECT 
                m.id, m.sender_id, m.message_text, m.message_type,
                m.attachment_url, m.is_read, m.created_at,
                u.full_name as sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.conversation_id = :conversation_id
            ORDER BY m.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        
        result = db.execute(text(sql), {
            "conversation_id": str(conversation.id),
            "limit": limit,
            "offset": offset
        }).fetchall()
        
        messages = [
            {
                "id": str(row.id),
                "sender_id": str(row.sender_id),
                "sender_name": row.sender_name,
                "message_text": row.message_text,
                "message_type": row.message_type,
                "attachment_url": row.attachment_url,
                "is_read": row.is_read,
                "created_at": row.created_at.isoformat(),
                "is_own_message": str(row.sender_id) == str(user_id)
            }
            for row in reversed(result)  # Reverse to show oldest first
        ]
        
        # Mark messages as read and get message IDs
        unread_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.sender_id != user_id,
            Message.is_read == False
        ).all()
        
        if unread_messages:
            message_ids = [str(msg.id) for msg in unread_messages]
            
            # Update read status
            db.query(Message).filter(
                Message.conversation_id == conversation.id,
                Message.sender_id != user_id,
                Message.is_read == False
            ).update({"is_read": True, "read_at": datetime.now(timezone.utc)})
            
            # Reset unread count
            if user_id == conversation.owner_id:
                conversation.owner_unread_count = 0
                sender_id = conversation.renter_id
            else:
                conversation.renter_unread_count = 0
                sender_id = conversation.owner_id
            
            db.commit()
            
            # Send real-time read notification
            await notify_message_read(str(sender_id), message_ids)
        else:
            db.commit()
        
        return {
            "messages": messages,
            "has_more": len(result) == limit
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch messages"
        )

@router.get("/unread-count")
def get_unread_count(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get total unread message count for user"""
    try:
        user_id = UUID(current_user["user_id"])
        
        sql = """
            SELECT SUM(
                CASE 
                    WHEN owner_id = :user_id THEN owner_unread_count
                    ELSE renter_unread_count
                END
            ) as total_unread
            FROM conversations
            WHERE owner_id = :user_id OR renter_id = :user_id
        """
        
        result = db.execute(text(sql), {"user_id": str(user_id)}).scalar()
        
        return {"unread_count": result or 0}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count"
        )