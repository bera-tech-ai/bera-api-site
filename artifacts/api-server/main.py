"""
Bera AI API — Developer Platform
Creator: Bruce Bera | Bera Tech
GitHub: https://github.com/bera-tech-ai
"""
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()

from database import (
    init_db,
    create_user,
    get_user_by_api_key,
    increment_request_count,
    revoke_key,
    revoke_key_by_id,
    log_request,
    add_audit_log,
    get_all_users,
    get_stats,
    get_audit_log,
    get_requests,
    RATE_LIMITS,
)
from ai_scrapers import get_ai_answer
from ssh_handler import run_ssh_commands, format_ssh_results
from intent_parser import parse_intent
from agent_executor import execute_agent_task, push_project_to_github, WORKSPACE_DIR

# ─── Config ─────────────────────────────────────────────────────────────────
MASTER_ADMIN_KEY = os.getenv("MASTER_ADMIN_KEY", "bruce_master_key_change_this")
GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Bera AI API",
    description="Developer AI platform — chat, agent actions, SSH, GitHub. Built by Bera Tech.",
    version="2.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("Bera AI API v2 is ready 🚀  workspace=%s", WORKSPACE_DIR)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    key = auth.replace("Bearer ", "").strip()
    if key != MASTER_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return True


async def _check_key(apikey: str) -> dict:
    if not apikey:
        raise HTTPException(status_code=401, detail="API key required. Get one free at /api/register")
    user = await get_user_by_api_key(apikey)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    rate_limit = user["rate_limit_per_day"]
    if rate_limit != -1 and user["requests_used_today"] >= rate_limit:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({rate_limit}/day). Upgrade your plan.")
    return user


def _bera_response(result: str, actions: list = None, **extra):
    return {
        "status": True,
        "creator": "Bruce Bera",
        "developer": "Bera Tech",
        "result": result,
        "reply": result,
        "message": result,
        "actions_taken": actions or [],
        "timestamp": _now_iso(),
        **extra,
    }


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/healthz", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "Bera AI API", "version": "2.0.0"}


@app.get("/api/status", tags=["system"])
async def api_status():
    stats = await get_stats()
    return {
        "status": "operational",
        "service": "Bera AI API",
        "version": "2.0.0",
        "creator": "Bruce Bera",
        "github": "https://github.com/bera-tech-ai",
        "total_users": stats.get("total_users", 0),
        "total_requests": stats.get("total_requests", 0),
        "uptime": "100%",
    }


# ─── GET AI Endpoints (WhatsApp bot compatible) ───────────────────────────────
# These match the api.gifted.co.ke format the cloud-bera bot uses

@app.get("/api/ai/chat", tags=["ai"])
@app.get("/api/ai/gpt", tags=["ai"])
@app.get("/api/ai/gemini", tags=["ai"])
@app.get("/api/ai/ai", tags=["ai"])
@app.get("/api/ai/chatgpt", tags=["ai"])
@app.get("/api/ai/llama", tags=["ai"])
@app.get("/api/ai/mistral", tags=["ai"])
@app.get("/api/ai/deepseek", tags=["ai"])
async def ai_get(
    q: str = Query(..., description="Your question or prompt"),
    apikey: str = Query(default="", description="Your API key"),
    request: Request = None,
):
    """
    Simple AI chat endpoint — GET style.
    Compatible with cloud-bera WhatsApp bot (NICK_API).
    """
    start = time.time()
    user = None

    if apikey:
        try:
            user = await _check_key(apikey)
        except HTTPException as e:
            return JSONResponse({"status": False, "error": e.detail}, status_code=e.status_code)

    try:
        answer = await get_ai_answer(q)
    except Exception as e:
        logger.error("AI answer error: %s", e)
        answer = "Bera AI is temporarily unavailable. Please try again."

    elapsed_ms = int((time.time() - start) * 1000)

    if user:
        await increment_request_count(user["id"])
        await log_request(
            user_id=user["id"],
            user_message=q,
            actions_taken=["ai_query"],
            response=answer[:2000],
            response_time_ms=elapsed_ms,
            success=True,
        )

    return _bera_response(answer, ["ai_query"], response_time_ms=elapsed_ms)


@app.get("/api/ai/agent", tags=["ai"])
async def ai_agent_get(
    q: str = Query(..., description="Task to execute (natural language)"),
    apikey: str = Query(default="", description="Your API key"),
    request: Request = None,
):
    """
    Agent mode — executes real actions (bash, files, folders, GitHub).
    """
    start = time.time()
    user = None

    if apikey:
        try:
            user = await _check_key(apikey)
        except HTTPException as e:
            return JSONResponse({"status": False, "error": e.detail}, status_code=e.status_code)

    actions = await execute_agent_task(q)
    elapsed_ms = int((time.time() - start) * 1000)

    if actions:
        result_parts = [a.output for a in actions]
        result = "\n\n".join(result_parts)
        action_names = [a.action for a in actions]
        success = all(a.success for a in actions)
    else:
        # No specific action detected — fall back to AI chat
        try:
            result = await get_ai_answer(q)
            action_names = ["ai_query"]
            success = True
        except Exception:
            result = "I could not understand or execute that task. Try: 'create folder myproject', 'run: ls -la', 'list my github repos'"
            action_names = ["no_op"]
            success = False

    if user:
        await increment_request_count(user["id"])
        await log_request(
            user_id=user["id"],
            user_message=q,
            actions_taken=action_names,
            response=result[:2000],
            response_time_ms=elapsed_ms,
            success=success,
        )

    return _bera_response(result, action_names, response_time_ms=elapsed_ms)


# ─── POST Chat endpoint (full featured) ──────────────────────────────────────

class SshCredentials(BaseModel):
    host: str
    port: int = 22
    username: str
    password: Optional[str] = None
    private_key: Optional[str] = None


class ChatInput(BaseModel):
    apikey: str
    message: str
    ssh: Optional[SshCredentials] = None
    agent_mode: bool = False


@app.post("/api/chat", tags=["chat"])
async def chat(payload: ChatInput, request: Request):
    start_time = time.time()
    ip = _client_ip(request)

    user = await _check_key(payload.apikey)
    actions_taken: list[str] = []
    result_parts: list[str] = []

    # ── Agent mode: real local actions ──
    if payload.agent_mode:
        actions = await execute_agent_task(payload.message)
        if actions:
            result_parts = [a.output for a in actions]
            actions_taken = [a.action for a in actions]

    # ── SSH actions ──
    intent = parse_intent(payload.message)
    if intent.needs_ssh and payload.ssh and not payload.agent_mode:
        ssh = payload.ssh
        try:
            ssh_results = await run_ssh_commands(
                host=ssh.host, port=ssh.port, username=ssh.username,
                password=ssh.password, private_key=ssh.private_key,
                commands=intent.ssh_commands,
            )
            result_parts.append(format_ssh_results(ssh_results))
            actions_taken.append("ssh_action")
        except Exception as e:
            result_parts.append(f"❌ SSH failed: {e}")
            actions_taken.append("ssh_error")
    elif intent.needs_ssh and not payload.ssh and not payload.agent_mode:
        result_parts.append("⚠️ SSH credentials required. Include the `ssh` field.")

    # ── AI query ──
    if intent.needs_ai or not result_parts:
        ai_query = intent.ai_query or payload.message
        try:
            ai_answer = await get_ai_answer(ai_query)
            result_parts.append(ai_answer)
            actions_taken.append("ai_query")
        except Exception as e:
            logger.error("AI error: %s", e)
            result_parts.append("AI is temporarily unavailable. Please try again.")

    if not result_parts:
        result_parts.append("I'm not sure what you need. Please clarify.")
        actions_taken.append("no_op")

    final_result = "\n\n".join(result_parts)
    elapsed_ms = int((time.time() - start_time) * 1000)

    await increment_request_count(user["id"])
    await log_request(
        user_id=user["id"], user_message=payload.message,
        actions_taken=actions_taken, response=final_result[:2000],
        response_time_ms=elapsed_ms, success=True,
    )
    await add_audit_log(
        user_id=user["id"], action="api_call",
        details={"snippet": payload.message[:100], "actions": actions_taken},
        ip_address=ip,
    )

    return _bera_response(final_result, actions_taken,
                          conversation_id=f"conv_{uuid.uuid4().hex[:10]}",
                          response_time_ms=elapsed_ms)


# ─── POST Agent endpoint ──────────────────────────────────────────────────────

class AgentInput(BaseModel):
    apikey: str
    task: str


@app.post("/api/agent", tags=["agent"])
async def agent_execute(payload: AgentInput, request: Request):
    """Execute a real action: bash, files, folders, GitHub ops."""
    ip = _client_ip(request)
    user = await _check_key(payload.apikey)
    start = time.time()

    actions = await execute_agent_task(payload.task)
    elapsed_ms = int((time.time() - start) * 1000)

    if actions:
        result = "\n\n".join(a.output for a in actions)
        action_names = [a.action for a in actions]
        success = all(a.success for a in actions)
    else:
        result = await get_ai_answer(payload.task)
        action_names = ["ai_query"]
        success = True

    await increment_request_count(user["id"])
    await log_request(
        user_id=user["id"], user_message=payload.task,
        actions_taken=action_names, response=result[:2000],
        response_time_ms=elapsed_ms, success=success,
    )
    await add_audit_log(user_id=user["id"], action="agent_execute",
                        details={"task": payload.task[:100]}, ip_address=ip)

    return _bera_response(result, action_names, response_time_ms=elapsed_ms)


# ─── GitHub endpoint ──────────────────────────────────────────────────────────

class GitHubPushInput(BaseModel):
    apikey: str
    repo_name: str
    description: str = ""
    local_path: str = "."
    commit_message: str = "Initial commit"


@app.post("/api/github/push", tags=["github"])
async def github_push(payload: GitHubPushInput, request: Request):
    """Create a GitHub repo and push local workspace files to it."""
    user = await _check_key(payload.apikey)
    start = time.time()

    results = await push_project_to_github(
        local_path=payload.local_path,
        repo_name=payload.repo_name,
        description=payload.description,
    )
    elapsed_ms = int((time.time() - start) * 1000)
    output = "\n\n".join(r.output for r in results)
    success = all(r.success for r in results)

    await increment_request_count(user["id"])

    return _bera_response(output, [r.action for r in results],
                          success=success, response_time_ms=elapsed_ms)


# ─── API key management ───────────────────────────────────────────────────────

class RegisterInput(BaseModel):
    email: str
    name: str
    plan: str = "free"


class RevokeKeyInput(BaseModel):
    apikey: str


@app.post("/api/register", tags=["keys"])
async def register(payload: RegisterInput, request: Request):
    ip = _client_ip(request)
    try:
        result = await create_user(email=payload.email, name=payload.name, plan=payload.plan)
        await add_audit_log(user_id=None, action="create_key",
                            details={"email": payload.email, "plan": payload.plan}, ip_address=ip)
        limits = {"free": 100, "pro": 10000, "enterprise": "unlimited"}
        limit = limits.get(payload.plan, 100)
        return {
            "status": True,
            "api_key": result["api_key"],
            "plan": payload.plan,
            "daily_limit": limit,
            "message": f"Welcome {payload.name}! Your {payload.plan} API key is ready.",
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/verify-key", tags=["keys"])
async def verify_key(apikey: str):
    user = await get_user_by_api_key(apikey)
    if not user:
        return {"valid": False}
    limit = user["rate_limit_per_day"]
    return {
        "valid": True,
        "plan": user["plan"],
        "requests_used": user["requests_used_today"],
        "limit": limit if limit != -1 else None,
        "name": user["name"],
        "email": user["email"],
    }


@app.post("/api/revoke-key", tags=["keys"])
async def revoke_own_key(payload: RevokeKeyInput, request: Request):
    ip = _client_ip(request)
    ok = await revoke_key(payload.apikey)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")
    await add_audit_log(user_id=None, action="revoke_key",
                        details={"prefix": payload.apikey[:20]}, ip_address=ip)
    return {"status": True, "message": "API key revoked"}


# ─── Admin endpoints ──────────────────────────────────────────────────────────

class AdminCreateKeyInput(BaseModel):
    email: str
    name: str
    plan: str = "free"
    rate_limit: Optional[int] = None


@app.get("/api/admin/stats", tags=["admin"])
async def admin_stats(request: Request, _=Depends(_require_admin)):
    return await get_stats()


@app.get("/api/admin/users", tags=["admin"])
async def admin_list_users(request: Request, _=Depends(_require_admin)):
    return await get_all_users()


@app.post("/api/admin/create-key", tags=["admin"])
async def admin_create_key(payload: AdminCreateKeyInput, request: Request, _=Depends(_require_admin)):
    ip = _client_ip(request)
    try:
        result = await create_user(email=payload.email, name=payload.name,
                                   plan=payload.plan, rate_limit=payload.rate_limit)
        await add_audit_log(user_id=None, action="admin_create_key",
                            details={"email": payload.email, "plan": payload.plan}, ip_address=ip)
        return {"status": True, "api_key": result["api_key"],
                "message": f"Key created for {payload.email} ({payload.plan})"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.delete("/api/admin/revoke/{key_id}", tags=["admin"])
async def admin_revoke_key(key_id: str, request: Request, _=Depends(_require_admin)):
    ip = _client_ip(request)
    ok = await revoke_key_by_id(int(key_id)) if key_id.isdigit() else await revoke_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")
    await add_audit_log(user_id=None, action="admin_revoke_key",
                        details={"key_id": key_id}, ip_address=ip)
    return {"status": True, "message": "Key revoked"}


@app.get("/api/admin/audit-log", tags=["admin"])
async def admin_audit_log(request: Request, limit: int = 100, _=Depends(_require_admin)):
    return await get_audit_log(limit=limit)


@app.get("/api/admin/requests", tags=["admin"])
async def admin_requests(request: Request, limit: int = 100, _=Depends(_require_admin)):
    return await get_requests(limit=limit)


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
