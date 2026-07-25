import json
import logging
from src.config import prisma

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"TENANT_ADMIN", "SUPER_ADMIN"}

class DashboardService:
    @staticmethod
    async def get_scoped_projects(user: dict):
        """Return the list of Project objects that the caller is allowed to see."""
        tenant_id = user.get("tenantId")
        user_id = user.get("userId")
        system_role = user.get("systemRole", "USER")

        if system_role in ADMIN_ROLES:
            project_filter = {"tenantId": tenant_id} if tenant_id else {}
            projects = await prisma.project.find_many(where=project_filter)
        else:
            memberships = await prisma.projectmember.find_many(
                where={"userId": user_id}, include={"project": True}
            )
            projects = [m.project for m in memberships if m.project is not None]
        return projects

    @staticmethod
    async def get_dashboard_stats(user: dict):
        """Aggregated dashboard statistics logic."""
        projects = await DashboardService.get_scoped_projects(user)
        project_ids = [p.id for p in projects]
        total_projects = len(projects)

        if not project_ids:
            return {
                "totalApisTested": 0,
                "totalProjects": 0,
                "totalTestRuns": 0,
                "passRate": 0,
                "totalTestsRun": 0,
                "totalPassed": 0,
                "totalFailed": 0,
                "testDistribution": {
                    "FUNCTIONAL": {"passed": 0, "failed": 0, "totalRuns": 0},
                    "NEGATIVE": {"passed": 0, "failed": 0, "totalRuns": 0},
                    "SECURITY": {"passed": 0, "failed": 0, "totalRuns": 0},
                    "CONTRACT": {"passed": 0, "failed": 0, "totalRuns": 0},
                    "FUZZ": {"passed": 0, "failed": 0, "totalRuns": 0},
                },
                "recentRuns": [],
                "activeProjects": [],
            }

        # Count distinct endpoints with test results (APIs tested)
        endpoints = await prisma.endpoint.find_many(where={"projectId": {"in": project_ids}})
        total_endpoints = len(endpoints)
        project_endpoints_map: dict[str, int] = {}
        for ep in endpoints:
            project_endpoints_map[ep.projectId] = project_endpoints_map.get(ep.projectId, 0) + 1

        # Aggregate test runs
        test_runs = await prisma.testrun.find_many(
            where={"projectId": {"in": project_ids}}, order={"createdAt": "desc"}
        )
        run_ids = [r.id for r in test_runs]

        # Initialize per‑category stats with passed/failed/total counters
        test_distribution = {
            "FUNCTIONAL": {"passed": 0, "failed": 0, "total": 0},
            "NEGATIVE": {"passed": 0, "failed": 0, "total": 0},
            "SECURITY": {"passed": 0, "failed": 0, "total": 0},
            "CONTRACT": {"passed": 0, "failed": 0, "total": 0},
            "FUZZ": {"passed": 0, "failed": 0, "total": 0},
        }

        if run_ids:
            test_results = await prisma.testresult.find_many(where={"runId": {"in": run_ids}})
            for result in test_results:
                cat = (result.category or "FUNCTIONAL").upper()
                if cat not in test_distribution:
                    continue
                test_distribution[cat]["total"] += 1
                status_str = str(getattr(result, "status", "")).upper()
                if status_str == "PASSED":
                    test_distribution[cat]["passed"] += 1
                else:
                    test_distribution[cat]["failed"] += 1

        total_test_runs = len(test_runs)
        total_passed = sum(r.passed for r in test_runs)
        total_failed = sum(r.failed for r in test_runs)
        total_tests = total_passed + total_failed
        pass_rate = round((total_passed / total_tests) * 100, 1) if total_tests > 0 else 0

        # Fetch API Specs to determine Swagger info
        api_specs = await prisma.apispec.find_many(
            where={"projectId": {"in": project_ids}}, order={"createdAt": "desc"}
        )
        project_spec_map = {}
        for spec in api_specs:
            if spec.projectId not in project_spec_map:
                project_spec_map[spec.projectId] = spec

        recent_runs_raw = test_runs[:5]
        project_name_map = {p.id: p.name for p in projects}
        recent_runs = []
        for run in recent_runs_raw:
            duration_str = DashboardService._format_duration(run.durationMs)
            recent_runs.append({
                "id": run.id,
                "projectName": project_name_map.get(run.projectId, "Unknown"),
                "projectId": run.projectId,
                "status": run.status,
                "totalTests": run.total_tests,
                "passed": run.passed,
                "failed": run.failed,
                "duration": duration_str,
                "date": run.createdAt.isoformat() if run.createdAt else None,
            })

        # Active projects with latest stats
        latest_run_map: dict[str, object] = {}
        project_total_runs_map: dict[str, int] = {}
        project_total_passed_map: dict[str, int] = {}
        project_total_failed_map: dict[str, int] = {}
        for run in test_runs:
            if run.projectId not in project_total_runs_map:
                project_total_runs_map[run.projectId] = 0
                project_total_passed_map[run.projectId] = 0
                project_total_failed_map[run.projectId] = 0
            project_total_runs_map[run.projectId] += 1
            project_total_passed_map[run.projectId] += run.passed
            project_total_failed_map[run.projectId] += run.failed
            if run.projectId not in latest_run_map:
                latest_run_map[run.projectId] = run

        test_suites = await prisma.testsuite.find_many(where={"projectId": {"in": project_ids}})
        project_suites_map: dict[str, int] = {}
        for suite in test_suites:
            project_suites_map[suite.projectId] = project_suites_map.get(suite.projectId, 0) + 1

        active_projects = []
        for p in projects:
            latest_run = latest_run_map.get(p.id)
            proj_total_runs = project_total_runs_map.get(p.id, 0)
            proj_total_apis = project_endpoints_map.get(p.id, 0)
            proj_suites_count = project_suites_map.get(p.id, 0)
            agg_passed = project_total_passed_map.get(p.id, 0)
            agg_failed = project_total_failed_map.get(p.id, 0)
            agg_total_tests = agg_passed + agg_failed
            proj_pass_rate = round((agg_passed / agg_total_tests) * 100) if agg_total_tests > 0 else None
            status = "PENDING"
            if proj_total_runs > 0 and latest_run and latest_run.status == "COMPLETED":
                status = "COMPLETED"
            elif proj_suites_count > 0 and proj_total_runs == 0:
                status = "RUNNING"
            elif proj_total_runs > 0:
                status = "RUNNING"
            swagger_name, api_version = DashboardService._parse_swagger_info(p, project_spec_map.get(p.id))
            active_projects.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "swaggerName": swagger_name,
                "apiVersion": api_version,
                "lastRunDate": latest_run.createdAt.isoformat() if latest_run else None,
                "lastRunStatus": status,
                "passed": agg_passed,
                "failed": agg_failed,
                "passRate": proj_pass_rate,
                "totalRuns": proj_total_runs,
                "totalApisTested": proj_total_apis,
            })

        # Convert internal dict to the format required by the frontend
        formatted_distribution = {
            cat: {
                "passed": stats["passed"],
                "failed": stats["failed"],
                "totalRuns": stats["total"],
            }
            for cat, stats in test_distribution.items()
        }

        return {
            "totalApisTested": total_endpoints,
            "totalProjects": total_projects,
            "totalTestRuns": total_test_runs,
            "passRate": pass_rate,
            "totalTestsRun": total_tests,
            "totalPassed": total_passed,
            "totalFailed": total_failed,
            "testDistribution": formatted_distribution,
            "recentRuns": recent_runs,
            "activeProjects": active_projects,
        }

    @staticmethod
    def _format_duration(duration_ms: int | None) -> str:
        if not duration_ms:
            return "—"
        secs = duration_ms // 1000
        mins = secs // 60
        secs = secs % 60
        return f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

    @staticmethod
    def _parse_swagger_info(project, spec):
        swagger_name = project.name
        api_version = None
        if spec and spec.parsed_spec:
            try:
                spec_data = spec.parsed_spec
                if isinstance(spec_data, str):
                    spec_data = json.loads(spec_data)
                if isinstance(spec_data, dict):
                    info = spec_data.get("info", {})
                    if info:
                        swagger_name = info.get("title", swagger_name)
                        api_version = info.get("version")
            except Exception as e:
                logger.warning(f"Error parsing swagger spec for project {project.id}: {e}")
        return swagger_name, api_version

    @staticmethod
    async def get_reports(user: dict):
        projects = await DashboardService.get_scoped_projects(user)
        project_ids = [p.id for p in projects]
        project_name_map = {p.id: p.name for p in projects}
        if not project_ids:
            return []
        test_runs = await prisma.testrun.find_many(
            where={"projectId": {"in": project_ids}, "status": {"in": ["COMPLETED", "FAILED"]}},
            order={"createdAt": "desc"},
            take=20,
        )
        reports = []
        for run in test_runs:
            vulns = await prisma.securityfinding.count(where={"runId": run.id})
            results = await prisma.testresult.find_many(where={"runId": run.id}, include={"test": True})
            passed_tests = []
            failed_tests = []
            category_summary: dict[str, int] = {}
            for res in results:
                cat = str(res.category) if res.category else (str(res.test.category) if res.test and res.test.category else None)
                sub = str(res.subCategory) if res.subCategory else None
                if cat:
                    category_summary[cat] = category_summary.get(cat, 0) + 1
                test_summary = {
                    "name": res.test.name if res.test else f"Test {res.testCaseId[:8]}",
                    "method": res.test.method if res.test else "GET",
                    "endpoint": res.test.endpoint_path if res.test else "/",
                    "expected": res.expected_status,
                    "actual": res.actual_status,
                    "category": cat,
                    "subCategory": sub,
                }
                if res.status == "PASSED":
                    passed_tests.append(test_summary)
                elif res.status == "FAILED":
                    test_summary["message"] = res.error_message or f"Expected {res.expected_status}, got {res.actual_status}"
                    failed_tests.append(test_summary)
            total = run.passed + run.failed
            coverage = round((run.passed / total) * 100) if total > 0 else 0
            duration_str = DashboardService._format_duration(run.durationMs)
            reports.append({
                "id": run.id,
                "project": project_name_map.get(run.projectId, "Unknown"),
                "projectId": run.projectId,
                "date": run.createdAt.strftime("%Y-%m-%d") if run.createdAt else "—",
                "duration": duration_str,
                "passed": run.passed,
                "failed": run.failed,
                "coverage": coverage,
                "vulns": vulns,
                "categorySummary": category_summary,
                "passedTests": passed_tests,
                "failedTests": failed_tests,
            })
        return reports

    @staticmethod
    async def get_report_detail(run_id: str, user: dict):
        run = await prisma.testrun.find_unique(where={"id": run_id}, include={"project": True})
        if not run:
            return None
        system_role = user.get("systemRole", "USER")
        if system_role not in ADMIN_ROLES:
            user_id = user.get("userId")
            if not user_id:
                raise PermissionError("Access denied")
            membership = await prisma.projectmember.find_unique(where={"projectId_userId": {"projectId": run.projectId, "userId": user_id}})
            if not membership:
                raise PermissionError("Access denied")
        results = await prisma.testresult.find_many(where={"runId": run_id}, include={"test": True}, order={"executedAt": "desc"})
        vulns = await prisma.securityfinding.count(where={"runId": run_id})
        passed_tests = []
        failed_tests = []
        category_summary: dict[str, int] = {}
        for res in results:
            cat = res.category.value if res.category else (res.test.category.value if res.test and res.test.category else None)
            sub = res.subCategory.value if res.subCategory else None
            if cat:
                category_summary[cat] = category_summary.get(cat, 0) + 1
            test_summary = {
                "name": res.test.name if res.test else f"Test {res.testCaseId[:8]}",
                "method": res.test.method if res.test else "GET",
                "endpoint": res.test.endpoint_path if res.test else "/",
                "expected": res.expected_status,
                "actual": res.actual_status,
                "responseTimeMs": res.response_time_ms,
                "category": cat,
                "subCategory": sub,
            }
            if res.status == "PASSED":
                passed_tests.append(test_summary)
            elif res.status == "FAILED":
                test_summary["message"] = res.error_message or f"Expected {res.expected_status}, got {res.actual_status}"
                failed_tests.append(test_summary)
        total = run.passed + run.failed
        coverage = round((run.passed / total) * 100) if total > 0 else 0
        duration_str = DashboardService._format_duration(run.durationMs)
        return {
            "id": run.id,
            "project": run.project.name if run.project else "Unknown",
            "projectId": run.projectId,
            "date": run.createdAt.strftime("%Y-%m-%d") if run.createdAt else "—",
            "duration": duration_str,
            "passed": run.passed,
            "failed": run.failed,
            "coverage": coverage,
            "vulns": vulns,
            "categorySummary": category_summary,
            "passedTests": passed_tests,
            "failedTests": failed_tests,
        }

import logging
import json

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"TENANT_ADMIN", "SUPER_ADMIN"}

class DashboardService:
    @staticmethod
    async def get_scoped_projects(user: dict):
        """
        Return the list of Project objects that the caller is allowed to see.
        """
        tenant_id = user.get("tenantId")
        user_id = user.get("userId")
        system_role = user.get("systemRole", "USER")

        if system_role in ADMIN_ROLES:
            # Admins: all projects in the tenant
            project_filter = {"tenantId": tenant_id} if tenant_id else {}
            projects = await prisma.project.find_many(where=project_filter)
        else:
            # Members: only projects they are assigned to
            memberships = await prisma.projectmember.find_many(
                where={"userId": user_id},
                include={"project": True},
            )
            projects = [m.project for m in memberships if m.project is not None]

        return projects

    @staticmethod
    async def get_dashboard_stats(user: dict):
        """
        Aggregated dashboard statistics logic.
        """
        projects = await DashboardService.get_scoped_projects(user)
        project_ids = [p.id for p in projects]
        total_projects = len(projects)

        if not project_ids:
            return {
                "totalApisTested": 0,
                "totalProjects": 0,
                "totalTestRuns": 0,
                "passRate": 0,
                "totalTestsRun": 0,
                "totalPassed": 0,
                "totalFailed": 0,
                "testDistribution": {
                    "FUNCTIONAL": 0,
                    "NEGATIVE": 0,
                    "SECURITY": 0,
                    "CONTRACT": 0,
                    "FUZZ": 0,
                },
                "recentRuns": [],
                "activeProjects": [],
            }

        # Count distinct endpoints with test results (APIs tested)
        endpoints = await prisma.endpoint.find_many(
            where={"projectId": {"in": project_ids}}
        )
        total_endpoints = len(endpoints)
        project_endpoints_map: dict[str, int] = {}
        for ep in endpoints:
            project_endpoints_map[ep.projectId] = project_endpoints_map.get(ep.projectId, 0) + 1

        # Aggregate test runs
        test_runs = await prisma.testrun.find_many(
            where={"projectId": {"in": project_ids}},
            order={"createdAt": "desc"},
        )


        # --------------------------------------------------------------------
        # New test‑distribution calculation – source of truth is TestCase categories
        # --------------------------------------------------------------------
        test_distribution = {
            "FUNCTIONAL": 0,
            "NEGATIVE": 0,
            "SECURITY": 0,
            "CONTRACT": 0,
            "FUZZ": 0,
        }
        # Fetch active test cases for the scoped projects and count categories.
        test_cases = await prisma.testcase.find_many(
            where={"projectId": {"in": project_ids}, "isActive": True},
        )
        for tc in test_cases:
            cat = str(tc.category.name if hasattr(tc.category, "name") else tc.category).upper() or "FUNCTIONAL"
            if cat in test_distribution:
                test_distribution[cat] += 1

        total_test_runs = len(test_runs)
        total_passed = sum(r.passed for r in test_runs)
        total_failed = sum(r.failed for r in test_runs)
        total_tests = total_passed + total_failed
        pass_rate = round((total_passed / total_tests) * 100, 1) if total_tests > 0 else 0

        # Fetch API Specs to determine Swagger info
        api_specs = await prisma.apispec.find_many(
            where={"projectId": {"in": project_ids}},
            order={"createdAt": "desc"}
        )
        project_spec_map = {}
        for spec in api_specs:
            if spec.projectId not in project_spec_map:
                project_spec_map[spec.projectId] = spec

        recent_runs_raw = test_runs[:5]
        project_name_map = {p.id: p.name for p in projects}

        recent_runs = []
        for run in recent_runs_raw:
            duration_str = DashboardService._format_duration(run.durationMs)
            recent_runs.append({
                "id": run.id,
                "projectName": project_name_map.get(run.projectId, "Unknown"),
                "projectId": run.projectId,
                "status": run.status,
                "totalTests": run.total_tests,
                "passed": run.passed,
                "failed": run.failed,
                "duration": duration_str,
                "date": run.createdAt.isoformat() if run.createdAt else None,
            })

        # Active projects with latest stats
        latest_run_map: dict[str, object] = {}
        project_total_runs_map: dict[str, int] = {}
        project_total_passed_map: dict[str, int] = {}
        project_total_failed_map: dict[str, int] = {}
        
        for run in test_runs:
            if run.projectId not in project_total_runs_map:
                project_total_runs_map[run.projectId] = 0
                project_total_passed_map[run.projectId] = 0
                project_total_failed_map[run.projectId] = 0
                
            project_total_runs_map[run.projectId] += 1
            project_total_passed_map[run.projectId] += run.passed
            project_total_failed_map[run.projectId] += run.failed
            
            if run.projectId not in latest_run_map:
                latest_run_map[run.projectId] = run

        test_suites = await prisma.testsuite.find_many(
            where={"projectId": {"in": project_ids}}
        )
        project_suites_map: dict[str, int] = {}
        for suite in test_suites:
            project_suites_map[suite.projectId] = project_suites_map.get(suite.projectId, 0) + 1

        active_projects = []
        for p in projects:
            latest_run = latest_run_map.get(p.id)
            proj_total_runs = project_total_runs_map.get(p.id, 0)
            proj_total_apis = project_endpoints_map.get(p.id, 0)
            proj_suites_count = project_suites_map.get(p.id, 0)
            
            agg_passed = project_total_passed_map.get(p.id, 0)
            agg_failed = project_total_failed_map.get(p.id, 0)
            agg_total_tests = agg_passed + agg_failed
            proj_pass_rate = round((agg_passed / agg_total_tests) * 100) if agg_total_tests > 0 else None

            status = "PENDING"
            if proj_total_runs > 0 and latest_run and latest_run.status == "COMPLETED":
                status = "COMPLETED"
            elif proj_suites_count > 0 and proj_total_runs == 0:
                status = "RUNNING"
            elif proj_total_runs > 0:
                status = "RUNNING"

            swagger_name, api_version = DashboardService._parse_swagger_info(p, project_spec_map.get(p.id))

            active_projects.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "swaggerName": swagger_name,
                "apiVersion": api_version,
                "lastRunDate": latest_run.createdAt.isoformat() if latest_run else None,
                "lastRunStatus": status,
                "passed": agg_passed,
                "failed": agg_failed,
                "passRate": proj_pass_rate,
                "totalRuns": proj_total_runs,
                "totalApisTested": proj_total_apis,
            })

        return {
            "totalApisTested": total_endpoints,
            "totalProjects": total_projects,
            "totalTestRuns": total_test_runs,
            "passRate": pass_rate,
            "totalTestsRun": total_tests,
            "totalPassed": total_passed,
            "totalFailed": total_failed,
            "testDistribution": test_distribution,
            "recentRuns": recent_runs,
            "activeProjects": active_projects,
        }

    @staticmethod
    def _format_duration(duration_ms: int | None) -> str:
        if not duration_ms:
            return "—"
        secs = duration_ms // 1000
        mins = secs // 60
        secs = secs % 60
        return f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

    @staticmethod
    def _parse_swagger_info(project, spec):
        swagger_name = project.name
        api_version = None
        if spec and spec.parsed_spec:
            try:
                spec_data = spec.parsed_spec
                if isinstance(spec_data, str):
                    spec_data = json.loads(spec_data)
                
                if isinstance(spec_data, dict):
                    info = spec_data.get("info", {})
                    if info:
                        swagger_name = info.get("title", swagger_name)
                        api_version = info.get("version")
            except Exception as e:
                logger.warning(f"Error parsing swagger spec for project {project.id}: {e}")
        return swagger_name, api_version

    @staticmethod
    async def get_reports(user: dict):
        projects = await DashboardService.get_scoped_projects(user)
        project_ids = [p.id for p in projects]
        project_name_map = {p.id: p.name for p in projects}

        if not project_ids:
            return []

        test_runs = await prisma.testrun.find_many(
            where={
                "projectId": {"in": project_ids},
                "status": {"in": ["COMPLETED", "FAILED"]},
            },
            order={"createdAt": "desc"},
            take=20,
        )

        reports = []
        for run in test_runs:
            vulns = await prisma.securityfinding.count(where={"runId": run.id})
            results = await prisma.testresult.find_many(
                where={"runId": run.id},
                include={"test": True},
            )

            passed_tests = []
            failed_tests = []
            category_summary: dict[str, int] = {}
            for res in results:
                cat = str(res.category) if res.category else (str(res.test.category) if res.test and res.test.category else None)
                sub = str(res.subCategory) if res.subCategory else None
                if cat:
                    category_summary[cat] = category_summary.get(cat, 0) + 1
                
                test_summary = {
                    "name": res.test.name if res.test else f"Test {res.testCaseId[:8]}",
                    "method": res.test.method if res.test else "GET",
                    "endpoint": res.test.endpoint_path if res.test else "/",
                    "expected": res.expected_status,
                    "actual": res.actual_status,
                    "category": cat,
                    "subCategory": sub,
                }
                if res.status == "PASSED":
                    passed_tests.append(test_summary)
                elif res.status == "FAILED":
                    test_summary["message"] = res.error_message or f"Expected {res.expected_status}, got {res.actual_status}"
                    failed_tests.append(test_summary)

            total = run.passed + run.failed
            coverage = round((run.passed / total) * 100) if total > 0 else 0
            duration_str = DashboardService._format_duration(run.durationMs)

            reports.append({
                "id": run.id,
                "project": project_name_map.get(run.projectId, "Unknown"),
                "projectId": run.projectId,
                "date": run.createdAt.strftime("%Y-%m-%d") if run.createdAt else "—",
                "duration": duration_str,
                "passed": run.passed,
                "failed": run.failed,
                "coverage": coverage,
                "vulns": vulns,
                "categorySummary": category_summary,
                "passedTests": passed_tests,
                "failedTests": failed_tests,
            })

        return reports

    @staticmethod
    async def get_report_detail(run_id: str, user: dict):
        run = await prisma.testrun.find_unique(
            where={"id": run_id},
            include={"project": True},
        )

        if not run:
            return None

        # Access check
        system_role = user.get("systemRole", "USER")
        if system_role not in ADMIN_ROLES:
            user_id = user.get("userId")
            if not user_id:
                raise PermissionError("Access denied")
            membership = await prisma.projectmember.find_unique(
                where={"projectId_userId": {"projectId": run.projectId, "userId": user_id}}
            )
            if not membership:
                raise PermissionError("Access denied")

        results = await prisma.testresult.find_many(
            where={"runId": run_id},
            include={"test": True},
            order={"executedAt": "desc"},
        )

        vulns = await prisma.securityfinding.count(where={"runId": run_id})

        passed_tests = []
        failed_tests = []
        category_summary: dict[str, int] = {}
        for res in results:
            cat = res.category.value if res.category else (res.test.category.value if res.test and res.test.category else None)
            sub = res.subCategory.value if res.subCategory else None
            if cat:
                category_summary[cat] = category_summary.get(cat, 0) + 1
            
            test_summary = {
                "name": res.test.name if res.test else f"Test {res.testCaseId[:8]}",
                "method": res.test.method if res.test else "GET",
                "endpoint": res.test.endpoint_path if res.test else "/",
                "expected": res.expected_status,
                "actual": res.actual_status,
                "responseTimeMs": res.response_time_ms,
                "category": cat,
                "subCategory": sub,
            }
            if res.status == "PASSED":
                passed_tests.append(test_summary)
            elif res.status == "FAILED":
                test_summary["message"] = res.error_message or f"Expected {res.expected_status}, got {res.actual_status}"
                failed_tests.append(test_summary)

        total = run.passed + run.failed
        coverage = round((run.passed / total) * 100) if total > 0 else 0
        duration_str = DashboardService._format_duration(run.durationMs)

        return {
            "id": run.id,
            "project": run.project.name if run.project else "Unknown",
            "projectId": run.projectId,
            "date": run.createdAt.strftime("%Y-%m-%d") if run.createdAt else "—",
            "duration": duration_str,
            "passed": run.passed,
            "failed": run.failed,
            "coverage": coverage,
            "vulns": vulns,
            "categorySummary": category_summary,
            "passedTests": passed_tests,
            "failedTests": failed_tests,
        }
