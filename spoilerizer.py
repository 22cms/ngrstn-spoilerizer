import json
import time
from telethon.extensions import markdown
from telethon import TelegramClient, events, types

# Load Config from config.json
with open("config.json", "r") as f:
    config = json.load(f)


# Bot commands

async def start(event):
    await event.reply("Hello! I am a Spoiler Bot. Reply to any message with /spoilerize to resend it as a spoiler.")

async def sourcecode(event):    
    await event.reply("https://github.com/22cms/ngrstn-spoilerizer")

async def spoilerize_message(event):
    message_to_delete = await event.get_reply_message()
    if not message_to_delete:
        await event.reply('Reply to a message to spoilerize it')
        return
    
    event.client.parse_mode = SpoilerParser
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
        await event.client.send_message(entity=event.chat_id, message=text)
    else:
        await event.client.send_file(
            entity=event.chat_id, 
            file=files if len(files) > 1 else files[0], 
            caption=text
            )

    try:
        await event.message.delete()
        for message in message_list:
            await message.delete()
    except Exception as e:
        await event.reply(f"Failed to delete messages: make sure the bot has the required admin rights.\n\n{e}")


# Helper Functions 'n Classes

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
        self.emojis = {
            "user": "\U0001F464",
            "bot": "\U0001F916",
            "channel": "\U0001F4E2",
            "incognito": "\U0001F575\U0000FE0F",
            "unknown": "\U00002754"
        }

    def _clickable(self, sender):
                return f"@{sender.username}" if getattr(sender, "username", None) else f"[{sender.first_name}](tg://user?id={sender.id})"
        
    def parse_user(self):
        try:
            if self.sender != None: 
                #If there is a sender, it might be a lot of stuff: a user, a bot or a channel to name a few
                if isinstance(self.sender, types.User): 
                    # If it's a user, also happens to work with bots
                    emoji = self.emojis['user'] if not self.sender.bot else self.emojis['bot']
                    return f"{emoji} {self._clickable(self.sender)}"
                
                elif isinstance(self.sender, types.Channel): 
                    emoji = self.emojis['channel']
                    #if it's a channel sender
                    post_author = None
                    if getattr(self.message, "fwd_from", None):
                        post_author = self.message.fwd_from.post_author
                    elif getattr(self.message, "post_author", None):
                        post_author = self.message.post_author
                    post_credits = f"({post_author})" if post_author else ""
                    return f'{emoji} [{self.sender.title}](https://t.me/c/{self.sender.id}) {post_credits}' if self.sender.username is None else f"{emoji} {self._clickable(self.sender)} {post_credits}"
                else:
                    # Fallback
                    return f"{self.emojis['unknown']} Unknown user type"

            elif isinstance(self.message.peer_id, types.PeerChannel): 
                # If there is no sender. but the peer_id looks like a channel's, it's an anonymous admin (???)
                emoji = self.emojis['incognito']
                return f"{emoji} {self.message.post_author} (anonymous admin)" if self.message.post_author else f"{emoji} Anonymous admin"

            else: 
                # i have no idea tbh
                return f"{self.emojis['unknown']} Unknown user"
            
        except Exception as e:
            print(e)
            return f"{self.emojis['unknown']} Unknown user"
    def is_forward(self):
        return self.forward and (self.forward.sender is None or self.forward.sender.id != self.sender.id)

    def parse_forward(self):
        try:
            if self.forward:
                if self.forward.sender:  
                    # If the sender is known, it might be a known user or bot
                    emoji = self.emojis['user'] if not self.forward.sender.bot else self.emojis['bot']
                    return f"{emoji} {self._clickable(self.forward.sender)}"
                elif self.forward.chat is not None:
                    emoji = self.emojis['channel'] if isinstance(self.forward.chat, types.Channel) and self.forward.chat.megagroup is False else self.emojis['incognito']
                    #If it's not known, it might be a channel or an anonymous admin forward
                    channel_post = self.forward.channel_post or ""
                    post_credits = ""
                    if getattr(self.forward, "post_author", None):
                        post_credits = f"({self.forward.post_author})"
                    chat_title = f"@{self.forward.chat.username}" if getattr(self.forward.chat, "username", None) else self.forward.chat.title
                    return f'{emoji} [{chat_title}](https://t.me/c/{self.forward.chat.id}/{channel_post}) {post_credits}'

                else:
                    # Last check: anonymous user forward or just unknown
                    return f"{self.emojis['incognito']} {getattr(self.message.forward, 'from_name', None)}" or f"{self.emojis['unknown']} Unknown forward"
            else:
                return f"{self.emojis['unknown']} Unknown forward"
        except Exception as e:
            print(e)
            return f"{self.emojis['unknown']} Unknown forward"
        

# Main Loop to keep the bot running
while True:
    try:
        client = TelegramClient('spoiler_bot_client', config['api_id'], config['api_hash']).start(bot_token=config['bot_token'])

        # Command Handling
        client.on(events.NewMessage(pattern="/start"))(start)
        client.on(events.NewMessage(pattern="/sourcecode"))(sourcecode)
        client.on(events.NewMessage(pattern="/spoilerize"))(spoilerize_message)
        
        # Start the bot     
        print("Bot is running...")  
        client.run_until_disconnected()        


    except Exception as e:
        print(f"Bot disconnected due to an error:\n{e}\nRestarting in 5 seconds...")
        time.sleep(5)