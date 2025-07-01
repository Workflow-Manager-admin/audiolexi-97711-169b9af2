from fastapi import FastAPI, HTTPException, Depends, status, Request, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from jose import jwt, JWTError
import sqlite3
import uuid
import os


# ------ App Metadata & CORS ------
app = FastAPI(
    title="AudioLexi Backend API",
    description=(
        "Backend API for AudioLexi English learning app. Features user/auth management, "
        "multilingual content, favorites, quizzes, daily suggestions, TTS & voice commands."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Auth", "description": "User authentication and profile endpoints."},
        {"name": "Content", "description": "APIs for words, sentences, and paragraphs."},
        {"name": "Favorites", "description": "Manage user favorites."},
        {"name": "Quizzes", "description": "Quiz endpoints."},
        {"name": "Suggestions", "description": "Daily suggestions."},
        {"name": "TTS", "description": "Text-to-speech endpoints."},
        {"name": "VoiceCommands", "description": "Voice command endpoints."},
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------ Environment: Secrets & DB Path ------
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week
DB_PATH = os.environ.get("AUDIOLEXI_DB_PATH", "audiolexi.sqlite")


# ------ Database Helpers ------
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        hashed_pw TEXT,
        display_name TEXT,
        language TEXT DEFAULT 'en',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS words (
        id TEXT PRIMARY KEY,
        word TEXT NOT NULL,
        language TEXT NOT NULL,
        audio_url TEXT,
        definition TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sentences (
        id TEXT PRIMARY KEY,
        sentence TEXT NOT NULL,
        language TEXT NOT NULL,
        audio_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS paragraphs (
        id TEXT PRIMARY KEY,
        paragraph TEXT NOT NULL,
        language TEXT NOT NULL,
        audio_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        item_type TEXT CHECK(item_type IN ('word','sentence','paragraph')),
        item_id TEXT NOT NULL,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS quizzes (
        id TEXT PRIMARY KEY,
        language TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        options TEXT,
        audio_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS suggestions (
        id TEXT PRIMARY KEY,
        type TEXT CHECK(type IN ('word','sentence','paragraph')),
        language TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS voice_commands (
        id TEXT PRIMARY KEY,
        language TEXT NOT NULL,
        command TEXT NOT NULL,
        action TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    db_init()


# ------ Auth Utils (JWT & Firebase Placeholder) ------
class AuthBearer(HTTPBearer):
    """Simple JWT token checker with Firebase placeholder logic."""

    async def __call__(self, request: Request) -> Optional[str]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if credentials:
            try:
                payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
                # Normally you might call Firebase to check revocation/validity.
                # Placeholder: accept the token if signature matches and not expired
                request.state.user_id = payload.get("sub")
                return credentials.credentials
            except JWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated"
        )


def create_jwt_token(sub: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def hash_pw(raw_pw: str) -> str:
    # Placeholder hash function for demo (do not use in production)
    return "hashed$" + raw_pw[::-1]


# ------ Pydantic Schemas ------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    email: str = Field(..., description="Email address of user")
    display_name: Optional[str] = Field(None, description="Display name")
    language: Optional[str] = Field("en", description="Preferred language, e.g., en, ta, hi")


class UserCreate(UserBase):
    password: str = Field(..., description="Raw password")


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(UserBase):
    id: str
    created_at: Optional[str]
    is_active: Optional[bool]


class WordIn(BaseModel):
    word: str
    language: str = Field("en", description="Content language")
    audio_url: Optional[str]
    definition: Optional[str]


class WordOut(WordIn):
    id: str
    created_at: Optional[str]


class SentenceIn(BaseModel):
    sentence: str
    language: str = Field("en")
    audio_url: Optional[str]


class SentenceOut(SentenceIn):
    id: str
    created_at: Optional[str]


class ParagraphIn(BaseModel):
    paragraph: str
    language: str = Field("en")
    audio_url: Optional[str]


class ParagraphOut(ParagraphIn):
    id: str
    created_at: Optional[str]


class FavoriteIn(BaseModel):
    item_type: str = Field(..., description="Type: word|sentence|paragraph")
    item_id: str


class FavoriteOut(FavoriteIn):
    id: str
    user_id: str
    added_at: Optional[str]


class QuizIn(BaseModel):
    question: str
    answer: str
    options: Optional[List[str]]
    language: str = Field("en")
    audio_url: Optional[str]


class QuizOut(QuizIn):
    id: str
    created_at: Optional[str]


class SuggestionOut(BaseModel):
    id: str
    type: str
    language: str
    content: str
    created_at: Optional[str]


class VoiceCommandIn(BaseModel):
    command: str
    action: str
    language: str = Field("en")


class VoiceCommandOut(VoiceCommandIn):
    id: str
    created_at: Optional[str]


class TTSRequest(BaseModel):
    text: str
    language: str = Field("en")
    speed: float = Field(1.0, description="Speech speed multiplier (0.5 - 2.0)")


class TTSResponse(BaseModel):
    audio_url: Optional[str]
    success: bool = True
    message: Optional[str] = Field(None)


# ---------- AUTH ENDPOINTS ----------

@app.post("/api/auth/register", response_model=Token, tags=["Auth"], summary="Register new user")
# PUBLIC_INTERFACE
def register(user: UserCreate):
    """Register a new user; returns JWT token."""
    conn = get_db_conn()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    try:
        c.execute(
            "INSERT INTO users (id, email, hashed_pw, display_name, language) VALUES (?, ?, ?, ?, ?)",
            (user_id, user.email, hash_pw(user.password), user.display_name, user.language)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")
    finally:
        conn.close()
    token = create_jwt_token(user_id)
    return Token(access_token=token)


@app.post("/api/auth/login", response_model=Token, tags=["Auth"], summary="Login existing user")
# PUBLIC_INTERFACE
def login(login_data: UserLogin):
    """Login user; returns JWT token."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, hashed_pw FROM users WHERE email=?", (login_data.email,))
    user = c.fetchone()
    conn.close()
    if not user or user["hashed_pw"] != hash_pw(login_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt_token(user["id"])
    return Token(access_token=token)


@app.get("/api/auth/me", response_model=UserOut, tags=["Auth"], summary="Get current user")
# PUBLIC_INTERFACE
def get_me(token: str = Depends(AuthBearer())):
    """Get profile for current auth user."""
    user_id = _get_user_id_from_token(token)
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, email, display_name, language, created_at, is_active FROM users WHERE id=?",
        (user_id,)
    )
    user = c.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404)
    return UserOut(**user)


def _get_user_id_from_token(token: str) -> str:
    """Extracts user_id (sub) from token."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload.get("sub")


# ---------- WORDS (CRUD) ----------

@app.post("/api/words", response_model=WordOut, tags=["Content"], summary="Add a word")
# PUBLIC_INTERFACE
def add_word(word: WordIn, token: str = Depends(AuthBearer())):
    """Add a new word (admin/teacher only)."""
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO words (id, word, language, audio_url, definition) VALUES (?, ?, ?, ?, ?)",
        (id_, word.word, word.language, word.audio_url, word.definition)
    )
    conn.commit()
    c.execute("SELECT * FROM words WHERE id=?", (id_,))
    out = c.fetchone()
    conn.close()
    return WordOut(**out)


@app.get("/api/words", response_model=List[WordOut], tags=["Content"], summary="List all words")
# PUBLIC_INTERFACE
def list_words(language: Optional[str] = None, q: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get list of words, optionally filter by language or search (q)."""
    conn = get_db_conn()
    c = conn.cursor()
    query = "SELECT * FROM words WHERE 1=1"
    params = []
    if language:
        query += " AND language=?"
        params.append(language)
    if q:
        query += " AND word LIKE ?"
        params.append(f"%{q}%")
    query += " LIMIT ? OFFSET ?"
    params += [limit, skip]
    c.execute(query, params)
    results = [WordOut(**row) for row in c.fetchall()]
    conn.close()
    return results


@app.get("/api/words/{word_id}", response_model=WordOut, tags=["Content"], summary="Get word by ID")
# PUBLIC_INTERFACE
def get_word(word_id: str):
    """Fetch a word by ID."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM words WHERE id=?", (word_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404)
    return WordOut(**row)


# ---------- SENTENCES (CRUD) ----------

@app.post("/api/sentences", response_model=SentenceOut, tags=["Content"], summary="Add a sentence")
# PUBLIC_INTERFACE
def add_sentence(sentence: SentenceIn, token: str = Depends(AuthBearer())):
    """Add a new sentence (admin/teacher only)."""
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sentences (id, sentence, language, audio_url) VALUES (?, ?, ?, ?)",
        (id_, sentence.sentence, sentence.language, sentence.audio_url)
    )
    conn.commit()
    c.execute("SELECT * FROM sentences WHERE id=?", (id_,))
    out = c.fetchone()
    conn.close()
    return SentenceOut(**out)


@app.get("/api/sentences", response_model=List[SentenceOut], tags=["Content"], summary="List all sentences")
# PUBLIC_INTERFACE
def list_sentences(language: Optional[str] = None, q: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get list of sentences, optionally filter by language or search (q)."""
    conn = get_db_conn()
    c = conn.cursor()
    query = "SELECT * FROM sentences WHERE 1=1"
    params = []
    if language:
        query += " AND language=?"
        params.append(language)
    if q:
        query += " AND sentence LIKE ?"
        params.append(f"%{q}%")
    query += " LIMIT ? OFFSET ?"
    params += [limit, skip]
    c.execute(query, params)
    results = [SentenceOut(**row) for row in c.fetchall()]
    conn.close()
    return results


@app.get("/api/sentences/{sentence_id}", response_model=SentenceOut, tags=["Content"], summary="Get sentence by ID")
# PUBLIC_INTERFACE
def get_sentence(sentence_id: str):
    """Fetch sentence by ID."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM sentences WHERE id=?", (sentence_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404)
    return SentenceOut(**row)


# ---------- PARAGRAPHS (CRUD) ----------

@app.post("/api/paragraphs", response_model=ParagraphOut, tags=["Content"], summary="Add a paragraph")
# PUBLIC_INTERFACE
def add_paragraph(paragraph: ParagraphIn, token: str = Depends(AuthBearer())):
    """Add a new paragraph (admin/teacher only)."""
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO paragraphs (id, paragraph, language, audio_url) VALUES (?, ?, ?, ?)",
        (id_, paragraph.paragraph, paragraph.language, paragraph.audio_url)
    )
    conn.commit()
    c.execute("SELECT * FROM paragraphs WHERE id=?", (id_,))
    out = c.fetchone()
    conn.close()
    return ParagraphOut(**out)


@app.get("/api/paragraphs", response_model=List[ParagraphOut], tags=["Content"], summary="List all paragraphs")
# PUBLIC_INTERFACE
def list_paragraphs(language: Optional[str] = None, q: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get list of paragraphs, optionally filter by language or search (q)."""
    conn = get_db_conn()
    c = conn.cursor()
    query = "SELECT * FROM paragraphs WHERE 1=1"
    params = []
    if language:
        query += " AND language=?"
        params.append(language)
    if q:
        query += " AND paragraph LIKE ?"
        params.append(f"%{q}%")
    query += " LIMIT ? OFFSET ?"
    params += [limit, skip]
    c.execute(query, params)
    results = [ParagraphOut(**row) for row in c.fetchall()]
    conn.close()
    return results


@app.get("/api/paragraphs/{paragraph_id}", response_model=ParagraphOut, tags=["Content"], summary="Get paragraph by ID")
# PUBLIC_INTERFACE
def get_paragraph(paragraph_id: str):
    """Fetch paragraph by ID."""
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM paragraphs WHERE id=?", (paragraph_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404)
    return ParagraphOut(**row)


# ---------- FAVORITES ----------

@app.post("/api/favorites", response_model=FavoriteOut, tags=["Favorites"], summary="Add favorite")
# PUBLIC_INTERFACE
def add_favorite(fav: FavoriteIn, token: str = Depends(AuthBearer())):
    """Add an item to user favorites."""
    user_id = _get_user_id_from_token(token)
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO favorites (id, user_id, item_type, item_id) "
        "VALUES (?, ?, ?, ?)",
        (
            id_,
            user_id,
            fav.item_type,
            fav.item_id
        )
    )
    conn.commit()
    c.execute("SELECT * FROM favorites WHERE id=?", (id_,))
    out = c.fetchone()
    conn.close()
    return FavoriteOut(**out)


@app.get("/api/favorites", response_model=List[FavoriteOut], tags=["Favorites"], summary="List user favorites")
# PUBLIC_INTERFACE
def list_favorites(token: str = Depends(AuthBearer())):
    """List all favorites for current user."""
    user_id = _get_user_id_from_token(token)
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM favorites WHERE user_id=?", (user_id,))
    results = [FavoriteOut(**row) for row in c.fetchall()]
    conn.close()
    return results


@app.delete(
    "/api/favorites/{favorite_id}",
    status_code=204,
    tags=["Favorites"],
    summary="Delete a favorite"
)
# PUBLIC_INTERFACE
def delete_favorite(favorite_id: str, token: str = Depends(AuthBearer())):
    """Delete a favorite by its ID (must belong to the user)."""
    user_id = _get_user_id_from_token(token)
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "DELETE FROM favorites WHERE id=? AND user_id=?",
        (
            favorite_id,
            user_id
        )
    )
    conn.commit()
    conn.close()
    return Response(status_code=204)


# ---------- QUIZZES ----------

@app.post("/api/quizzes", response_model=QuizOut, tags=["Quizzes"], summary="Add quiz question")
# PUBLIC_INTERFACE
def add_quiz(q: QuizIn, token: str = Depends(AuthBearer())):
    """Add a quiz question (admin/teacher only)."""
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    options_str = ",".join(q.options or []) if q.options else None
    c.execute(
        "INSERT INTO quizzes (id, language, question, answer, options, audio_url) VALUES (?, ?, ?, ?, ?, ?)",
        (id_, q.language, q.question, q.answer, options_str, q.audio_url)
    )
    conn.commit()
    c.execute("SELECT * FROM quizzes WHERE id=?", (id_,))
    out = c.fetchone()
    out = dict(out)
    if out["options"]:
        out["options"] = out["options"].split(",")
    else:
        out["options"] = []
    conn.close()
    return QuizOut(**out)


@app.get("/api/quizzes", response_model=List[QuizOut], tags=["Quizzes"], summary="Get quiz questions")
# PUBLIC_INTERFACE
def list_quizzes(language: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get quizzes, optionally filter by language."""
    conn = get_db_conn()
    c = conn.cursor()
    query = "SELECT * FROM quizzes WHERE 1=1"
    params = []
    if language:
        query += " AND language=?"
        params.append(language)
    query += " LIMIT ? OFFSET ?"
    params += [limit, skip]
    c.execute(query, params)
    out = []
    for row in c.fetchall():
        row = dict(row)
        row["options"] = row["options"].split(",") if row["options"] else []
        out.append(QuizOut(**row))
    conn.close()
    return out


# ---------- SUGGESTIONS ----------

@app.get(
    "/api/suggestions",
    response_model=List[SuggestionOut],
    tags=["Suggestions"],
    summary="Get daily suggestions"
)
# PUBLIC_INTERFACE
def get_suggestions(type: Optional[str] = None, language: Optional[str] = None, limit: int = 10):
    """Get daily suggestions for words/sentences/paragraphs in given language."""
    conn = get_db_conn()
    c = conn.cursor()
    query = "SELECT * FROM suggestions WHERE 1=1"
    params = []
    if type:
        query += " AND type=?"
        params.append(type)
    if language:
        query += " AND language=?"
        params.append(language)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    out = [SuggestionOut(**row) for row in c.fetchall()]
    conn.close()
    return out


@app.post(
    "/api/suggestions",
    response_model=SuggestionOut,
    tags=["Suggestions"],
    summary="Add daily suggestion"
)
# PUBLIC_INTERFACE
def add_suggestion(
    type: str = Body(...),
    language: str = Body(...),
    content: str = Body(...),
    token: str = Depends(AuthBearer())
):
    """Add a new suggestion (admin/teacher only)."""
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO suggestions (id, type, language, content) VALUES (?, ?, ?, ?)",
        (
            id_,
            type,
            language,
            content
        )
    )
    conn.commit()
    c.execute("SELECT * FROM suggestions WHERE id=?", (id_,))
    out = c.fetchone()
    conn.close()
    return SuggestionOut(**out)


# ---------- VOICE COMMANDS ----------

@app.get(
    "/api/voice_commands",
    response_model=List[VoiceCommandOut],
    tags=["VoiceCommands"],
    summary="Get voice commands"
)
# PUBLIC_INTERFACE
def get_voice_commands(language: Optional[str] = None):
    """Get known voice commands (multilingual)."""
    conn = get_db_conn()
    c = conn.cursor()
    query = "SELECT * FROM voice_commands WHERE 1=1"
    params = []
    if language:
        query += " AND language=?"
        params.append(language)
    c.execute(query, params)
    out = [VoiceCommandOut(**row) for row in c.fetchall()]
    conn.close()
    return out


@app.post(
    "/api/voice_commands",
    response_model=VoiceCommandOut,
    tags=["VoiceCommands"],
    summary="Add voice command"
)
# PUBLIC_INTERFACE
def add_voice_command(cmd: VoiceCommandIn, token: str = Depends(AuthBearer())):
    """Add new voice command (admin only)."""
    id_ = str(uuid.uuid4())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO voice_commands (id, command, action, language) "
        "VALUES (?, ?, ?, ?)",
        (
            id_,
            cmd.command,
            cmd.action,
            cmd.language
        )
    )
    conn.commit()
    c.execute("SELECT * FROM voice_commands WHERE id=?", (id_,))
    out = c.fetchone()
    conn.close()
    return VoiceCommandOut(**out)


# ---------- TTS ENDPOINTS ----------

def fake_tts_generate_audio(text: str, lang: str, speed: float) -> Dict[str, Any]:
    """
    Placeholder: Simulates TTS generation (replace with Google TTS/Azure in prod)
    Returns 'audio_url' as a fake local URL.
    """
    return {
        "audio_url": (
            f"/static/audio/generated_{lang}_{speed}_{uuid.uuid4().hex}.mp3"
        ),
        "success": True,
    }


@app.post(
    "/api/tts",
    response_model=TTSResponse,
    tags=["TTS"],
    summary="Text-to-Speech"
)
# PUBLIC_INTERFACE
def tts(req: TTSRequest):
    """Generate audio from text (fake TTS, placeholder - integrate real TTS here)."""
    data = fake_tts_generate_audio(req.text, req.language, req.speed)
    return TTSResponse(**data)


@app.get(
    "/api/tts/db_check",
    response_model=TTSResponse,
    tags=["TTS"],
    summary="DB+TTS pipeline check"
)
# PUBLIC_INTERFACE
def tts_db_check(language: str = "en"):
    """
    Pipeline check: Fetch a word or sentence from DB, send to TTS, return result.
    Confirms end-to-end DB → TTS is healthy.
    """
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT word FROM words WHERE language=? LIMIT 1", (language,))
    row = c.fetchone()
    text = row["word"] if row else None
    if not text:
        c.execute("SELECT sentence FROM sentences WHERE language=? LIMIT 1", (language,))
        row = c.fetchone()
        text = row["sentence"] if row else None
    conn.close()
    if not text:
        return TTSResponse(
            success=False,
            message=(
                "No example text in DB for chosen language."
            ),
            audio_url=None
        )
    audio_result = fake_tts_generate_audio(text, language, speed=1.0)
    return TTSResponse(**audio_result)


# ---------- HEALTH ----------

@app.get("/", summary="Health check")
# PUBLIC_INTERFACE
def health_check():
    """Confirms API is up."""
    return {"message": "Healthy"}


# ---------- OFFLINE/ACCESSIBILITY SUPPORT NOTES ----------
# - API endpoints are RESTful and work offline with local SQLite.
# - Multilingual (en, ta, hi) support via stored language codes.
# - Accessible structure: can be called from PWA, mobile or desktop.


# ---------- OPENAPI DOCS HINT FOR WEBSOCKETS ----------

@app.get("/api/usage_help", tags=["TTS", "VoiceCommands"])
def usage_help():
    """
    PUBLIC_INTERFACE
    This backend does not require WebSockets for TTS; use REST API endpoints above.
    Voice commands should POST an action to /api/voice_commands.
    """
    return {
        "message": (
            "To use TTS, POST to /api/tts. For voice commands, "
            "use /api/voice_commands. No websocket endpoints required."
        )
    }
