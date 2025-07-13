# models.py

from pydantic import BaseModel, EmailStr
from typing import Optional, List

class User(BaseModel):
    nome: str
    email: EmailStr
    password: str
    card_id: Optional[str] = None

class Card(BaseModel):
    nome: str
    emailContato: EmailStr
    whatsapp: str
    card_id: Optional[str] = None

    foto_perfil: Optional[str] = None
    biografia: Optional[str] = None

    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    site: Optional[str] = None
    chave_pix: Optional[str] = None

    galeria: Optional[List[str]] = []
