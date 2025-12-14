import os
import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")

# твой айди админа
ADMIN_ID = 5220438670

bot = Bot(token=TOKEN)
dp = Dispatcher()

participants: dict[int, str] = {}
assignments: dict[int, int] = {}  # giver_id -> receiver_id


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🎅 Тайный Санта\n\n"
        "/join — участвовать\n"
        "Админ-команды:\n"
        "/draw — жеребьёвка\n"
        "/participants — список участников\n"
        "/results — результаты (кто кому)\n"
        "/reset — сброс жеребьёвки"
    )


@dp.message(Command("join"))
async def join(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.full_name

    participants[user_id] = name
    await message.answer(f"✅ {name}, ты участвуешь!")


@dp.message(Command("participants"))
async def participants_list(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда только для админа.")
        return

    if not participants:
        await message.answer("Пока нет участников.")
        return

    text = "👥 Участники:\n" + "\n".join(
        f"{i+1}. {name} (id: {uid})"
        for i, (uid, name) in enumerate(participants.items())
    )
    await message.answer(text)


@dp.message(Command("draw"))
async def draw(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Жеребьёвку может запускать только админ.")
        return

    if len(participants) < 3:
        await message.answer("❌ Нужно минимум 3 участника.")
        return

    # если уже проводили — не даём повторно (чтобы не путать людей)
    if assignments:
        await message.answer("⚠️ Жеребьёвка уже проведена. Если надо заново — /reset.")
        return

    users = list(participants.keys())
    shuffled = users[:]

    # перемешиваем, пока никто не назначен сам себе
    while True:
        random.shuffle(shuffled)
        if all(u != s for u, s in zip(users, shuffled)):
            break

    # сохраняем результаты
    for giver, receiver in zip(users, shuffled):
        assignments[giver] = receiver

    # рассылаем каждому его подопечного
    for giver, receiver in assignments.items():
        await bot.send_message(
            giver,
            f"🎁 Ты Тайный Санта для: {participants[receiver]}"
        )

    await message.answer("🎉 Жеребьёвка проведена! Участникам разослано в личку.")


@dp.message(Command("results"))
async def results(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда только для админа.")
        return

    if not assignments:
        await message.answer("Пока жеребьёвка не проводилась. Сначала /draw.")
        return

    lines = ["🧾 Результаты (кто кому дарит):"]
    for giver, receiver in assignments.items():
        giver_name = participants.get(giver, str(giver))
        receiver_name = participants.get(receiver, str(receiver))
        lines.append(f"• {giver_name} → {receiver_name}")
    await message.answer("\n".join(lines))


@dp.message(Command("reset"))
async def reset(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда только для админа.")
        return

    assignments.clear()
    await message.answer("🔄 Жеребьёвка сброшена. Можно снова делать /draw.")


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения Render.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
