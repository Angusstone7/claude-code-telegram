# API Contract: Authentication

**Base path**: `/api/v1/auth`
**Auth**: Public (login, refresh) / JWT Bearer (остальные)

---

## POST /api/v1/auth/login

Аутентификация пользователя. Возвращает access token, устанавливает refresh token в HTTP-only cookie.

**Request**:
```python
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
```

**Response 200**:
```python
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds (900 = 15 min)
    user: UserProfile

class UserProfile(BaseModel):
    id: str  # UUID
    username: str
    display_name: str
    telegram_id: Optional[int]
    role: str
```

**Response Headers**:
```
Set-Cookie: refresh_token=<token>; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=604800
```

**Errors**:
- `401 Unauthorized`: Неверные учётные данные
- `429 Too Many Requests`: Превышен лимит попыток входа (5 за 15 мин)

---

## POST /api/v1/auth/refresh

Обновление access token через refresh cookie.

**Request**: Нет тела. Refresh token читается из cookie.

**Response 200**:
```python
class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
```

**Errors**:
- `401 Unauthorized`: Refresh token отсутствует, истёк или отозван

---

## POST /api/v1/auth/logout

Инвалидация текущего refresh token.

**Request**: Нет тела. Refresh token из cookie.

**Response 200**:
```python
class MessageResponse(BaseModel):
    message: str = "Logged out successfully"
```

**Response Headers**:
```
Set-Cookie: refresh_token=; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=0
```

---

## GET /api/v1/auth/me

Получение профиля текущего пользователя.

**Auth**: JWT Bearer

**Response 200**:
```python
class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    telegram_id: Optional[int]
    role: str
    created_at: datetime
```

---

## PATCH /api/v1/auth/me

Обновление профиля текущего пользователя.

**Auth**: JWT Bearer

**Request**:
```python
class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    telegram_id: Optional[int] = Field(None, gt=0)
```

**Response 200**: `UserProfile`

**Errors**:
- `409 Conflict`: Telegram ID уже привязан к другому аккаунту (FR-019)

---

## POST /api/v1/auth/users

Создание нового пользователя (только для администраторов).

**Auth**: JWT Bearer (role=admin)

**Request**:
```python
class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8)
    display_name: str = Field(..., min_length=1, max_length=100)
    telegram_id: Optional[int] = Field(None, gt=0)
```

**Response 201**: `UserProfile`

**Errors**:
- `409 Conflict`: Username или Telegram ID уже существует
- `403 Forbidden`: Недостаточно прав

---

## PATCH /api/v1/auth/users/{user_id}/password

Сброс пароля пользователя (только для администраторов).

**Auth**: JWT Bearer (role=admin)

**Request**:
```python
class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)
```

**Response 200**: `MessageResponse`
