import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/", summary="Главная", tags=["Основные"])
def home():
    return "Тест fastapi"

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)