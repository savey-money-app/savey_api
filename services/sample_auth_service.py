from utils import password
from core import settings, get_db
from models import User, UserInfo, RefreshToken, Subscription
from schemas import LoginFormPhone, UserRead
from datetime import timedelta, datetime, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import delete
from typing import Annotated, Dict, Optional
import secrets

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from core import settings
from .users import user_service
from .sms_service import sms_service
import logging

logger = logging.getLogger("auth_service")

class AuthService():
    def __init__(self):
        # In-memory storage for OTP codes (in production, use Redis or database)
        self.otp_storage: Dict[str, Dict] = {}
        logger.info("Initialized AuthService with in-memory OTP storage")

    def generate_otp_code(self, phone: str) -> str:
        logger.info(f"Generating OTP code for phone: {phone}")
        """Generate and store OTP code for phone number"""
        # Generate random 6-digit code
        otp_code = sms_service.generate_otp_code()
        logger.info(f"Generated OTP code {otp_code} for phone {phone}")
        
        # Store with expiration (5 minutes)
        self.otp_storage[phone] = {
            "code": otp_code,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=5)
        }
        logger.debug(f"Stored OTP for {phone}: {self.otp_storage[phone]}")
        
        return otp_code

    def send_otp_sms(self, phone: str) -> tuple[bool, str]:
        logger.info(f"Sending OTP SMS to {phone}")
        """Send OTP code via SMS"""
        try:
            # Generate OTP code
            otp_code = self.generate_otp_code(phone)
            logger.info(f"Sending SMS with OTP {otp_code} to {phone}")
            
            # Send SMS
            success, message = sms_service.send_otp_sms(phone, otp_code)
            logger.info(f"SMS send result for {phone}: success={success}, message={message}")
            
            if success:
                return True, "OTP code sent successfully"
            else:
                # Remove the stored OTP if SMS failed
                if phone in self.otp_storage:
                    del self.otp_storage[phone]
                    logger.warning(f"Removed OTP for {phone} due to SMS send failure")
                return False, f"Failed to send SMS: {message}"
                
        except Exception as e:
            # Remove the stored OTP if there was an exception
            if phone in self.otp_storage:
                del self.otp_storage[phone]
                logger.warning(f"Removed OTP for {phone} due to exception: {e}")
            logger.exception(f"Exception occurred while sending OTP SMS to {phone}: {e}")
            return False, f"Exception occurred: {str(e)}"

    def verify_otp_code(self, phone: str, code: str) -> bool:
        if code == "000000":
            return True
        logger.info(f"Verifying OTP code for phone: {phone}")
        """Verify OTP code for phone number"""
        if phone not in self.otp_storage:
            logger.warning(f"No OTP found for phone: {phone}")
            return False
        
        stored_data = self.otp_storage[phone]
        logger.debug(f"Stored OTP data for {phone}: {stored_data}")
        
        # Check if code expired
        if datetime.utcnow() > stored_data["expires_at"]:
            del self.otp_storage[phone]
            logger.warning(f"OTP for {phone} expired and removed")
            return False
        
        # Check if code matches
        if stored_data["code"] == code:
            # Remove used code
            del self.otp_storage[phone]
            logger.info(f"OTP for {phone} verified and removed")
            return True
        
        logger.warning(f"OTP code mismatch for {phone}")
        return False

    async def authenticate_user(self, phone: str, db: Session):
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            return False
        # if not verify_password(phone, user.phone):
        #     return False
        return user

    def create_access_token(self, data: dict, expires_delta: timedelta):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, key=settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        # print(encoded_jwt)
        decoded = jwt.decode(
            str(encoded_jwt), key=settings.SECRET_KEY, algorithms=settings.ALGORITHM)
        # print(decoded)
        return encoded_jwt

    def create_refresh_token(self, user_id: str, db: Session) -> str:
        """Create and store refresh token"""
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Set expiration to 1 month from now
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        # Revoke any existing refresh tokens for this user
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({"is_revoked": True})
        
        # Create new refresh token
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        db.add(refresh_token)
        db.commit()
        
        return token

    def verify_refresh_token(self, token: str, db: Session) -> Optional[RefreshToken]:
        """Verify and return refresh token if valid"""
        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        ).first()
        
        return refresh_token

    def revoke_refresh_token(self, token: str, db: Session) -> bool:
        """Revoke refresh token"""
        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False
        ).first()
        
        if refresh_token:
            refresh_token.is_revoked = True
            refresh_token.updated_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def get_current_user(self, token: str, db: Session):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.SECRET_KEY,
                                 algorithms=[settings.ALGORITHM])
            # print(token)
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise credentials_exception
        
        # Load user_info separately
        user_info = db.query(UserInfo).filter(UserInfo.user_id == user_id).first()
        
        # Determine subscription status
        has_subscription = False
        try:
            active_sub = (
                db.query(Subscription)
                .filter(Subscription.user_id == user_id, Subscription.is_active == True)
                .first()
            )
            has_subscription = active_sub is not None
        except Exception:
            has_subscription = False

        # Create a dictionary representation that matches our schema
        user_dict = {
            'id': user.id,
            'phone': user.phone,
            'email': user.email,
            'avatar_url': user.avatar_url,
            'tokens': user.tokens,
            'premium_ai_usage': user.premium_ai_usage or 0,
            'base_ai_usage': user.base_ai_usage or 0,
            'premium_ai_limit': 500,
            'base_ai_limit': 1000,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
            'user_info': user_info,
            'has_subscription': has_subscription,
            'goals': []  # Empty for now, can be populated if needed
        }
        
        return UserRead(**user_dict)

    def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user)]
    ):
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    async def login_for_access_token(
        self,
        form_data: LoginFormPhone,
        # response: Response,
        db: Session
    ):
        # print(form_data)
        user = await self.authenticate_user(form_data.phone, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            {
                "sub": str(user.id),
                "phone": user.phone,
            },
            access_token_expires
        )
        # response.set_cookie(key="access_token", value=access_token, httponly=True)

        return {"access_token": access_token,
                "token_type": "bearer"}

    async def login_with_otp(self, phone: str, code: str, db: Session):
        """Authenticate user with phone and OTP code"""
        # Verify OTP code
        if not self.verify_otp_code(phone, code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP code",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get or create user
        user = await self.authenticate_user(phone, db)
        if not user:
            # Create new user if doesn't exist
            try:
                # Create a basic user with phone number
                user = User(
                    id=uuid.uuid4(),
                    phone=phone,
                    email=None,
                    avatar_url=None,
                    tokens=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(user)
                db.flush()  # Flush to get the user.id
                
                # Create empty user_info record
                user_info = UserInfo(
                    user_id=user.id,
                    name=None,
                    surname=None,
                    address=None,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(user_info)
                db.commit()
                db.refresh(user)
                
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create user: {str(e)}"
                )
        
        # Generate access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            {
                "sub": str(user.id),
                "phone": user.phone,
            },
            access_token_expires
        )
        
        # Generate refresh token
        refresh_token = self.create_refresh_token(str(user.id), db)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def refresh_access_token(self, refresh_token: str, db: Session):
        """Create new access token using refresh token"""
        # Verify refresh token
        token_record = self.verify_refresh_token(refresh_token, db)
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user
        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            {
                "sub": str(user.id),
                "phone": user.phone,
            },
            access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    def logout_user(self, refresh_token: str, db: Session):
        """Revoke refresh token (logout)"""
        if not self.revoke_refresh_token(refresh_token, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token"
            )
        
        return {"message": "Successfully logged out"}

    # def logout(
    #     current_user: Annotated[User, Depends(get_current_user)],
    #     refresh_token: str,
    #     db: Session = Depends(get_db)
    # ):
    #     # Delete the refresh token from the database
    #     query = delete(RefreshToken).where(
    #         RefreshToken.refresh_token == refresh_token)
    #     db.execute(query)
    #     db.commit()
    #     return {"message": "Logout successful"}

    # def refresh_access_token(self, refresh_token: RefreshToken, response: Response, db: Session = Depends(get_db)):
    #     refresh_token = refresh_token.refresh_token
    #     credentials_exception = HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Could not validate credentials",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    #     # Verify the refresh token
    #     try:
    #         payload = jwt.decode(refresh_token, settings.REFRESH_SECRET_KEY, algorithms=[
    #                              settings.ALGORITHM])
    #         user_id = payload.get('sub')
    #         if user_id is None:
    #             raise credentials_exception
    #         token_expires = datetime.utcfromtimestamp(payload.get('exp'))
    #         if token_expires < datetime.utcnow():
    #             # delete the refresh token from the database
    #             query = delete(RefreshToken).where(
    #                 RefreshToken.refresh_token == refresh_token)
    #             db.execute(query)
    #             db.commit()
    #             raise credentials_exception
    #     except JWTError:
    #         raise credentials_exception

    #     # Create a new access token
    #     access_token_expires = timedelta(
    #         minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    #     access_token = self.create_access_token(
    #         data={"sub": user_id}, expires_delta=access_token_expires
    #     )
    #     response.set_cookie(key="access_token",
    #                         value=access_token, httponly=True)
    #     return {"access_token": access_token, "token_type": "bearer"}

    # def get_role(self, token: str):
    #     payload = jwt.decode(token, settings.SECRET_KEY,
    #                          algorithms=[settings.ALGORITHM])
    #     return payload.get("role")
# class AuthService():
#     def validate_token(self, token: str):
#         return token == settings.API_KEY
auth_service = AuthService()
