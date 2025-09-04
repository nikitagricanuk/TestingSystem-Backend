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

    async def test_get_user_by_id(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            first_name="Jane",
            middle_name="A.",
            second_name="Smith",
            age=22,
            email="mail@newmail.com",
            phone="0987654321",
            password="anotherpassword123",
            role=RoleEnum.STUDENT,
            school_id=None,
            session=test_session
        )
        user_id = user.id
        retrieved_user = await dao.get_user_by_id(user_id, session=test_session)
        assert retrieved_user is not None
        assert retrieved_user.id == user_id
        assert retrieved_user.first_name == "Jane"

    async def test_update_user_by_id(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            first_name="Alice",
            middle_name="C.",
            second_name="Johnson",
            age=25,
            email="test@test.com",
            phone="1122334455",
            password="password123",
            role=RoleEnum.STUDENT,
            school_id=None,
            session=test_session
        )
        user_id = user.id
        updated_data = {
            "first_name": "Alice Updated",
            "age": 26
        }
        updated_user = await dao.update_user_by_id(user_id, updated_data, session=test_session)
        assert updated_user is not None
        assert updated_user.first_name == "Alice Updated"
        assert updated_user.age == 26

    async def test_update_user_by_email(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            first_name="Bob",
            middle_name="D.",
            second_name="Brown",
            age=30,
            email="emailtest@test.com",
            phone="2233445566",
            password="password456",
            role=RoleEnum.STUDENT,
            school_id=None,
            session=test_session
        )
        updated_data = {
            "first_name": "Bob Updated",
            "age": 31
        }
        updated_user = await dao.update_user_by_email("emailtest@test.com", updated_data, session=test_session)
        assert updated_user is not None
        assert updated_user.first_name == "Bob Updated"
        assert updated_user.age == 31

    async def test_delete_user_by_id(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            first_name="Charlie",
            middle_name="E.",
            second_name="Davis",
            age=28,
            email="test@test.com",
            phone="3344556677",
            password="password789",
            role=RoleEnum.STUDENT,
            school_id=None,
            session=test_session
        )
        user_id = user.id
        await dao.delete_user_by_id(user_id, session=test_session)
        deleted_user = await dao.get_user_by_id(user_id, session=test_session)
        assert deleted_user is None

    async def test_delete_user_by_email(self, test_session):
        dao = UserDAO()
        user = await dao.create(
            first_name="David",
            middle_name="F.",
            second_name="Wilson",
            age=35,
            email="test@test.com",
            phone="4455667788",
            password="password101",
            role=RoleEnum.STUDENT,
            school_id=None,
            session=test_session
        )
        await dao.delete_user_by_email("test@test.com", session=test_session)
        deleted_user = await dao.get_user_by_email("test@test.com", session=test_session)
        assert deleted_user is None