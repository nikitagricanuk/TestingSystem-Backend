from uuid import UUID

from pydantic import BaseModel


class CertificateFieldIn(BaseModel):
    key: str
    page: int = 0
    x: float
    y: float
    font_size: float = 24


class CertificateSignaturePosition(BaseModel):
    page: int = 0
    x: float
    y: float
    width: float = 150
    height: float = 60


class CertificateTemplateOut(BaseModel):
    id: UUID
    test_id: UUID | None = None
    name: str
    kind: str
    fields: list[CertificateFieldIn] = []
    has_signature: bool = False
    signature_position: CertificateSignaturePosition | None = None


class CertificateFieldsUpdate(BaseModel):
    fields: list[CertificateFieldIn]
    signature_position: CertificateSignaturePosition | None = None
