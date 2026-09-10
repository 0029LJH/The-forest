import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.common.exception.exceptions import (
    BusinessException,
    AuthenticationException,
    ForbiddenException,
)
from app.common.exception.handlers import (
    business_exception_handler,
    authentication_exception_handler,
    forbidden_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from app.common.middleware.logging import LoggingMiddleware
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("forest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("forest Python backend starting...")
    from app.dependencies import engine

    # Auto-create tables (dev convenience)
    await _init_database(engine)

    try:
        from app.engine.es_service import es_service
        await es_service.ensure_index()
    except Exception:
        logger.warning("Elasticsearch not available, skipping index check")

    # Seed dev admin
    if settings.dev_admin.enabled:
        await _seed_dev_admin()

    # Recover jobs orphaned by a previous crash, then start the worker
    from app.ingestion.job_service import worker, recover_interrupted_jobs
    interrupted = await recover_interrupted_jobs()
    if interrupted:
        logger.warning("Marked %d interrupted ingestion jobs as FAILED", interrupted)
    await worker.start()

    # Periodic maintenance: expired upload sessions
    cleanup_task = asyncio.create_task(_upload_cleanup_loop())

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await worker.stop()
    await engine.dispose()
    try:
        from app.engine.es_service import es_service
        await es_service.close()
    except Exception:
        pass
    logger.info("forest Python backend stopped")


async def _upload_cleanup_loop():
    """Hourly cleanup of expired upload sessions (non-critical)."""
    while True:
        try:
            from app.dependencies import async_session_factory
            from app.document.maintenance import DocumentMaintenanceService
            async with async_session_factory() as session:
                service = DocumentMaintenanceService(session)
                cleaned = await service.cleanup_expired_uploads()
                await session.commit()
                if cleaned:
                    logger.info("Upload cleanup: removed %d expired sessions", cleaned)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Upload cleanup error: %s", e)
        await asyncio.sleep(3600)


app = FastAPI(
    title="forest RAG Platform",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.add_middleware(LoggingMiddleware)

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(AuthenticationException, authentication_exception_handler)
app.add_exception_handler(ForbiddenException, forbidden_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Register routers
from app.auth.router import router as auth_router
from app.user.router import router as user_router
from app.group.router import router as group_router, invitation_router, admin_router as group_admin_router
from app.document.router import router as document_router, admin_router as document_admin_router
from app.qa.router import router as qa_router, admin_router as qa_admin_router
from app.assistant.router import router as assistant_router
from app.metrics.router import router as metrics_router
from app.models_config.router import router as model_config_router
from app.audit.router import router as audit_router
from app.system.router import router as system_router
from app.api_token.router import router as api_token_admin_router
from app.open.router import router as open_router

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(user_router, prefix="/api", tags=["User"])
app.include_router(group_router, prefix="/api/groups", tags=["Groups"])
app.include_router(invitation_router, prefix="/api/invitations", tags=["Invitations"])
app.include_router(group_admin_router, prefix="/api/admin", tags=["Admin Groups"])
app.include_router(document_router, prefix="/api", tags=["Documents"])
app.include_router(qa_router, prefix="/api/qa", tags=["QA"])
app.include_router(assistant_router, prefix="/api/assistant", tags=["Assistant"])
app.include_router(document_admin_router, prefix="/api/admin", tags=["Admin Documents"])
app.include_router(qa_admin_router, prefix="/api/admin", tags=["Admin QA"])
app.include_router(metrics_router, prefix="/api/admin/metrics", tags=["Metrics"])
app.include_router(model_config_router, prefix="/api/admin", tags=["Model Config"])
app.include_router(audit_router, prefix="/api/admin", tags=["Audit"])
app.include_router(system_router, prefix="/api/admin", tags=["System"])
app.include_router(api_token_admin_router, prefix="/api/admin", tags=["API Tokens"])
app.include_router(open_router)


async def _init_database(engine):
    """Create all tables and pgvector extension on startup."""
    from sqlalchemy import text
    from app.database import Base
    # Import all models so Base.metadata knows about them
    import app.auth.models as _am       # noqa: F401
    import app.group.models as _gm      # noqa: F401
    import app.document.models as _dm   # noqa: F401
    import app.ingestion.models as _im  # noqa: F401
    import app.assistant.models as _asm # noqa: F401
    import app.qa.models as _qm         # noqa: F401
    import app.metrics.models as _mm    # noqa: F401
    import app.models_config.models as _mcm  # noqa: F401
    import app.audit.models as _audit   # noqa: F401
    import app.api_token.models as _atm  # noqa: F401

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent columns for QA evidence-level statistics (no migration tooling)
        await conn.execute(text(
            "ALTER TABLE qa_messages ADD COLUMN IF NOT EXISTS evidence_level VARCHAR(16)"
        ))
        await conn.execute(text(
            "ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS mode VARCHAR(32) DEFAULT 'CHAT'"
        ))
        await conn.execute(text(
            "ALTER TABLE model_configs ADD COLUMN IF NOT EXISTS parameters JSON"
        ))
        await conn.execute(text(
            "ALTER TABLE model_configs ADD COLUMN IF NOT EXISTS fallback_config_id INTEGER"
        ))
        await conn.execute(text(
            "ALTER TABLE model_configs ADD COLUMN IF NOT EXISTS api_format VARCHAR(16)"
        ))

    # pgvector table + HNSW/GIN indexes — ensure before the first QA request
    # can hit them (previously only created lazily during ingestion, so a
    # fresh database 500'd on the first QA attempt)
    from app.engine.vector_store import PgVectorRetrievalAdapter
    await PgVectorRetrievalAdapter(settings.database_url).ensure_table()

    # 模型卡片注册表：校验 .env 默认模型是否已注册（未注册的模型格式按 URL 推断）
    from app.models_config.cards import load_cards, get_card
    load_cards()
    for default_name, kind in [(settings.chat.model_name, "chat"),
                               (settings.embedding.model_name, "embedding")]:
        card = get_card(default_name)
        if card is None or card.kind.value != kind:
            logger.warning(
                "Default %s model '%s' is not registered as a model card; "
                "API format will be inferred from base_url", kind, default_name)
    logger.info("Database tables initialized")


async def _seed_dev_admin():
    from sqlalchemy import select
    from app.dependencies import async_session_factory
    from app.auth.models import User
    from app.auth.security import hash_password
    from app.auth.enums import SystemRole, UserStatus

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.system_role == SystemRole.ADMIN.value)
        )
        if result.scalar_one_or_none():
            logger.info("Admin user already exists, skipping seed")
            return

        admin = User(
            user_code=settings.dev_admin.username,
            username=settings.dev_admin.username,
            email=settings.dev_admin.email,
            display_name=settings.dev_admin.display_name,
            password_hash=hash_password(settings.dev_admin.password),
            system_role=SystemRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,
            must_change_password=False,
        )
        session.add(admin)
        await session.commit()
        logger.info("Dev admin user seeded: %s", settings.dev_admin.email)
