import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import os
...
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

participants = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🎅 Тайный Санта\n\n"
        "/join — участвовать\n"
        "/draw — провести жеребьёвку"
    )

@dp.message(Command("join"))
async def join(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.full_name
    participants[user_id] = name
    await message.answer(f"✅ {name}, ты участвуешь!")

@dp.message(Command("draw"))
async def draw(message: types.Message):
    if len(participants) < 3:
        await message.answer("❌ Нужно минимум 3 участника")
        return

    users = list(participants.keys())
    shuffled = users[:]

    while True:
        random.shuffle(shuffled)
        if all(u != s for u, s in zip(users, shuffled)):
            break

    for giver, receiver in zip(users, shuffled):
        await bot.send_message(
            giver,
            f"🎁 Ты Тайный Санта для: {participants[receiver]}"
        )

    await message.answer("🎉 Жеребьёвка проведена!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

