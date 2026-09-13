from pydantic import BaseModel


class AdminStatsOut(BaseModel):
    active_now: int
    active_today: int
    avg_score: float
    total_finished_attempts: int


class WeekdayLoad(BaseModel):
    weekday: int  # 0 = Monday .. 6 = Sunday
    label: str
    count: int


class RegionCount(BaseModel):
    region: str | None
    count: int


class AgeBucketCount(BaseModel):
    bucket: str
    count: int


class AdminDemographicsOut(BaseModel):
    by_region: list[RegionCount]
    by_age: list[AgeBucketCount]
