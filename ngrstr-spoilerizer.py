from time import time
import json
from telethon.extensions import markdown
from telethon import TelegramClient, events, types

# Load Config from config.json and create client
with open("config.json", "r") as f:
    config = json.load(f)

api_id = config["api_id"]
api_hash = config["api_hash"]
bot_token = config["bot_token"]

client = TelegramClient('spoiler_bot', api_id, api_hash).start(bot_token=bot_token)

#Command Handling
@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.reply("Hello! I am a Spoiler Bot. Reply to any message with /spoilerize to resend it as a spoiler.")


@client.on(events.NewMessage(pattern="/spoilerize"))
async def spoilerize_message(event):
    message_to_delete = await event.get_reply_message()
    if not message_to_delete:
        await event.reply('Reply to a message to spoilerize it')
        return
    
    client.parse_mode = SpoilerParser
    caption = f"[{message_to_delete.text}](spoiler)" if message_to_delete.text else "" # Spoilers the caption if there's any
    parser = UserClickableParser(message_to_delete)

    credits = f" ~ {parser.parse_user()}" 
    if parser.is_forward():
        credits = f" ~ {parser.parse_forward()} \u21aa\ufe0f {parser.parse_user()}" 
    text = f'{caption}\n\n{credits}' 
    
    files = []
    message_list = [message_to_delete]
    if message_to_delete.media:
        message_list = await fetch_album(event) if message_to_delete.grouped_id else message_list
        files = [msg.media for msg in message_list]
        for item in files: item.spoiler = True


    if files == []:
        await event.reply(message=text)
    elif len(files) == 1:
        await event.reply(file=files[0], message=text)
    else:
        await event.client.send_file(
            entity=event.chat_id, 
            reply_to=event.message.id, 
            file=files if len(files) > 1 else files[0], 
            caption=text
            )

    try:
        for message in message_list:
            await message.delete()
    except Exception as e:
        await event.reply(f"Failed to delete message: make sure the bot has the required admin rights.\n\n{e}")

async def fetch_album(event):
    message_list = []
    album = await event.get_reply_message()
    if not album:
        return False

    message_list = await event.client.get_messages(event.chat_id, ids=range(album.id-9, album.id+10))
    message_list = [msg for msg in message_list if msg is not None and msg.grouped_id == album.grouped_id]

    return message_list


class SpoilerParser:
    @staticmethod
    def parse(text):
        text, entities = markdown.parse(text)
        for i, e in enumerate(entities):
            if isinstance(e, types.MessageEntityTextUrl):
                if e.url == 'spoiler':
                    entities[i] = types.MessageEntitySpoiler(e.offset, e.length)
        return text, entities
    @staticmethod
    def unparse(text, entities):
        for i, e in enumerate(entities or []):
            if isinstance(e, types.MessageEntitySpoiler):
                entities[i] = types.MessageEntityTextUrl(e.offset, e.length, 'spoiler')
        return markdown.unparse(text, entities)
    

class UserClickableParser: # Get ready for a stroke on this one
    def __init__(self, message):
        self.message = message
        self.sender = message.sender
        self.forward = message.forward

    def _clickable(self, sender):
        return f"@{sender.username}" if sender.username else f"[{sender.first_name}](tg://user?id={sender.id})"
        
    def parse_user(self):
        if self.sender != None: #If there is a sender, it might be a lot of stuff: a user, a bot or a channel to name a few
            if isinstance(self.sender, types.User): # If it's a user, also happens to work with bots
                return self._clickable(self.sender)
            elif isinstance(self.sender, types.Channel): #if it's a channel
                post_credits = f"({self.message.fwd_from.post_author})" if self.message.fwd_from.post_author else ""
                return f'[{self.sender.title}](https://t.me/c/{self.sender.id}) {post_credits}' if self.sender.username is None else f"{self._clickable(self.sender)} {post_credits}"
            else:
                return "Unknown user type"

        elif isinstance(self.message.peer_id, types.PeerChannel): # If there is no sender. but the peer_id looks like a channel's, it's an anonymous admin (???)
            return f"{self.message.post_author} (anonymous admin)" if self.message.post_author else "Anonymous admin"

        else: # i have no idea tbh
            return "Unknown user"

    def is_forward(self):
        return self.forward and (self.forward.sender is None or self.forward.sender.id != self.sender.id)

    def parse_forward(self):
        if self.forward:
            if self.forward.sender:  # If the sender is known, it might be a known user or bot
                return self._clickable(self.forward.sender)
            elif self.forward.chat is not None: #If it's not known, it might be a channel or an anonymous admin forward
                channel_post = self.forward.channel_post or ""
                return f"[{self.forward.chat.title}](https://t.me/c/{self.forward.chat.id}/{channel_post})"
            else:
                return self.message.forward.from_name or "Unknown forward"
        else:
            return "Unknown forward"
        
print("Bot is running...")
while True:
    try:
        client.run_until_disconnected()
    except Exception as e:
        print(f"Bot disconnected due to an error:\n{e}\nRestarting in 5 seconds...")
        time.sleep(5)