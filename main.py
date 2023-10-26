from io import BytesIO
import logging, os, json, requests, asyncio

from decouple import config
logging.basicConfig(level=logging.INFO)

from swibots import (
    regexp,
    Client,
    BotContext,
    CallbackQueryEvent,
    CommandEvent,
    InlineMarkup,
    InlineKeyboardButton,
    BotCommand,
    MessageEvent,
)

reactions = ["💖", "👍", "🤩"]

BOT_TOKEN = config("BOT_TOKEN", default="")

app = Client(
    token=BOT_TOKEN
).set_bot_commands(
    [
        BotCommand("start", "Get Start message", True),
        BotCommand("set", "Set buttons format", True),
        BotCommand("get", "Get Example with current settings", True),
        BotCommand("delete", "Remove format", True),
        BotCommand("setchannel", "Setup post channel", True),
        BotCommand("getchannel", "Get post channel", True),
        BotCommand("post", "post message in channel", True),
    ]
)

if os.path.exists("Settings.json"):
    with open("Settings.json", "r") as f:
        Data = json.load(f)
        if not Data.get("messages"):
            Data["messages"] = {}
        if not Data.get("chats"):
            Data["chats"] = {}
else:
    Data = {"messages": {}}


def save():
    with open("Settings.json", "w") as f:
        json.dump(Data, f)


@app.on_command("start")
async def getStartmessage(ctx: BotContext[CommandEvent]):
    await ctx.event.message.reply_text(
        """Hi I am a Button Builder bot!
To set format:

<copy>/set button1-https://url.com | button2-https://url.com
button3-https://url.com</copy>
Note: Enable instant messaging!"""
    )


def SplitText(text):
    split = text.split("-")
    if len(split) != 2:
        return
    return list(map(lambda x: x.strip(), split))


@app.on_command("post")
async def postMessage(ctx: BotContext[CommandEvent]):
    m = ctx.event.message
    chat_id = m.channel_id or m.group_id or str(m.user_id)
    if not Data["chats"].get(chat_id):
        return await m.reply_text("Chat is currently not set!")
    reply = await m.get_replied_message()
    if not reply:
        return await m.reply_text("Reply to a message!")
    try:
        await m.delete()
    except Exception as er:
        pass
    channel_id = Data["chats"][chat_id]
    isGroup = None
    try:
        channel = await app.get_channel(channel_id)
    except Exception:
        channel = await app.get_group(channel_id)
        isGroup = True
    document, description, name = None, None, None
    if reply.is_media:
        minfo = reply.media_info
        document = BytesIO(requests.get(minfo.url).content)
        document.name = minfo.file_name or minfo.description
        description = minfo.description
        name = minfo.caption
    await app.send_message(
        community_id=channel.community_id,
        channel_id=channel_id if not isGroup else None,
        group_id=channel_id if isGroup else None,
        message=reply.message,
        inline_markup=reply.inline_markup,
        document=document,
        description=description,
        caption=name,
        thumb=document,
    )
    nm = await m.reply_text("Done!")
    await asyncio.sleep(3)
    await nm.delete()


@app.on_command("getchannel")
async def getSample(ctx: BotContext[CommandEvent]):
    m = ctx.event.message
    chat_id = m.channel_id or m.group_id or str(m.user_id)
    if not Data["chats"].get(chat_id):
        return await m.reply_text("No Post chat is active!")
    chat = Data["chats"][chat_id]
    try:
        channel = await app.get_channel(chat)
    except Exception:
        channel = await app.get_group(chat)
    await m.reply_text(
        f"Post Channel:\nName: {channel.name} [<copy>{channel.id}</copy>]"
    )


@app.on_command("setchannel")
async def setButtonFormat(ctx: BotContext[CommandEvent]):
    m = ctx.event.message
    try:
        param = m.message.split(maxsplit=1)[1]
    except IndexError:
        param = None
    if not param:
        return await m.reply_text("Provide a Channel ID!")
    chat_id = m.channel_id or m.group_id or str(m.user_id)
    try:
        channel = await app.get_channel(param)
    except Exception as er:
        try:
            channel = await app.get_group(param)
        except Exception:
            return await m.reply_text("Provide a valid channel id!")
    Data["chats"][chat_id] = param
    save()
    await m.reply_text("Saved!")


@app.on_command("get")
async def getSample(ctx: BotContext[CommandEvent]):
    m = ctx.event.message
    chat_id = m.channel_id or m.group_id or str(m.user_id)
    if not Data.get(chat_id):
        return await m.reply_text("Set format first!")
    keyBoard = []
    buttons = Data.get(chat_id)
    for line in buttons:
        part = [InlineKeyboardButton(*button) for button in line]
        keyBoard.append(part)
    await m.reply_text("Hi, This is a message!", inline_markup=InlineMarkup(keyBoard))


@app.on_command("set")
async def setButtonFormat(ctx: BotContext[CommandEvent]):
    m = ctx.event.message
    try:
        param = m.message.split(maxsplit=1)[1]
    except IndexError:
        param = None
    if not param:
        return await m.reply_text("Provide a format!\nCheck /start for details!")
    parse = param.split("\n")
    buttons = []
    #    print(parse)
    for line in parse:
        part = []
        if "|" in line:
            sList = line.split("|")
        else:
            sList = [line]
        for button in sList:
            if data := SplitText(button):
                part.append(data)
        if part:
            buttons.append(part)
    # print(buttons)
    chat_id = m.group_id or m.channel_id or str(m.user_id)
    Data[chat_id] = buttons
    save()
    await m.reply_text("Saved!")


@app.on_callback_query(regexp(r"react_(.*)"))
async def onCallback(ctx: BotContext[CallbackQueryEvent]):
    m = ctx.event.message
    callback = m.callback_data.split("_")
    mId = callback[-1]
    user_id = str(ctx.event.action_by_id)
    if not Data["messages"].get(mId):
        Data["messages"][mId] = {}
    if Data["messages"][mId].get(user_id) == callback[1]:
        del Data["messages"][mId][user_id]
    else:
        Data["messages"][mId][user_id] = callback[1]
    reacts = {x: 0 for x in reactions}
    newRow = []
    for react in Data["messages"][mId].values():
        reacts[react] += 1
    for key, value in reacts.items():
        title = key
        if value:
            title += f" {value}"
        newRow.append(InlineKeyboardButton(title, callback_data=rf"react_{key}_{mId}"))
    buttons = [newRow, *m.inline_markup.inline_keyboard[1:]]
    await m.edit_text(m.message, inline_markup=InlineMarkup(buttons))
    save()


@app.on_message()
async def on_Message(ctx: BotContext[MessageEvent]):
    m = ctx.event.message
    if m.forward:
        return
    try:
        await m.delete()
    except:
        pass
    chat_id = m.group_id or m.channel_id or str(m.user_id)
    if buttons := Data.get(chat_id):
        keyBoard = [
            [
                InlineKeyboardButton(text, callback_data=rf"react_{text}_{m.id}")
                for text in reactions
            ]
        ]
        for line in buttons:
            part = [InlineKeyboardButton(*button) for button in line]
            keyBoard.append(part)
        document, description, name = None, None, None
        if m.is_media:
            minfo = m.media_info
            document = BytesIO(requests.get(minfo.url).content)
            document.name = minfo.file_name or minfo.description
            description = minfo.description
            name = minfo.caption
        await m.send(
            m.message,
            inline_markup=InlineMarkup(keyBoard),
            document=document,
            description=description,
            caption=name,
            thumb=document,
        )


app.run()
