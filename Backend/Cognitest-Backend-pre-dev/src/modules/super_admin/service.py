"""Service layer for Super Admin business logic.

Extracted from the monolithic `router.py` to separate concerns.
All DB queries and aggregation logic live here; the router is a thin controller.
"""
import logging
from typing import Any

from src.config import prisma
from src.utils.formatting import format_duration_ms
from .schema import (
    CreateTenantRequest,
    UpdateTenantRequest,
    UpdateStatusRequest,
    PLAN_MAPPING,
)

logger = logging.getLogger(__name__)


# ─── Dashboard Stats ─────────────────────────────────────────────────────────

async def get_dashboard_stats() -> dict[str, Any]:
    """Global statistics for the Super Admin dashboard."""

    total_tenants = await prisma.tenant.count()
    active_tenants = await prisma.tenant.count(where={"status": "ACTIVE"})
    total_users = await prisma.user.count(
        where={"systemRole": {"not": "SUPER_ADMIN"}}
    )
    total_projects = await prisma.project.count()
    total_test_runs = await prisma.testrun.count()

    # Test results aggregates
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    all_runs = await prisma.testrun.find_many(where={"status": "COMPLETED"})
    for run in all_runs:
        total_passed += run.passed or 0
        total_failed += run.failed or 0
        total_skipped += run.skipped or 0
    total_tests = total_passed + total_failed + total_skipped

    # Subscriptions — count by plan
    subscribed_tenants = 0
    free_tenants_count = 0
    enterprise_tenants = 0

    all_subs = await prisma.subscription.find_many()
    for sub in all_subs:
        plan_name = "FREE"
        if plan_name == "FREE":
            free_tenants_count += 1
        else:
            subscribed_tenants += 1
            if plan_name == "ENTERPRISE":
                enterprise_tenants += 1

    # Users by role
    admin_count = await prisma.user.count(where={"systemRole": "TENANT_ADMIN"})
    member_count = await prisma.user.count(
        where={"systemRole": {"not_in": ["SUPER_ADMIN", "TENANT_ADMIN"]}}
    )

    return {
        "totalTenants": total_tenants,
        "activeTenants": active_tenants,
        "totalUsers": total_users,
        "subscribedTenants": subscribed_tenants,
        "freeTenants": free_tenants_count,
        "enterpriseTenants": enterprise_tenants,
        "totalProjects": total_projects,
        "totalTestRuns": total_test_runs,
        "totalTests": total_tests,
        "totalPassed": total_passed,
        "totalFailed": total_failed,
        "totalSkipped": total_skipped,
        "adminCount": admin_count,
        "memberCount": member_count,
    }


# ─── Tenants List ────────────────────────────────────────────────────────────

async def get_all_tenants() -> list[dict[str, Any]]:
    """Fetch all tenants with their details, team, projects, and stats."""

    tenants = await prisma.tenant.find_many(
        include={
            "users": True,
            "projects": {
                "include": {
                    "test_runs": {
                        "order_by": {"createdAt": "desc"},
                        "take": 5,
                    }
                }
            },
            "subscriptions": True,
        }
    )

    formatted = []
    for t in tenants:
        plan_name = "FREE"

        # Aggregate test stats across all projects
        total_test_runs = 0
        total_passed = 0
        total_failed = 0
        for p in t.projects:
            for run in (p.test_runs or []):
                total_test_runs += 1
                total_passed += run.passed or 0
                total_failed += run.failed or 0

        # Primary admin user
        admin_user = next(
            (u for u in t.users if u.systemRole == "TENANT_ADMIN"), None
        )
        primary_email = (
            admin_user.email
            if admin_user
            else (t.users[0].email if t.users else "N/A")
        )
        primary_phone = (
            admin_user.contactNumber
            if admin_user
            else (t.users[0].contactNumber if t.users else None)
        ) or "N/A"

        formatted.append({
            "id": t.id,
            "name": t.name,
            "avatar": None,
            "email": primary_email,
            "phone": primary_phone,
            "role": "Admin",
            "location": "Remote",
            "plan": plan_name,
            "status": t.status,
            "company": t.name,
            "createdAt": t.createdAt.isoformat() if t.createdAt else None,
            "stats": {
                "totalProjects": len(t.projects),
                "totalTestRuns": total_test_runs,
                "totalPassed": total_passed,
                "totalFailed": total_failed,
                "activeEndpoints": 0,
                "riskScore": "Low",
                "tokenQuota": "Unlimited" if plan_name == "ENTERPRISE" else "Limited",
                "activeIncidents": 0,
                "health": "Optimal",
            },
            "team": [
                {
                    "id": u.id,
                    "name": u.name or u.email,
                    "email": u.email,
                    "role": u.systemRole,
                    "avatar": None,
                    "status": "Active",
                }
                for u in t.users
            ],
            "projects": [
                {
                    "id": p.id,
                    "title": p.name,
                    "status": "Active",
                    "testRuns": len(p.test_runs) if p.test_runs else 0,
                    "tasks": f"{len(p.test_runs) if p.test_runs else 0} runs",
                    "prog": 0,
                    "color": "bg-slate-900",
                }
                for p in t.projects
            ],
        })

    return formatted


# ─── Test System Stats ───────────────────────────────────────────────────────

async def get_test_system_stats() -> dict[str, Any]:
    """Aggregate test statistics across all tenants."""

    all_runs = await prisma.testrun.find_many(
        where={"status": "COMPLETED"},
        include={"project": {"include": {"tenant": True}}},
        order_by={"createdAt": "desc"},
    )

    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    category_stats: dict[str, dict[str, int]] = {}

    for run in all_runs:
        total_tests += run.total_tests or 0
        total_passed += run.passed or 0
        total_failed += run.failed or 0
        total_skipped += run.skipped or 0

        for cat in (run.categories or []):
            cat_name = cat if isinstance(cat, str) else str(cat)
            if cat_name not in category_stats:
                category_stats[cat_name] = {"total": 0, "passed": 0, "failed": 0}
            category_stats[cat_name]["total"] += run.total_tests or 0
            category_stats[cat_name]["passed"] += run.passed or 0
            category_stats[cat_name]["failed"] += run.failed or 0

    # Recent executions (last 10 runs)
    recent_executions = []
    for run in all_runs[:10]:
        tenant_name = (
            run.project.tenant.name
            if run.project and run.project.tenant
            else "Unknown"
        )
        categories_list = [str(c) for c in (run.categories or [])]
        category = categories_list[0] if categories_list else "Functional"

        recent_executions.append({
            "tenant": tenant_name,
            "testType": "Automated",
            "category": category,
            "priority": "High" if run.total_tests and run.total_tests > 50 else "Medium",
            "status": "Completed" if run.status == "COMPLETED" else str(run.status),
            "coverage": f"{round((run.passed / run.total_tests) * 100) if run.total_tests else 0}%",
            "duration": format_duration_ms(run.durationMs),
            "timestamp": (
                run.completedAt.isoformat()
                if run.completedAt
                else run.createdAt.isoformat()
            ),
        })

    return {
        "totalTests": total_tests,
        "totalPassed": total_passed,
        "totalFailed": total_failed,
        "totalSkipped": total_skipped,
        "categoryStats": category_stats,
        "recentExecutions": recent_executions,
    }


# ─── Billing Stats ───────────────────────────────────────────────────────────

async def get_billing_stats() -> dict[str, Any]:
    """Aggregate billing/subscription statistics."""

    all_subs = await prisma.subscription.find_many(include={"tenant": True})

    plan_counts: dict[str, int] = {}
    plan_tenants: dict[str, list[dict[str, Any]]] = {}

    for sub in all_subs:
        plan_name = "FREE"
        plan_counts[plan_name] = plan_counts.get(plan_name, 0) + 1
        if plan_name not in plan_tenants:
            plan_tenants[plan_name] = []
        plan_tenants[plan_name].append({
            "tenantId": sub.tenantId,
            "tenantName": sub.tenant.name if sub.tenant else "Unknown",
            "status": sub.status,
            "startDate": sub.startDate.isoformat() if sub.startDate else None,
            "expiryDate": sub.expiryDate.isoformat() if sub.expiryDate else None,
        })

    return {
        "planCounts": plan_counts,
        "planTenants": plan_tenants,
        "totalSubscriptions": len(all_subs),
    }


# ─── Tenant CRUD ─────────────────────────────────────────────────────────────

async def create_tenant(data: CreateTenantRequest) -> dict[str, str]:
    """Create a new tenant via the existing signup flow."""
    from src.modules.auth.service import signup
    from src.modules.auth.schema import SignupRequest

    plan_name = PLAN_MAPPING.get(data.plan.upper(), "FREE")

    signup_data = SignupRequest(
        email=data.email,
        name=data.name or data.email.split("@")[0],
        passcode=data.password,
        company=data.name or "Client",
        contactNumber=None,
    )
    result = await signup(signup_data)

    if plan_name != "FREE":
        plan = await prisma.plan.find_first(where={"name": plan_name})
        if plan:
            await prisma.subscription.update_many(
                where={"tenantId": result.tenant.id},
                data={"planId": plan.id},
            )

    return {"status": "success", "tenantId": result.tenant.id}


async def update_tenant(tenant_id: str, data: UpdateTenantRequest) -> dict[str, str]:
    """Update a tenant's details, admin credentials, or plan."""

    # Update tenant name
    if data.name:
        await prisma.tenant.update(where={"id": tenant_id}, data={"name": data.name})

    # Update primary admin email/password
    admin_update: dict[str, Any] = {}
    if data.email:
        admin_update["email"] = data.email
    if data.password:
        from src.modules.auth.service import hash_password
        admin_update["passwordHash"] = hash_password(data.password)

    if admin_update:
        admin_user = await prisma.user.find_first(
            where={"tenantId": tenant_id, "systemRole": "TENANT_ADMIN"}
        )
        if admin_user:
            await prisma.user.update(where={"id": admin_user.id}, data=admin_update)

    # Update subscription plan
    if data.plan:
        plan_name = PLAN_MAPPING.get(data.plan.upper(), "FREE")
        plan = await prisma.plan.find_first(where={"name": plan_name})
        if plan:
            await prisma.subscription.update_many(
                where={"tenantId": tenant_id},
                data={"planId": plan.id},
            )

    return {"status": "success"}


async def update_tenant_status(tenant_id: str, status: str) -> dict[str, str]:
    """Toggle a tenant's active/inactive status."""
    await prisma.tenant.update(where={"id": tenant_id}, data={"status": status})
    return {"status": "success"}


async def delete_tenant(tenant_id: str) -> dict[str, str]:
    """Cascade-delete a tenant and all related records."""

    async with prisma.tx() as tx:
        # 1. Subscriptions
        await tx.subscription.delete_many(where={"tenantId": tenant_id})

        # 2. Roles and RolePermissions
        roles = await tx.role.find_many(where={"tenantId": tenant_id})
        role_ids = [r.id for r in roles]
        if role_ids:
            await tx.rolepermission.delete_many(where={"roleId": {"in": role_ids}})
            await tx.role.delete_many(where={"tenantId": tenant_id})

        # 3. Workspaces and members
        workspaces = await tx.workspace.find_many(where={"tenantId": tenant_id})
        ws_ids = [w.id for w in workspaces]
        if ws_ids:
            await tx.workspacemember.delete_many(where={"workspaceId": {"in": ws_ids}})
            await tx.workspace.delete_many(where={"tenantId": tenant_id})

        # 4. Projects and members
        projects = await tx.project.find_many(where={"tenantId": tenant_id})
        p_ids = [p.id for p in projects]
        if p_ids:
            await tx.projectmember.delete_many(where={"projectId": {"in": p_ids}})
            await tx.project.delete_many(where={"tenantId": tenant_id})

        # 5. Users
        await tx.user.delete_many(where={"tenantId": tenant_id})

        # 6. Tenant
        await tx.tenant.delete(where={"id": tenant_id})

    return {"status": "success"}


# ─── User Status ──────────────────────────────────────────────────────────────

async def update_user_status(user_id: str, status: str) -> dict[str, str]:
    """Toggle a user's active/disabled status via systemRole."""

    user = await prisma.user.find_unique(where={"id": user_id})
    if not user:
        return {"error": "User not found"}

    if status in ("INACTIVE", "DISABLED"):
        new_role = "DISABLED"
    else:
        # Re-activate: restore to USER to avoid privilege escalation
        new_role = "USER" if user.systemRole == "DISABLED" else user.systemRole

    await prisma.user.update(where={"id": user_id}, data={"systemRole": new_role})
    return {"status": "success"}


# ─── Project Deletion ────────────────────────────────────────────────────────

async def delete_project(project_id: str) -> dict[str, str]:
    """Cascade-delete a project and all related records."""

    async with prisma.tx() as tx:
        await tx.projectmember.delete_many(where={"projectId": project_id})

        endpoints = await tx.endpoint.find_many(where={"projectId": project_id})
        e_ids = [e.id for e in endpoints]
        if e_ids:
            await tx.testcase.delete_many(where={"endpointId": {"in": e_ids}})
            await tx.endpoint.delete_many(where={"projectId": project_id})

        await tx.apispec.delete_many(where={"projectId": project_id})
        await tx.testrun.delete_many(where={"projectId": project_id})
        await tx.project.delete(where={"id": project_id})

    return {"status": "success"}
