from telethon import events
from asyncio import sleep, create_task
from .. import loader, utils
import aiohttp
import asyncio

@loader.tds
class InsTrans(loader.Module):
    """Переводчик от @InsModule"""
    strings = {
        'name': 'InsTrans',
        'no_text': 'Нет текста для перевода',
        'unsupported_lang': 'Язык <code>{lang}</code> не поддерживается',
        'error': 'Ошибка перевода',
        'server_error': 'Сервер не отвечает'
    }
    strings_ru = {
        'no_text': 'Нет текста для перевода',
        'unsupported_lang': 'Язык <code>{lang}</code> не поддерживается',
        'error': 'Ошибка перевода',
        'server_error': 'Сервер не отвечает'
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            "DEFAULT_LANG", "RU", 
            lambda: "Язык по умолчанию (RU, EN, DE, FR, ES, IT, JA, ZH, UK, AR, PT, KO, TR, PL, NL, HI, ID, VI, TH)"
        )
        self.session = None
        self.supported_langs = {
            'RU': 'ru', 'EN': 'en', 'DE': 'de', 'FR': 'fr', 'ES': 'es',
            'IT': 'it', 'JA': 'ja', 'ZH': 'zh', 'UK': 'uk', 'AR': 'ar',
            'PT': 'pt', 'KO': 'ko', 'TR': 'tr', 'PL': 'pl', 'NL': 'nl',
            'HI': 'hi', 'ID': 'id', 'VI': 'vi', 'TH': 'th'
        }

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self.session = aiohttp.ClientSession()
        if self.config["DEFAULT_LANG"].upper() not in self.supported_langs:
            self.config["DEFAULT_LANG"] = "RU"

    async def on_unload(self):
        if self.session:
            await self.session.close()

    async def translate_text(self, text: str, target_lang: str) -> str:
        """Функция перевода"""
        if not text or not target_lang:
            return None
            
        try:
            url = 'https://translate.googleapis.com/translate_a/single'
            params = {
                'client': 'gtx',
                'sl': 'auto',
                'tl': target_lang,
                'dt': 't',
                'q': text[:5000]  
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(url, params=params, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and data[0]:
                        return ''.join([chunk[0] for chunk in data[0] if chunk[0]])
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None
        except Exception:
            return None

    @loader.command()
    async def t(self, message):
        """[язык?] [текст/реплай] - перевод с удалением команды"""
        try:
            args = utils.get_args_raw(message)
            reply = await message.get_reply_message()
            
            
            await message.delete()
            
            
            text = ''
            if reply and (reply.text or reply.caption):
                text = reply.text or reply.caption
            
            target_lang = self.config["DEFAULT_LANG"].upper()
            
            if args:
                if not text:  
                    text = args
                else:  
                    potential_lang = args.strip().upper()
                    if potential_lang in self.supported_langs:
                        target_lang = potential_lang
            
            
            if args and not reply:
                parts = args.split(maxsplit=1)
                if len(parts) > 0 and parts[0].upper() in self.supported_langs:
                    target_lang = parts[0].upper()
                    text = parts[1] if len(parts) > 1 else ''
            
            
            if not text:
                error_msg = await utils.answer(message, self.strings('no_text'))
                await asyncio.sleep(3)
                await error_msg.delete()
                return
            
            
            lang_code = self.supported_langs.get(target_lang)
            if not lang_code:
                error_msg = await utils.answer(
                    message, 
                    self.strings('unsupported_lang').format(lang=target_lang)
                )
                await asyncio.sleep(3)
                await error_msg.delete()
                return
            
            
            result = await self.translate_text(text, lang_code)
            
            if not result:
                error_msg = await utils.answer(message, self.strings('error'))
                await asyncio.sleep(3)
                await error_msg.delete()
                return
            
            
            await message.reply(
                f"{result}",
                parse_mode='html'
            )
            
        except Exception as e:
            pass

    @loader.command()
    async def tlang(self, message):
        """[язык] - установить язык по умолчанию"""
        args = utils.get_args_raw(message)
        
        if not args:
            langs = ', '.join(self.supported_langs.keys())
            await utils.answer(
                message,
                f"Текущий язык: <b>{self.config['DEFAULT_LANG']}</b>\n"
                f"Поддерживаемые языки: {langs}"
            )
            return
        
        lang = args.strip().upper()
        
        if lang not in self.supported_langs:
            await utils.answer(
                message,
                f"Язык <code>{lang}</code> не поддерживается\n"
                f"Доступные: {', '.join(self.supported_langs.keys())}"
            )
            return
        
        self.config["DEFAULT_LANG"] = lang
        await utils.answer(
            message,
            f"Язык по умолчанию <b>{lang}</b>"
        )