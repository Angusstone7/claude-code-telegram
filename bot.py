import os
import asyncio
import logging
import shlex
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from anthropic import AsyncAnthropic

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# КОНФИГУРАЦИЯ
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))
HOST_USER = os.getenv("HOST_USER", "root")
SSH_KEY_PATH = "/app/bot_key"
HOST_ADDRESS = "host.docker.internal"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# Хранилище истории и команд
user_histories = {}
pending_commands = {}

# Инструменты
tools = [
    {
        "name": "bash",
        "description": "Выполнить bash-команду на ХОСТ-СЕРВЕРЕ. У тебя есть полный доступ. Можно читать файлы, ставить пакеты, работать с docker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Команда bash"}
            },
            "required": ["command"]
        }
    }
]

SYSTEM_PROMPT = f"""Ты — интеллектуальный агент DevOps, управляющий сервером через Telegram.
Ты работаешь внутри Docker-контейнера, но выполняешь команды на ХОСТ-машине через SSH.
Твой пользователь: {HOST_USER}.
Среда: Ubuntu Linux.

ПРАВИЛА:
1. Если команда может быть опасной (rm -rf, форматирование диска), переспроси дважды.
2. Всегда анализируй вывод команд. Если вывод пустой, сообщи об этом.
3. Если вывод слишком длинный, покажи последние 20 строк или попроси использовать grep.
"""

async def execute_ssh_command(command):
    """Выполняет команду на хосте через SSH из контейнера"""
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no", # Не спрашивать подтверждение хоста
        "-i", SSH_KEY_PATH,
        f"{HOST_USER}@{HOST_ADDRESS}",
        command
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        output = stdout.decode().strip()
        error = stderr.decode().strip()

        full_output = ""
        if output:
            full_output += f"{output}"
        if error:
            full_output += f"\n[STDERR]: {error}"

        if not full_output:
            full_output = "(Команда выполнена успешно, вывода нет)"

        return full_output
    except Exception as e:
        return f"SSH Execution Error: {str(e)}"

async def chat_with_claude(chat_id, user_input=None, tool_outputs=None):
    history = user_histories.get(chat_id, [])

    if user_input:
        history.append({"role": "user", "content": user_input})
    if tool_outputs:
        history.append({"role": "user", "content": tool_outputs})

    try:
        await bot.send_chat_action(chat_id, "typing")
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=history,
            tools=tools
        )
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Ошибка Claude API: {e}")
        return

    assistant_msg = {"role": response.role, "content": response.content}
    history.append(assistant_msg)
    user_histories[chat_id] = history

    for block in response.content:
        if block.type == 'text':
            # Разбиваем длинные сообщения, если нужно
            if len(block.text) > 4000:
                 await bot.send_message(chat_id, block.text[:4000] + "...")
            else:
                 await bot.send_message(chat_id, block.text)

        elif block.type == 'tool_use':
            if block.name == 'bash':
                cmd = block.input['command']
                tool_id = block.id

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Run", callback_data=f"run:{tool_id}"),
                        InlineKeyboardButton(text="❌ Stop", callback_data=f"cancel:{tool_id}")
                    ]
                ])

                pending_commands[tool_id] = cmd
                await bot.send_message(
                    chat_id,
                    f"⚙️ **SSH Command:**\n`{cmd}`",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ALLOWED_USER_ID:
        return
    user_histories[message.chat.id] = []
    await message.answer(f"🤖 Claude DevOps (Dockerized) готов.\nУправление пользователем: {HOST_USER}")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_histories[message.chat.id] = []
    await message.answer("🧹 История диалога очищена.")

@dp.message()
async def handle_text(message: types.Message):
    if message.from_user.id != ALLOWED_USER_ID:
        return
    await chat_with_claude(message.chat.id, user_input=message.text)

@dp.callback_query(F.data.startswith("run:"))
async def process_run(callback: types.CallbackQuery):
    tool_id = callback.data.split(":")[1]
    cmd = pending_commands.pop(tool_id, None)

    if not cmd:
        await callback.message.edit_text("⚠️ Команда устарела.")
        return

    await callback.message.edit_text(f"🚀 Executing via SSH...\n`{cmd}`", parse_mode="Markdown")

    # Выполнение
    output = await execute_ssh_command(cmd)

    # Обрезаем вывод для телеграма, если он огромный
    display_output = output
    if len(display_output) > 3000:
        display_output = output[:1000] + "\n... [ОБРЕЗАНО] ...\n" + output[-1000:]

    await callback.message.answer(f"📄 **Result:**\n```\n{display_output}\n```", parse_mode="Markdown")

    tool_result = [{
        "type": "tool_result",
        "tool_use_id": tool_id,
        "content": output
    }]

    await chat_with_claude(callback.message.chat.id, tool_outputs=tool_result)

@dp.callback_query(F.data.startswith("cancel:"))
async def process_cancel(callback: types.CallbackQuery):
    tool_id = callback.data.split(":")[1]
    pending_commands.pop(tool_id, None)
    await callback.message.edit_text("❌ Отменено.")

    tool_result = [{
        "type": "tool_result",
        "tool_use_id": tool_id,
        "content": "User denied execution.",
        "is_error": True
    }]
    await chat_with_claude(callback.message.chat.id, tool_outputs=tool_result)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
