import uuid
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    name = Column(String)
    username = Column(String)
    phone = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True) # 'EA' or 'VPS'
    name = Column(String, index=True)
    price = Column(Float)
    duration = Column(Integer) # in months
    active = Column(Boolean, default=True)
    description = Column(Text)

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    order_type = Column(String) # 'EA' or 'VPS'
    mt5_id = Column(String, nullable=True) # captured before payment
    # pending, paid, compiling, ready, delivered, expired, cancelled
    status = Column(String, default="pending")
    
    # Installment fields
    installment_enabled = Column(Boolean, default=False)
    installment_total_amount = Column(Float, nullable=True)
    installment_amount = Column(Float, nullable=True)
    installment_count = Column(Integer, nullable=True)
    installments_paid = Column(Integer, default=0)
    amount_paid = Column(Float, default=0.0)
    amount_remaining = Column(Float, nullable=True)
    next_due_date = Column(DateTime(timezone=True), nullable=True)
    license_period_days = Column(Integer, nullable=True)
    grace_days = Column(Integer, default=5)
    installment_status = Column(String, default="active") # active, completed, defaulted

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class InstallmentPayment(Base):
    __tablename__ = "installment_payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    amount = Column(Float)
    payment_number = Column(Integer)
    payment_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="confirmed")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    razorpay_order_id = Column(String, unique=True)
    payment_id = Column(String)
    amount = Column(Float)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True) # nullable for manual/trial grants
    user_id = Column(Integer, ForeignKey("users.id"))
    mt5_id = Column(String)
    broker = Column(String, nullable=True)
    license_type = Column(String, default="paid") # 'paid' or 'trial'
    purchase_date = Column(DateTime(timezone=True), server_default=func.now())
    expiry_date = Column(DateTime(timezone=True))
    license_uuid = Column(String, default=lambda: str(uuid.uuid4()), unique=True)
    generated_filename = Column(String) # This will be the path to the ZIP file
    download_count = Column(Integer, default=0)
    renew_count = Column(Integer, default=0)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CompileJob(Base):
    __tablename__ = "compile_jobs"

    id = Column(Integer, primary_key=True, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    status = Column(String, default="pending") # pending, processing, completed, failed
    logs = Column(Text, nullable=True)
    worker_id = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class EaTemplate(Base):
    """A versioned copy of the EA source (.mq5) template used by the
    windows-worker to compile customer EAs. Uploaded/replaced from the web
    admin UI so the client can hand over a new EA file without anyone
    touching code. Exactly one row should have is_active=True at a time -
    that's the version the worker fetches before compiling."""
    __tablename__ = "ea_templates"

    id = Column(Integer, primary_key=True, index=True)
    version_label = Column(String, nullable=True)
    filename = Column(String)
    source_code = Column(Text)
    file_size = Column(Integer, default=0)
    is_active = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    uploaded_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class VpsOrder(Base):
    __tablename__ = "vps_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    duration = Column(Integer)
    status = Column(String, default="pending")
    ip = Column(String)
    username = Column(String)
    password = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    message = Column(Text)
    status = Column(String, default="unread")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TrialSetting(Base):
    __tablename__ = "trial_settings"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=True)
    # Business rule: free trial is 3 days, once per Telegram ID per calendar
    # month. These defaults must match that rule exactly - the actual
    # enforcement in trials.py request_free_trial() also allows exactly one
    # claim per telegram_id per calendar month regardless of this setting.
    duration_days = Column(Integer, default=3)
    max_trials_per_month = Column(Integer, default=1)
    allow_existing_customers = Column(Boolean, default=False)
    trial_plan_name = Column(String, default="Trial EA")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TrialActivation(Base):
    __tablename__ = "trial_activations"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, index=True)
    mt5_id = Column(String, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    month_key = Column(String, index=True) # e.g. "2026-08"
    status = Column(String, default="active") # active, expired, revoked
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TrialClaim(Base):
    __tablename__ = "trial_claims"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, index=True)
    claim_month = Column(String, index=True) # "YYYY-MM"
    license_id = Column(Integer, ForeignKey("licenses.id"))
    mt5_id = Column(String)
    claimed_at = Column(DateTime(timezone=True), server_default=func.now())

class LicenseMt5History(Base):
    __tablename__ = "license_mt5_history"

    id = Column(Integer, primary_key=True, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    old_mt5_id = Column(String)
    new_mt5_id = Column(String)
    change_reason = Column(String)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_by = Column(String, nullable=True)

class BrokerChangeRequest(Base):
    __tablename__ = "broker_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    license_id = Column(Integer, ForeignKey("licenses.id"))
    old_mt5_id = Column(String)
    old_broker = Column(String, nullable=True)
    new_mt5_id = Column(String)
    new_broker = Column(String, nullable=True)
    status = Column(String, default="pending_broker_change_approval")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AdminSettings(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String, unique=True, index=True)
    setting_value = Column(String)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
