import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from pwdlib import PasswordHash
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
    create_engine, select, desc, func, or_, event
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker

APP_NAME = "لُب | Lub"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lub_dev.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Development-only fallback. Production startup is intentionally blocked without a secret.
    if os.getenv("RENDER") == "true" or os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("SECRET_KEY must be configured in production.")
    SECRET_KEY = "local-development-only-" + secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "24"))
PUBLIC_ORIGIN = os.getenv("PUBLIC_ORIGIN", "")
IS_PROD = os.getenv("ENVIRONMENT") == "production" or os.getenv("RENDER") == "true"

engine_args = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_args)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

class Base(DeclarativeBase):
    pass

def now_utc():
    return datetime.now(timezone.utc)

def new_id():
    return str(uuid4())

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(String(255))
    bio: Mapped[str] = mapped_column(String(240), default="")
    profile_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    intention: Mapped[str] = mapped_column(String(30), index=True)
    topic: Mapped[str] = mapped_column(String(60), default="عام", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    confirm_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    author: Mapped["User"] = relationship()
    comments: Mapped[list["Comment"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("id", "author_id", name="uq_post_owner"),)

class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    author: Mapped["User"] = relationship()

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("post_id", "user_id", "kind", name="uq_signal_once"),)

class SavedPost(Base):
    __tablename__ = "saved_posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_saved_once"),)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(String(1000), default="")
    state: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    object_type: Mapped[str] = mapped_column(String(30))
    object_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

Base.metadata.create_all(engine)
app = FastAPI(title=APP_NAME, version="0.1.0", description="Arabic-first intentional social network MVP")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=10, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class ProfileIn(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)
    bio: str = Field(default="", max_length=240)
    profile_hidden: bool = False

class PostIn(BaseModel):
    body: str = Field(min_length=8, max_length=1800)
    intention: str
    topic: str = Field(default="عام", min_length=1, max_length=60)

class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

class SignalIn(BaseModel):
    kind: str

class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=80)
    details: str = Field(default="", max_length=1000)

class UserOut(BaseModel):
    id: str
    username: str
    display_name: str
    bio: str
    profile_hidden: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

def audit(db: Session, actor: Optional[str], action: str, object_type: str, object_id: str, detail: str = ""):
    db.add(AuditEvent(actor_id=actor, action=action, object_type=object_type, object_id=object_id, detail=detail[:500]))

def create_token(user: User):
    exp = now_utc() + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": user.id, "exp": exp, "iat": now_utc()}, SECRET_KEY, algorithm=JWT_ALGORITHM)

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not creds:
        raise HTTPException(status_code=401, detail="سجّل الدخول للمتابعة.")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="جلسة غير صالحة أو منتهية. سجّل الدخول مجددًا.")
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="الحساب غير متاح.")
    return user

def post_out(db: Session, post: Post, viewer_id: Optional[str] = None):
    comments = db.scalars(select(Comment).where(Comment.post_id == post.id).order_by(Comment.created_at.asc()).limit(100)).all()
    saved = bool(viewer_id and db.scalar(select(SavedPost.id).where(SavedPost.post_id == post.id, SavedPost.user_id == viewer_id).limit(1)))
    my_signals = set(db.scalars(select(Signal.kind).where(Signal.post_id == post.id, Signal.user_id == viewer_id)).all()) if viewer_id else set()
    # Public counters are intentionally omitted: this product is not an engagement leaderboard.
    return {
        "id": post.id, "body": post.body, "intention": post.intention, "topic": post.topic,
        "status": post.status, "created_at": post.created_at, "confirm_after": post.confirm_after,
        "published_at": post.published_at,
        "author": {"username": post.author.username, "display_name": post.author.display_name, "bio": post.author.bio},
        "comments": [{"id": c.id, "body": c.body, "created_at": c.created_at,
                      "author": {"username": c.author.username, "display_name": c.author.display_name}} for c in comments],
        # Signal membership is private to the viewer; do not expose aggregate counts.
        "saved": saved, "my_signals": sorted(my_signals)
    }

def get_post_or_404(db: Session, post_id: str):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="المنشور غير موجود.")
    return post

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
        return {
            "status": "ok",
            "service": "lub-social",
            "database": "reachable",
            "database_backend": engine.dialect.name,
            "postgres_configured": engine.dialect.name == "postgresql",
            "version": "0.1.1"
        }
    except Exception:
        raise HTTPException(status_code=503, detail="database_unavailable")

@app.get("/api/meta")
def meta():
    return {"name": APP_NAME, "principles": ["slow-social", "proof-of-meaning", "no-public-like-counts"],
            "intentions": ["أفيد", "أتعلم", "أوثّق ذكرى", "أطلب مساعدة"],
            "signals": ["استفدت", "فكرت", "تواصلت معك"], "fridge_hours": 12}

@app.post("/api/auth/register", status_code=201)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()
    username = data.username.lower().strip()
    if db.scalar(select(User.id).where(or_(User.email == email, User.username == username))):
        raise HTTPException(status_code=409, detail="البريد أو اسم المستخدم مستخدم بالفعل.")
    user = User(email=email, username=username, display_name=data.display_name.strip(),
                password_hash=password_hash.hash(data.password))
    db.add(user)
    db.flush()
    audit(db, user.id, "account.registered", "user", user.id, "email verification not yet enabled")
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer", "user": UserOut.model_validate(user)}

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower().strip()))
    if not user or not user.is_active or not password_hash.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="البريد أو كلمة المرور غير صحيحة.")
    audit(db, user.id, "account.login", "user", user.id)
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer", "user": UserOut.model_validate(user)}

@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.patch("/api/profile", response_model=UserOut)
def update_profile(data: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.display_name = data.display_name.strip()
    user.bio = data.bio.strip()
    user.profile_hidden = data.profile_hidden
    audit(db, user.id, "profile.updated", "user", user.id)
    db.commit()
    db.refresh(user)
    return user

@app.get("/api/profiles/{username}")
def public_profile(username: str, viewer: Optional[User] = Depends(lambda: None), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.username == username.lower()))
    if not target or not target.is_active:
        raise HTTPException(status_code=404, detail="الملف غير موجود.")
    if target.profile_hidden:
        raise HTTPException(status_code=404, detail="هذا الملف مخفي.")
    return {"id": target.id, "username": target.username, "display_name": target.display_name,
            "bio": target.bio, "created_at": target.created_at}

@app.post("/api/posts", status_code=201)
def create_post(data: PostIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    allowed = {"أفيد", "أتعلم", "أوثّق ذكرى", "أطلب مساعدة"}
    if data.intention not in allowed:
        raise HTTPException(status_code=422, detail="اختار قصدًا من الخيارات المتاحة.")
    body = data.body.strip()
    if len(body) < 8:
        raise HTTPException(status_code=422, detail="المنشور قصير جدًا.")
    created = now_utc()
    post = Post(author_id=user.id, body=body, intention=data.intention, topic=data.topic.strip() or "عام",
                status="pending", created_at=created, confirm_after=created + timedelta(hours=12))
    db.add(post)
    db.flush()
    audit(db, user.id, "post.staged", "post", post.id, "12-hour confirmation window")
    db.commit()
    db.refresh(post)
    return post_out(db, post, user.id)

@app.get("/api/posts")
def list_posts(sort: str = "new", intention: Optional[str] = None, limit: int = 30, offset: int = 0,
               creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 50)); offset = max(0, offset)
    viewer_id = None
    if creds:
        try:
            viewer_id = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM]).get("sub")
        except jwt.PyJWTError:
            viewer_id = None
    q = select(Post).join(User, User.id == Post.author_id).where(Post.status == "published", User.is_active == True)
    q = q.where(or_(User.profile_hidden == False, User.id == viewer_id))
    if intention:
        q = q.where(Post.intention == intention)
    if sort == "help":
        q = q.where(Post.intention == "أطلب مساعدة").order_by(desc(Post.published_at))
    else:
        q = q.order_by(desc(Post.published_at), desc(Post.created_at))
    posts = db.scalars(q.offset(offset).limit(limit)).all()
    return {"items": [post_out(db, p, viewer_id) for p in posts], "limit": limit, "offset": offset}

@app.get("/api/posts/mine")
def my_posts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    posts = db.scalars(select(Post).where(Post.author_id == user.id, Post.status.in_(["pending", "published"])).order_by(desc(Post.created_at)).limit(100)).all()
    return {"items": [post_out(db, p, user.id) for p in posts]}

@app.post("/api/posts/{post_id}/confirm")
def confirm_post(post_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = get_post_or_404(db, post_id)
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="تقدر تأكد منشوراتك فقط.")
    if post.status != "pending":
        raise HTTPException(status_code=409, detail="المنشور ليس في حالة انتظار.")
    after = post.confirm_after
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    if now_utc() < after:
        remaining = int((after - now_utc()).total_seconds())
        raise HTTPException(status_code=409, detail={"message": "لسه ماكملش 12 ساعة في الثلاجة.", "seconds_remaining": remaining})
    post.status = "published"
    post.published_at = now_utc()
    audit(db, user.id, "post.published", "post", post.id, "confirmed after fridge interval")
    db.commit()
    db.refresh(post)
    return post_out(db, post, user.id)

@app.patch("/api/posts/{post_id}")
def edit_post(post_id: str, data: PostIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = get_post_or_404(db, post_id)
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="مش من حقك تعدّل المنشور ده.")
    if post.status != "pending":
        raise HTTPException(status_code=409, detail="التعديل متاح أثناء وجود المنشور في الثلاجة فقط.")
    if data.intention not in {"أفيد", "أتعلم", "أوثّق ذكرى", "أطلب مساعدة"}:
        raise HTTPException(status_code=422, detail="اختار قصدًا صالحًا.")
    post.body = data.body.strip(); post.intention = data.intention; post.topic = data.topic.strip() or "عام"; post.edited_at = now_utc()
    audit(db, user.id, "post.edited", "post", post.id)
    db.commit()
    return post_out(db, post, user.id)

@app.delete("/api/posts/{post_id}", status_code=204)
def delete_post(post_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = get_post_or_404(db, post_id)
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="مش من حقك تحذف المنشور ده.")
    audit(db, user.id, "post.deleted", "post", post.id)
    db.delete(post); db.commit()
    return None

@app.post("/api/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: str, data: CommentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = get_post_or_404(db, post_id)
    if post.status != "published":
        raise HTTPException(status_code=409, detail="التعليق متاح بعد النشر فقط.")
    comment = Comment(post_id=post.id, author_id=user.id, body=data.body.strip())
    db.add(comment); db.flush()
    audit(db, user.id, "comment.created", "comment", comment.id)
    db.commit()
    return {"id": comment.id, "body": comment.body, "created_at": comment.created_at,
            "author": {"username": user.username, "display_name": user.display_name}}

@app.put("/api/posts/{post_id}/signals/{kind}")
def toggle_signal(post_id: str, kind: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if kind not in {"استفدت", "فكرت", "تواصلت معك"}:
        raise HTTPException(status_code=422, detail="إشارة غير معروفة.")
    post = get_post_or_404(db, post_id)
    if post.status != "published":
        raise HTTPException(status_code=409, detail="الإشارات متاحة للمنشورات المنشورة فقط.")
    existing = db.scalar(select(Signal).where(Signal.post_id == post.id, Signal.user_id == user.id, Signal.kind == kind))
    if existing:
        db.delete(existing); active = False
    else:
        db.add(Signal(post_id=post.id, user_id=user.id, kind=kind)); active = True
    audit(db, user.id, "signal.toggled", "post", post.id, kind)
    db.commit()
    return {"active": active, "kind": kind}

@app.put("/api/posts/{post_id}/save")
def toggle_save(post_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = get_post_or_404(db, post_id)
    existing = db.scalar(select(SavedPost).where(SavedPost.post_id == post.id, SavedPost.user_id == user.id))
    if existing:
        db.delete(existing); active = False
    else:
        db.add(SavedPost(post_id=post.id, user_id=user.id)); active = True
    db.commit()
    return {"saved": active}

@app.get("/api/saved")
def saved_posts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    posts = db.scalars(select(Post).join(SavedPost, SavedPost.post_id == Post.id).where(SavedPost.user_id == user.id).order_by(desc(SavedPost.created_at)).limit(100)).all()
    return {"items": [post_out(db, p, user.id) for p in posts if p.status == "published" or p.author_id == user.id]}

@app.post("/api/posts/{post_id}/reports", status_code=201)
def report_post(post_id: str, data: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = get_post_or_404(db, post_id)
    if post.author_id == user.id:
        raise HTTPException(status_code=422, detail="مينفعش تبلغ عن منشورك.")
    duplicate = db.scalar(select(Report.id).where(Report.post_id == post.id, Report.reporter_id == user.id, Report.state == "open"))
    if duplicate:
        raise HTTPException(status_code=409, detail="سبق وقدمت بلاغًا مفتوحًا عن المنشور.")
    report = Report(post_id=post.id, reporter_id=user.id, reason=data.reason, details=data.details.strip())
    db.add(report); db.flush()
    audit(db, user.id, "report.created", "report", report.id)
    db.commit()
    return {"id": report.id, "state": report.state, "message": "تم تسجيل البلاغ للمراجعة. البلاغ وحده لا يثبت المخالفة."}

@app.get("/api/discovery/topics")
def topics(db: Session = Depends(get_db)):
    rows = db.execute(select(Post.topic, func.count(Post.id)).where(Post.status == "published").group_by(Post.topic).order_by(desc(func.count(Post.id))).limit(20)).all()
    return {"items": [{"topic": r[0], "posts": r[1]} for r in rows]}

@app.get("/api/admin/audit")
def audit_feed(limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Private development endpoint: only visible to the account configured as ADMIN_EMAIL.
    if user.email != os.getenv("ADMIN_EMAIL", "").lower():
        raise HTTPException(status_code=403, detail="غير مصرح.")
    rows = db.scalars(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(max(1, min(limit, 200)))).all()
    return {"items": [{"action": x.action, "object_type": x.object_type, "object_id": x.object_id,
                       "detail": x.detail, "created_at": x.created_at} for x in rows]}

@app.delete("/api/account", status_code=204)
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user_id = user.id
    audit(db, user_id, "account.deletion_requested", "user", user_id, "self-service deletion")
    db.commit()
    db.delete(user)
    db.commit()
    return None
