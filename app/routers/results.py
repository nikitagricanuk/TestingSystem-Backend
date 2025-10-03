from uuid import UUID

from fastapi import APIRouter, Depends
router = APIRouter()

@router.get("/tests/result/{result-id}")
async def get_tests_result_result_id(result_id: UUID):
    """Get test result by ID"""
    return {
        "status": "not_implemented",
        "operationId": "get_tests_result_result_id",
        "echo": {"result-id": result_id}
    }
