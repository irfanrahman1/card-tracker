"""Sign up, log in, log out, try the demo, change password, delete account."""
import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import auth, emailer, models, schemas
from ..auth import current_user, limiter
from ..database import get_db
from .demo import load_demo_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.UserOut, status_code=201)
def signup(payload: schemas.CredentialsIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create an account and log in. Needs only an email and a password."""
    ip = f"ip:{auth.client_ip(request)}"
    limiter.check(db, ip)
    email = auth.normalize_email(payload.email)
    auth.check_new_password(payload.password, email)
    if db.scalar(select(models.User).where(models.User.email == email)):
        limiter.failed(db, ip)  # stops anyone probing many emails quickly
        raise HTTPException(409, "An account with this email already exists. Try logging in.")
    first_real_user = not db.scalar(select(func.count()).select_from(models.User).where(models.User.is_demo.is_(False)))
    user = models.User(email=email, password_hash=auth.hash_password(payload.password))
    db.add(user)
    db.commit()
    if first_real_user:
        auth.claim_legacy_data(db, user)  # your data from before accounts existed
    auth.start_session(db, response, user)
    return user


@router.post("/login", response_model=schemas.UserOut)
def login(payload: schemas.CredentialsIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Log in. The same vague error for a wrong email or a wrong password, so it
    doesn't reveal who has an account."""
    email = (payload.email or "").strip().lower()
    keys = (f"ip:{auth.client_ip(request)}", f"email:{email}")
    limiter.check(db, *keys)
    user = db.scalar(select(models.User).where(models.User.email == email, models.User.is_demo.is_(False)))
    # Check a dummy hash when there's no such user, so both cases take the same time.
    ok = auth.verify_password(user.password_hash if user else auth._DUMMY_HASH, payload.password)
    if not (user and ok):
        limiter.failed(db, *keys)
        raise HTTPException(401, "Email or password is incorrect")
    limiter.succeeded(db, *keys)
    auth.start_session(db, response, user)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth.end_session(db, request, response)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    """Who's logged in (401 if nobody)."""
    return user


@router.post("/demo", response_model=schemas.UserOut, status_code=201)
def try_demo(request: Request, response: Response, db: Session = Depends(get_db)):
    """A throwaway account with sample cards and purchases. Deleted after 24 hours."""
    ip = f"demo:{auth.client_ip(request)}"
    limiter.check(db, ip)
    limiter.failed(db, ip)  # counts toward a limit so one visitor can't create thousands
    auth.delete_expired(db)
    user = models.User(email=f"demo-{secrets.token_hex(6)}@demo.local",
                       password_hash=auth.hash_password(secrets.token_urlsafe(24)), is_demo=True)
    db.add(user)
    db.commit()
    load_demo_data(db, user)
    auth.start_session(db, response, user)
    return user


@router.post("/change-password", status_code=204)
def change_password(payload: schemas.ChangePasswordIn, request: Request, response: Response,
                    db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    """Change your password. Logs out your other devices."""
    if user.is_demo:
        raise HTTPException(400, "Demo accounts don't have a password")
    if not auth.verify_password(user.password_hash, payload.current_password):
        raise HTTPException(401, "Current password is incorrect")
    auth.check_new_password(payload.new_password, user.email)
    user.password_hash = auth.hash_password(payload.new_password)
    db.query(models.LoginSession).filter(models.LoginSession.user_id == user.id).delete()
    db.commit()
    auth.start_session(db, response, user)


@router.post("/delete-account", status_code=204)
def delete_account(payload: schemas.PasswordIn, request: Request, response: Response,
                   db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    """Permanently delete your account and every card, purchase and setting in it."""
    if not user.is_demo and not auth.verify_password(user.password_hash, payload.password):
        raise HTTPException(401, "Password is incorrect")
    auth.delete_user_data(db, user.id)
    db.delete(user)
    db.commit()
    response.delete_cookie(auth.COOKIE_NAME, path="/")


# ---------- Forgot password ----------

RESET_MINUTES = 30
# Where reset links point. Set APP_URL to your site's address in production. It's never
# taken from the request, so a forged Host header can't redirect links elsewhere.
APP_URL = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")


@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Email a one-time reset link. Always gives the same answer, so it doesn't reveal
    whether an email has an account."""
    email = (payload.email or "").strip().lower()
    keys = (f"reset-ip:{auth.client_ip(request)}", f"reset-email:{email}")
    limiter.check(db, *keys)
    limiter.failed(db, *keys)  # every request counts, so the form can't be used to spam inboxes
    user = db.scalar(select(models.User).where(models.User.email == email, models.User.is_demo.is_(False)))
    if user:
        token = secrets.token_urlsafe(32)
        db.add(models.PasswordReset(user_id=user.id, token_hash=auth._hash_token(token),
                                    expires_at=auth.utcnow() + timedelta(minutes=RESET_MINUTES)))
        db.commit()
        emailer.send_email(
            user.email,
            "Reset your Card Tracker password",
            f"Someone asked to reset the password for your Card Tracker account.\n\n"
            f"To choose a new password, open this link within {RESET_MINUTES} minutes:\n"
            f"{APP_URL}/?reset={token}\n\n"
            f"If it wasn't you, ignore this email. Your password won't change.",
        )
    return {"message": "If that email has an account, a reset link is on its way."}


@router.post("/reset-password", response_model=schemas.UserOut)
def reset_password(payload: schemas.ResetPasswordIn, request: Request, response: Response,
                   db: Session = Depends(get_db)):
    """Set a new password with a reset link. Logs out every other device, then logs you in."""
    reset = db.scalar(select(models.PasswordReset).where(
        models.PasswordReset.token_hash == auth._hash_token(payload.token)))
    if not reset or reset.used or reset.expires_at < auth.utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired. Ask for a new one.")
    user = db.get(models.User, reset.user_id)
    auth.check_new_password(payload.new_password, user.email)
    user.password_hash = auth.hash_password(payload.new_password)
    # Use up this link and any others for the account, and log out everywhere.
    db.query(models.PasswordReset).filter(models.PasswordReset.user_id == user.id).update({"used": True})
    db.query(models.LoginSession).filter(models.LoginSession.user_id == user.id).delete()
    db.commit()
    auth.start_session(db, response, user)
    return user
