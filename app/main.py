from typing import Union

from fastapi import FastAPI

from app.db.dao.userdao import UserDAO, RoleEnum

app = FastAPI()


@app.get("/")
async def read_root():
    user = await UserDAO().create(first_name="John", middle_name="B.", second_name="Doe",
                                  age=20, email="my@ngctl.ru", phone="1234562890",
                                  password="securepassword123", role=RoleEnum.ADMIN, school_id=None
                                  )
    return {"Hello": user.first_name}


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
