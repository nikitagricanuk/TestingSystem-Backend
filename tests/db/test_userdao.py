import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.models.users import Base, Role, Permission, User
from app.db.dao.userdao import UserDAO, RoleEnum
import uuid

@pytest.mark.asyncio
class TestUserDAO:
    @pytest_asyncio.fixture
    async def test_session(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session_maker() as session:
            admin_role = Role(id=uuid.uuid4(), role="admin")
            student_role = Role(id=uuid.uuid4(), role="student")
            session.add_all([admin_role, student_role])
            await session.commit()
            yield session

    async def test_create_user(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            first_name="John",
            middle_name="B.",
            second_name="Doe",
            age=20,
            email="john@example.com",
            phone="1234567890",
            password="securepassword123",
            role=RoleEnum.ADMIN,
            school_id=None,
            session=test_session
        )
        from sqlalchemy import select
        result = await test_session.execute(
            select(User).where(User.email == "john@example.com")
        )
        user_obj = result.scalar_one_or_none()
        assert user_obj is not None
        assert user_obj.first_name == "John"