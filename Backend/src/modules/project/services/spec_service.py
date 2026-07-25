import json
import logging
import yaml
from fastapi import UploadFile
from src.middleware import AppError
from src.config import prisma
from prisma import Json as PrismaJson
from src.modules.generator.spec_parser import extract_endpoints
from ..utils import sanitize_json

logger = logging.getLogger(__name__)

async def process_spec_upload(project_id: str, spec: UploadFile, user_id: str, spec_store: dict, spec_name_store: dict, draft_store: dict, base_url_store: dict):
    content = await spec.read()

    try:
        try:
            spec_json = json.loads(content)
        except json.JSONDecodeError:
            spec_json = yaml.safe_load(content)

        if not isinstance(spec_json, dict):
            raise AppError("Invalid spec file: expected a JSON/YAML object", status_code=400)

        # In-memory updates (to be replaced by DB/Cache eventually)
        spec_store[project_id] = spec_json
        spec_name_store[project_id] = spec.filename or "spec"
        draft_store[project_id] = []

        base_url = None
        if "servers" in spec_json and spec_json["servers"]:
            base_url = spec_json["servers"][0].get("url")
        elif "host" in spec_json:
            scheme = spec_json.get("schemes", ["https"])[0]
            base_path = spec_json.get("basePath", "")
            base_url = f"{scheme}://{spec_json['host']}{base_path}"

        if base_url and project_id not in base_url_store:
            base_url_store[project_id] = base_url

        version = spec_json.get("openapi", spec_json.get("swagger", "unknown"))
        file_type = "openapi" if spec_json.get("openapi") else "swagger"

        api_spec = await prisma.apispec.create(
            data={
                "projectId": project_id,
                "file_type": file_type,
                "version": version,
                "file_url": spec.filename or "uploaded.json",
                "uploadedBy": user_id if user_id else None,
                "parsed_spec": PrismaJson(spec_json),
            }
        )
        spec_id = api_spec.id
        logger.info("Created ApiSpec %s for project %s", spec_id, project_id)

        endpoints_count = 0
        try:
            parsed_endpoints = extract_endpoints(spec_json)
            for ep in parsed_endpoints:
                ep_data = {
                    "projectId": project_id,
                    "specId": spec_id,
                    "method": ep.method,
                    "path": ep.path,
                    "requiresAuth": ep.requires_auth,
                }
                if ep.body_schema:
                    ep_data["requestSchema"] = sanitize_json(ep.body_schema)
                if ep.response_schema:
                    ep_data["responseSchema"] = sanitize_json(ep.response_schema)
                await prisma.endpoint.create(data=ep_data)
                endpoints_count += 1
            logger.info("Created %d Endpoint records for spec %s", endpoints_count, spec_id)
        except Exception as e:
            logger.warning("Failed to persist some endpoints: %s", e)

        return spec_id, endpoints_count, len(content)

    except AppError:
        raise
    except Exception as e:
        logger.exception("Spec upload failed")
        raise AppError(f"Invalid spec file: {e}", status_code=400)

async def repair_project_endpoints(project_id: str):
    api_spec = await prisma.apispec.find_first(
        where={"projectId": project_id},
        order={"createdAt": "desc"},
    )
    if not api_spec:
        raise AppError("No ApiSpec found for this project", status_code=404)

    spec_dict = api_spec.parsed_spec if isinstance(api_spec.parsed_spec, dict) else json.loads(api_spec.parsed_spec)

    await prisma.endpoint.delete_many(where={"projectId": project_id})

    parsed_endpoints = extract_endpoints(spec_dict)
    created = 0
    for ep in parsed_endpoints:
        try:
            ep_data = {
                "projectId": project_id,
                "specId": api_spec.id,
                "method": ep.method,
                "path": ep.path,
                "requiresAuth": ep.requires_auth,
            }
            if ep.body_schema:
                ep_data["requestSchema"] = ep.body_schema
            if ep.response_schema:
                ep_data["responseSchema"] = ep.response_schema
            await prisma.endpoint.create(data=ep_data)
            created += 1
        except Exception as e:
            logger.warning("Failed to create endpoint %s %s: %s", ep.method, ep.path, e)

    return created, api_spec.id
