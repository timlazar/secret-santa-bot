import os
import sqlite3
import asyncio
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5220438670

# В Render лучше хранить БД на диске: /var/data/santa.db
DB_PATH = os.getenv("DB_PATH", "santa.db")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ---------- DB ----------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                wish TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                giver_id INTEGER PRIMARY KEY,
                receiver_id INTEGER NOT NULL
            )
        """)


def upsert_participant(user_id: int, name: str):
    with db() as conn:
        conn.execute("""
            INSERT INTO participants (user_id, name)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
        """, (user_id, name))


def set_wish(user_id: int, wish: str):
    with db() as conn:
        conn.execute("UPDATE participants SET wish=? WHERE user_id=?", (wish, user_id))


def get_participants() -> list[tuple[int, str, str]]:
    with db() as conn:
        cur = conn.execute("SELECT user_id, name, COALESCE(wish,'') FROM participants ORDER BY name")
        return cur.fetchall()


def clear_assignments():
    with db() as conn:
        conn.execute("DELETE FROM assignments")


def get_assignments() -> dict[int, int]:
    with db() as conn:
        cur = conn.execute("SELECT giver_id, receiver_id FROM assignments")
        return {row[0]: row[1] for row in cur.fetchall()}


def save_assignments(pairs: dict[int, int]):
    with db() as conn:
        conn.execute("DELETE FROM assignments")
        conn.executemany(
            "INSERT INTO assignments (giver_id, receiver_id) VALUES (?, ?)",
            list(pairs.items())
        )


def get_wish(user_id: int) -> str:
    with db() as conn:
        cur = conn.execute("SELECT COALESCE(wish,'') FROM participants WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else ""


# ---------- UI ----------
BTN_JOIN = "✅ Участвовать"
BTN_WISH = "📝 Пожелание"
BTN_MY_WISH = "👀 Моё пожелание"
BTN_HELP = "ℹ️ Помощь"

BTN_ADMIN_PARTICIPANTS = "👥 Участники (админ)"
BTN_ADMIN_DRAW = "🎲 Провести жеребьёвку (админ)"
BTN_ADMIN_RESULTS = "📋 Результаты (админ)"
BTN_ADMIN_RESET = "🔄 Сброс жеребьёвки (админ)"


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_JOIN)],
        [KeyboardButton(text=BTN_WISH), KeyboardButton(text=BTN_MY_WISH)],
        [KeyboardButton(text=BTN_HELP)],
    ]
    if is_admin(user_id):
        rows += [
            [KeyboardButton(text=BTN_ADMIN_PARTICIPANTS)],
            [KeyboardButton(text=BTN_ADMIN_DRAW)],
            [KeyboardButton(text=BTN_ADMIN_RESULTS), KeyboardButton(text=BTN_ADMIN_RESET)],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, selective=True)


# ---------- FSM ----------
class WishFlow(StatesGroup):
    waiting_wish_text = State()


# ---------- Handlers ----------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🎅 Тайный Санта\n\n"
        "Жми кнопки ниже.\n"
        "Если хочешь участвовать — нажми «Участвовать».",
        reply_markup=main_keyboard(message.from_user.id)
    )


@dp.message(F.text == BTN_HELP)
async def help_btn(message: types.Message):
    await message.answer(
        "Как это работает:\n"
        "1) Нажми «✅ Участвовать»\n"
        "2) При желании добавь «📝 Пожелание»\n"
        "3) Админ запускает жеребьёвку — тебе придёт в личку, кому дарить."
    )


@dp.message(F.text == BTN_JOIN)
async def join_btn(message: types.Message):
    upsert_participant(message.from_user.id, message.from_user.full_name)
    await message.answer("✅ Ты в списке участников!", reply_markup=main_keyboard(message.from_user.id))


@dp.message(F.text == BTN_MY_WISH)
async def my_wish_btn(message: types.Message):
    w = get_wish(message.from_user.id)
    if not w:
        await message.answer("Пока пожелания нет. Нажми «📝 Пожелание» и напиши одним сообщением, что хочешь.")
    else:
        await message.answer(f"📝 Твоё пожелание:\n{w}")


@dp.message(F.text == BTN_WISH)
async def wish_btn(message: types.Message, state: FSMContext):
    # автодобавим в участников, если ещё не добавлен
    upsert_participant(message.from_user.id, message.from_user.full_name)
    await state.set_state(WishFlow.waiting_wish_text)
    await message.answer("Ок. Напиши ОДНИМ сообщением своё пожелание (что любишь/что не надо/лимит и т.п.).")


@dp.message(WishFlow.waiting_wish_text, F.text)
async def wish_text(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 2:
        await message.answer("Слишком коротко. Напиши нормально одним сообщением 🙂")
        return
    if len(text) > 500:
        await message.answer("Слишком длинно. Сократи до ~500 символов.")
        return

    set_wish(message.from_user.id, text)
    await state.clear()
    await message.answer("✅ Пожелание сохранено.", reply_markup=main_keyboard(message.from_user.id))


# ----- Admin buttons -----
@dp.message(F.text == BTN_ADMIN_PARTICIPANTS)
async def admin_participants(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    ppl = get_participants()
    if not ppl:
        await message.answer("Пока нет участников.")
        return

    lines = ["👥 Участники:"]
    for i, (uid, name, wish) in enumerate(ppl, start=1):
        lines.append(f"{i}. {name} (id: {uid})" + (f" — 📝 есть пожелание" if wish else ""))
    await message.answer("\n".join(lines))


@dp.message(F.text == BTN_ADMIN_DRAW)
async def admin_draw(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    ppl = get_participants()
    if len(ppl) < 3:
        await message.answer("❌ Нужно минимум 3 участника.")
        return

    if get_assignments():
        await message.answer("⚠️ Жеребьёвка уже проведена. Если нужно заново — нажми «Сброс жеребьёвки».")
        return

    users = [uid for uid, _, _ in ppl]
    shuffled = users[:]

    while True:
        random.shuffle(shuffled)
        if all(u != s for u, s in zip(users, shuffled)):
            break

    pairs = {giver: receiver for giver, receiver in zip(users, shuffled)}
    save_assignments(pairs)

    # рассылаем каждому
    names = {uid: name for uid, name, _ in ppl}
    for giver, receiver in pairs.items():
        receiver_wish = get_wish(receiver)
        text = f"🎁 Ты Тайный Санта для: {names.get(receiver, receiver)}"
        if receiver_wish:
            text += f"\n\n📝 Пожелание:\n{receiver_wish}"
        await bot.send_message(giver, text)

    await message.answer("🎉 Жеребьёвка проведена! Всем разослано в личку.")


@dp.message(F.text == BTN_ADMIN_RESULTS)
async def admin_results(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    pairs = get_assignments()
    if not pairs:
        await message.answer("Пока результатов нет. Сначала «Провести жеребьёвку».")
        return

    ppl = get_participants()
    names = {uid: name for uid, name, _ in ppl}
    lines = ["📋 Результаты (кто кому дарит):"]
    for giver, receiver in pairs.items():
        lines.append(f"• {names.get(giver, giver)} → {names.get(receiver, receiver)}")
    await message.answer("\n".join(lines))


@dp.message(F.text == BTN_ADMIN_RESET)
async def admin_reset(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    clear_assignments()
    await message.answer("🔄 Жеребьёвка сброшена. Можно проводить заново.")


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Добавь его в Render → Environment Variables.")
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
