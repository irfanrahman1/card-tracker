"""Sign up, log in, log out, try the demo, change password, delete account."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import auth, models, schemas
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
