import logging
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

import bcrypt
from jose import JWTError, jwt

from src.config import settings, prisma
from src.services.email_service import send_otp_email
from .schema import (
    SignupRequest, SignupResponse, LoginResponse, UserResponse,
    TenantResponse, WorkspaceResponse, ProjectResponse,
    SubscriptionResponse, SignupInitialResponse,
)

logger = logging.getLogger(__name__)

# Default roles to create for new tenants
DEFAULT_ROLES = [
    {"name": "ADMIN", "description": "Full access to tenant and workspaces"},
    {"name": "TESTER", "description": "Can create and run tests"},
    {"name": "QA", "description": "Can review results"},
    {"name": "AUDIT", "description": "Read-only access"}
]

def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiration_days)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

async def ensure_global_permissions():
    """
    Ensure all system permissions exist globally.
    Does NOT need to be in a transaction as Permissions are global.
    """
    resources = ["UPLOAD_SWAGGER", "TEST_CASE", "TEST_RUN", "REPORT", "PROJECT", "MEMBER", "ROLE"]
    actions = ["READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "MANAGE"]
    
    to_check = []
    for res in resources:
        for act in actions:
            to_check.append({
                "name": f"{act} {res}".replace("_", " ").title(),
                "resource": res.upper(),
                "action": act
            })
            
    # Fetch all existing to avoid duplicate checks
    existing = await prisma.permission.find_many()
    existing_keys = {(p.resource, p.action) for p in existing}
    
    needed = [p for p in to_check if (p["resource"], p["action"]) not in existing_keys]

    if needed:
        logger.info("Seeding %d global permissions", len(needed))
        await prisma.permission.create_many(data=needed)

def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


def _get_is_verified(user: object) -> bool:
    """Safely read `isVerified` from a Prisma User model.

    If the running environment has an out-of-date generated Prisma client
    (common when running `uvicorn` from a global/Conda Python), the model won't
    contain the field and attribute access will raise.
    """

    value = getattr(user, "isVerified", None)
    if value is None:
        raise RuntimeError(
            "Your running Python environment's Prisma client doesn't match the current schema: "
            "User.isVerified is missing. This usually means you're running the server from a different "
            "Python (e.g. Anaconda `(base)`) than the one where Prisma was generated. "
            "Fix: from Cognitest-Backend run `uv sync`, then `uv run prisma generate`, then "
            "start with `uv run uvicorn src.main:app --reload --port 5000`."
        )
    return bool(value)

async def signup(data: SignupRequest) -> SignupInitialResponse:
    # If inviteToken is provided, route through the invitation signup workflow
    if data.inviteToken:
        inv = await prisma.invitation.find_unique(
            where={"token": data.inviteToken},
            include={"workspace": True}
        )
        if not inv:
            raise ValueError("Invitation not found")
        if inv.status != "PENDING":
            raise ValueError(f"Invitation has already been {inv.status.lower()}")
        
        now = datetime.utcnow()
        expires_at = inv.expiresAt.replace(tzinfo=None) if inv.expiresAt.tzinfo else inv.expiresAt
        if expires_at < now:
            raise ValueError("Invitation has expired")

        if data.email.lower() != inv.email.lower():
            raise ValueError(f"This invitation is for {inv.email}, not {data.email}")

        existing_user = await prisma.user.find_first(where={"email": data.email})
        if existing_user:
            if _get_is_verified(existing_user):
                raise ValueError("User with this email already exists")
            
            password_hash = hash_password(data.passcode)
            otp_code = generate_otp()
            otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            await prisma.user.update(
                where={"id": existing_user.id},
                data={
                    "name": data.name,
                    "passwordHash": password_hash,
                    "tenantId": inv.workspace.tenantId,
                    "contactNumber": data.contactNumber,
                    "otpCode": otp_code,
                    "otpExpiry": otp_expiry,
                    "otpAttempts": 0,
                    "otpLockedUntil": None
                }
            )
            try:
                send_otp_email(data.email, otp_code)
            except Exception as e:
                logger.error("Error sending OTP to %s: %s", data.email, e)

            return SignupInitialResponse(
                message="Verification code sent to your email.",
                email=data.email
            )

        password_hash = hash_password(data.passcode)
        otp_code = generate_otp()
        otp_expiry = datetime.utcnow() + timedelta(minutes=10)

        await ensure_global_permissions()

        await prisma.user.create(
            data={
                "tenantId": inv.workspace.tenantId,
                "email": data.email,
                "name": data.name,
                "passwordHash": password_hash,
                "systemRole": "USER",
                "company": inv.workspace.name,
                "contactNumber": data.contactNumber,
                "otpCode": otp_code,
                "otpExpiry": otp_expiry,
                "isVerified": False
            }
        )

        try:
            send_otp_email(data.email, otp_code)
        except Exception as e:
            logger.error("Error sending OTP to %s: %s", data.email, e)

        return SignupInitialResponse(
            message="Verification code sent to your email.",
            email=data.email
        )

    if not data.company:
        raise ValueError("Company name is required for registration")

    # 1. Check if user already exists
    existing_user = await prisma.user.find_first(where={"email": data.email})
    if existing_user:
        if _get_is_verified(existing_user):
            raise ValueError("User with this email already exists")
        else:
            # User exists but is unverified. We will recycle the account and resend OTP.
            otp_code = generate_otp()
            otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
            password_hash = hash_password(data.passcode)

            # Check if they are trying to use a completely different company name that is already taken
            tenant_name = data.company or data.name
            if tenant_name and existing_user.tenantId:
                existing_tenant = await prisma.tenant.find_first(where={"name": tenant_name})
                if existing_tenant and existing_tenant.id != existing_user.tenantId:
                    raise ValueError(f"Company name '{tenant_name}' is already taken")
                
                # Update their tenant name just in case they changed it
                if not existing_tenant or existing_tenant.id == existing_user.tenantId:
                    await prisma.tenant.update(
                        where={"id": existing_user.tenantId},
                        data={"name": tenant_name}
                    )

            # Update the user record with the new OTP and signup details
            await prisma.user.update(
                where={"id": existing_user.id},
                data={
                    "name": data.name,
                    "passwordHash": password_hash,
                    "company": data.company,
                    "contactNumber": data.contactNumber,
                    "otpCode": otp_code,
                    "otpExpiry": otp_expiry,
                    "otpAttempts": 0,
                    "otpLockedUntil": None
                }
            )

            # Resend OTP email
            try:
                send_otp_email(existing_user.email, otp_code)
            except Exception as e:
                logger.error("Error sending OTP to %s: %s", existing_user.email, e)

            logger.info("Signup recycled (resent OTP) for unverified user %s", data.email)
            return SignupInitialResponse(
                message="Verification code sent to your email.",
                email=data.email
            )

    # 2. Check if tenant name is unique
    if data.company or data.name:
        tenant_name = data.company or data.name
        existing_tenant = await prisma.tenant.find_first(where={"name": tenant_name})
        if existing_tenant:
            raise ValueError(f"Company name '{tenant_name}' is already taken")

    password_hash = hash_password(data.passcode)

    logger.info("Starting signup transaction for %s", data.email)
    
    # Ensure global permissions exist before starting tenant transaction
    await ensure_global_permissions()
    
    async with prisma.tx(timeout=30000) as tx:
        # 1. Create Tenant
        tenant = await tx.tenant.create(
            data={
                "name": data.company or data.name,
                "status": "ACTIVE"
            }
        )
        logger.info("Tenant created: %s", tenant.id)

        # 2. Attach FREE Plan
        free_plan = await tx.plan.find_first(where={"name": "FREE"})
        if not free_plan:
            # Seed FREE plan if it doesn't exist
            free_plan = await tx.plan.create(
                data={
                    "name": "FREE",
                    "description": "Free plan with 1 project limit",
                    "maxProjects": 1,
                    "maxTestRunsPerMonth": 100,
                    "maxUsers": 5,
                    "aiGenerationEnabled": False,
                    "regressionEnabled": False
                }
            )

        subscription = await tx.subscription.create(
            data={
                "tenantId": tenant.id,
                "planId": free_plan.id,
                "status": "ACTIVE",
                "startDate": datetime.now(timezone.utc),
                "expiryDate": datetime.now(timezone.utc) + timedelta(days=3650), # 10 years for free?
                "autoRenew": True
            }
        )

        # 3. Create User
        user = await tx.user.create(
            data={
                "tenantId": tenant.id,
                "email": data.email,
                "name": data.name,
                "passwordHash": password_hash,
                "systemRole": "TENANT_ADMIN",
                "company": data.company,
                "contactNumber": data.contactNumber
            }
        )

        # 4. Create Default Workspace
        workspace = await tx.workspace.create(
            data={
                "tenantId": tenant.id,
                "name": "Default Workspace",
                "createdBy": user.id
            }
        )

        # 5. Seed Default Roles
        roles_map = {}
        for role_data in DEFAULT_ROLES:
            role = await tx.role.create(
                data={
                    "tenantId": tenant.id,
                    "workspaceId": workspace.id,
                    "name": role_data["name"],
                    "description": role_data["description"]
                }
            )
            roles_map[role_data["name"]] = role.id
        logger.info("Default roles seeded")

        # 5b. Seed Role Permissions
        # We fetch permissions inside the transaction to ensure we have the IDs
        all_perms = await tx.permission.find_many()
        
        rp_data = []
        for p in all_perms:
            # Grant everything to ADMIN
            rp_data.append({
                "roleId": roles_map["ADMIN"],
                "permissionId": p.id
            })
            
            # Grant READ permissions to others
            if p.action == "READ":
                for r_name in ["TESTER", "QA", "AUDIT"]:
                    if r_name in roles_map:
                        rp_data.append({
                            "roleId": roles_map[r_name],
                            "permissionId": p.id
                        })
        
        if rp_data:
            logger.info("Batch creating %d role permissions", len(rp_data))
            # prisma-client-py supports create_many
            await tx.rolepermission.create_many(data=rp_data)

        # 6. Assign ADMIN role to the creator
        await tx.workspacemember.create(
            data={
                "workspaceId": workspace.id,
                "userId": user.id,
                "roleId": roles_map["ADMIN"]
            }
        )

        # No default project created — users must create projects with swagger specs
    
    otp_code = generate_otp()
    otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

    # 10. Make user unverified and attach OTP
    await prisma.user.update(
        where={"id": user.id},
        data={
            "otpCode": otp_code, 
            "otpExpiry": otp_expiry, 
            "isVerified": False,
            "otpAttempts": 0,
            "otpLockedUntil": None
        }
    )

    # Send the OTP email asynchronously but we'll await it or fire and forget
    # For a small user base, synchronous call is fine. But let's just call it.
    try:
        send_otp_email(user.email, otp_code)
    except Exception as e:
        logger.error("Error sending OTP to %s: %s", user.email, e)

    logger.info("Signup initial phase completed successfully for %s", data.email)

    return SignupInitialResponse(
        message="Verification code sent to your email.",
        email=data.email
    )

async def _accept_invitation_internal(user_id: str, invite_token: str):
    inv = await prisma.invitation.find_unique(where={"token": invite_token}, include={"workspace": True})
    if not inv or inv.status != "PENDING":
        return
    
    now = datetime.utcnow()
    expires_at = inv.expiresAt.replace(tzinfo=None) if inv.expiresAt.tzinfo else inv.expiresAt
    if expires_at < now:
        return

    # Update invitation status
    await prisma.invitation.update(
        where={"id": inv.id},
        data={"status": "ACCEPTED"}
    )
    # Create WorkspaceMember
    if inv.workspaceId:
        existing_wm = await prisma.workspacemember.find_unique(
            where={
                "workspaceId_userId": {
                    "workspaceId": inv.workspaceId,
                    "userId": user_id
                }
            }
        )
        if not existing_wm:
            await prisma.workspacemember.create(
                data={
                    "workspaceId": inv.workspaceId,
                    "userId": user_id,
                    "roleId": inv.roleId
                }
            )
    # Create ProjectMember
    if inv.projectId:
        existing_pm = await prisma.projectmember.find_unique(
            where={
                "projectId_userId": {
                    "projectId": inv.projectId,
                    "userId": user_id
                }
            }
        )
        if not existing_pm:
            await prisma.projectmember.create(
                data={
                    "projectId": inv.projectId,
                    "userId": user_id,
                    "roleId": inv.roleId
                }
            )

async def verify_otp(email: str, otp: str, invite_token: Optional[str] = None) -> SignupResponse:
    user = await prisma.user.find_first(
        where={"email": email},
        include={"tenant": True}
    )
    if not user:
        raise ValueError("User not found")
    
    if _get_is_verified(user):
        raise ValueError("User is already verified")

    now_utc = datetime.now(timezone.utc)

    # Check for active lockout
    if user.otpLockedUntil:
        locked_until = user.otpLockedUntil.replace(tzinfo=timezone.utc) if user.otpLockedUntil.tzinfo is None else user.otpLockedUntil
        if locked_until > now_utc:
            remaining_seconds = int((locked_until - now_utc).total_seconds())
            remaining_minutes = max(1, (remaining_seconds + 59) // 60)
            raise ValueError(f"Too many failed attempts. Try again in {remaining_minutes} minutes.")

    # Check if verification code matches
    if user.otpCode != otp:
        new_attempts = (user.otpAttempts or 0) + 1
        if new_attempts >= 5:
            lock_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            await prisma.user.update(
                where={"id": user.id},
                data={"otpAttempts": 0, "otpLockedUntil": lock_until}
            )
            raise ValueError("Too many failed attempts. Account temporarily locked for 15 minutes.")
        else:
            await prisma.user.update(
                where={"id": user.id},
                data={"otpAttempts": new_attempts}
            )
        raise ValueError("Invalid verification code")

    # Prisma may return offset-aware or offset-naive depending on DB connector
    # We strip tzinfo for safe comparison, or add it to both.
    expiry = user.otpExpiry.replace(tzinfo=timezone.utc) if user.otpExpiry.tzinfo is None else user.otpExpiry
    
    if not user.otpExpiry or expiry < now_utc:
        raise ValueError("Verification code expired")

    # Mark as verified and reset attempt tracking/lockout
    user = await prisma.user.update(
        where={"id": user.id},
        data={
            "isVerified": True, 
            "otpCode": None, 
            "otpExpiry": None,
            "otpAttempts": 0,
            "otpLockedUntil": None
        },
        include={"tenant": True}
    )

    if invite_token:
        await _accept_invitation_internal(user.id, invite_token)

    # Load workspace
    workspace = await prisma.workspace.find_first(where={"tenantId": user.tenantId})
    subscription = await prisma.subscription.find_first(where={"tenantId": user.tenantId})

    from src.modules.rbac.service import get_user_workspace_permissions
    workspace_permissions = await get_user_workspace_permissions(user.id)
    token = create_access_token(data={
        "userId": user.id,
        "tenantId": user.tenantId,
        "systemRole": user.systemRole,
        "workspacePermissions": workspace_permissions
    })

    return SignupResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            tenantId=user.tenantId,
            email=user.email,
            name=user.name,
            systemRole=user.systemRole,
            company=user.company,
            contactNumber=user.contactNumber
        ),
        tenant=TenantResponse(
            id=user.tenant.id,
            name=user.tenant.name,
            status=user.tenant.status
        ),
        workspace=WorkspaceResponse(
            id=workspace.id,
            tenantId=workspace.tenantId,
            name=workspace.name,
            createdBy=workspace.createdBy
        ) if workspace else None,
        project=None,  # No default project — users must create projects with swagger specs
        subscription=SubscriptionResponse(
            id=subscription.id,
            planId=subscription.planId,
            status=subscription.status,
            expiryDate=subscription.expiryDate.isoformat()
        ) if subscription else None
    )



async def login(email: str, passcode: str, invite_token: Optional[str] = None) -> LoginResponse:
    # ── Super Admin login ──────────────────────────────────────────────────────
    # Email is compared case-insensitively. Password is verified against the
    # bcrypt hash stored in SUPER_ADMIN_PASSWORD_HASH — never plaintext equality.
    if email.lower() == settings.super_admin_email.lower():
        if not verify_password(passcode, settings.super_admin_password_hash):
            # Deliberately use the same generic error as normal login to avoid
            # leaking that the super-admin email was recognised.
            raise ValueError("Invalid credentials")

        logger.info("Super Admin login for %s", email)

        # Ensure a persistent DB record exists for the super admin so that the
        # JWT userId is stable across restarts.
        user = await prisma.user.find_first(where={"email": email})
        if not user:
            user = await prisma.user.create(
                data={
                    "email": email,
                    "name": "System Super Admin",
                    # Store the hash (not plaintext) — consistent with normal users.
                    "passwordHash": settings.super_admin_password_hash,
                    "systemRole": "SUPER_ADMIN",
                    "isVerified": True,
                }
            )

        token = create_access_token(data={
            "userId": user.id,
            "tenantId": user.tenantId or "super-admin-tenant",
            "systemRole": "SUPER_ADMIN",
            "workspacePermissions": {}  # Super Admin bypasses workspace checks
        })

        return LoginResponse(
            token=token,
            user=UserResponse(
                id=user.id,
                tenantId=user.tenantId,
                email=user.email,
                name=user.name,
                systemRole="SUPER_ADMIN",
                company=user.company,
                contactNumber=user.contactNumber
            ),
            tenant=TenantResponse(
                id="super-admin-tenant",
                name="Super Admin Tenant",
                status="ACTIVE"
            ),
            workspace=None,
            subscription=None
        )

    user = await prisma.user.find_first(
        where={"email": email},
        include={"tenant": True}
    )

    if not user or not verify_password(passcode, user.passwordHash):
        raise ValueError("Invalid credentials")
    
    if not _get_is_verified(user):
        raise ValueError("Please verify your email before logging in. Contact support if you need a new code.")

    if invite_token:
        inv = await prisma.invitation.find_unique(
            where={"token": invite_token},
            include={"workspace": True}
        )
        if inv and inv.workspace:
            # Update user's tenantId to the invited workspace's tenantId
            await prisma.user.update(
                where={"id": user.id},
                data={"tenantId": inv.workspace.tenantId}
            )
            # Reload user with updated tenant info
            user = await prisma.user.find_unique(
                where={"id": user.id},
                include={"tenant": True}
            )
        await _accept_invitation_internal(user.id, invite_token)

    # Fetch the user's workspace (first workspace in their tenant)
    workspace = await prisma.workspace.find_first(
        where={"tenantId": user.tenantId}
    )

    # Fetch subscription
    subscription = await prisma.subscription.find_first(
        where={"tenantId": user.tenantId}
    )

    # Load workspace permissions
    from src.modules.rbac.service import get_user_workspace_permissions
    workspace_permissions = await get_user_workspace_permissions(user.id)
    
    token = create_access_token(data={
        "userId": user.id,
        "tenantId": user.tenantId,
        "systemRole": user.systemRole,
        "workspacePermissions": workspace_permissions
    })

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            tenantId=user.tenantId,
            email=user.email,
            name=user.name,
            systemRole=user.systemRole,
            company=user.company,
            contactNumber=user.contactNumber
        ),
        tenant=TenantResponse(
            id=user.tenant.id,
            name=user.tenant.name,
            status=user.tenant.status
        ),
        workspace=WorkspaceResponse(
            id=workspace.id,
            tenantId=workspace.tenantId,
            name=workspace.name,
            createdBy=workspace.createdBy
        ) if workspace else None,
        subscription=SubscriptionResponse(
            id=subscription.id,
            planId=subscription.planId,
            status=subscription.status,
            expiryDate=subscription.expiryDate.isoformat()
        ) if subscription else None
    )
