from telethon import events
from asyncio import sleep, create_task
from .. import loader, utils
import aiohttp
import asyncio

@loader.tds
class InsTrans(loader.Module):
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
        self._semaphore = asyncio.Semaphore(3)
        self._session_timeout = aiohttp.ClientTimeout(
            total=10,
            connect=5,
            sock_read=7
        )

    async def client_ready(self, client, db):
        self._client = client
        self._db = db
        self.session = aiohttp.ClientSession(
            timeout=self._session_timeout,
            connector=aiohttp.TCPConnector(
                limit=20,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
        )
        if self.config["DEFAULT_LANG"].upper() not in self.supported_langs:
            self.config["DEFAULT_LANG"] = "RU"

    async def on_unload(self):
        if self.session:
            await self.session.close()

    async def _make_request(self, url: str, params: dict) -> dict:
        async with self._semaphore:
            try:
                async with self.session.get(
                    url, 
                    params=params,
                    headers={
                        'Accept': 'application/json',
                        'Accept-Encoding': 'gzip, deflate',
                        'User-Agent': 'Mozilla/5.0 (compatible; GoogleTranslate)'
                    },
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json(content_type=None)
                    return None
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return None
            except Exception:
                return None

    async def translate_text(self, text: str, target_lang: str) -> str:
        if not text or not target_lang:
            return None
        
        if len(text.strip()) == 0:
            return text
            
        try:
            text_to_translate = text[:4000]
            
            url = 'https://translate.googleapis.com/translate_a/single'
            params = {
                'client': 'gtx',
                'sl': 'auto',
                'tl': target_lang,
                'dt': 't',
                'q': text_to_translate,
                'dj': '1'
            }
            
            data = await self._make_request(url, params)
            
            if data and data.get('sentences'):
                result_parts = []
                for sentence in data['sentences']:
                    if 'trans' in sentence:
                        result_parts.append(sentence['trans'])
                return ''.join(result_parts) if result_parts else None
                
            return None
            
        except Exception:
            return None

    @loader.command()
    async def t(self, message):
        """[язык?] [текст/реплай] - перевод"""
        try:
            args = utils.get_args_raw(message)
            reply = await message.get_reply_message()
            
            delete_task = create_task(message.delete())
            
            text = ''
            source_message = reply if reply else None
            
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
                delete_error = create_task(error_msg.delete())
                await asyncio.sleep(2)
                await delete_error
                return
            
            lang_code = self.supported_langs.get(target_lang)
            if not lang_code:
                error_msg = await utils.answer(
                    message, 
                    self.strings('unsupported_lang').format(lang=target_lang)
                )
                delete_error = create_task(error_msg.delete())
                await asyncio.sleep(2)
                await delete_error
                return
            
            translation_task = create_task(self.translate_text(text, lang_code))
            await delete_task
            
            result = await translation_task
            
            if not result:
                return
            
            if source_message:
                await source_message.reply(
                    result,
                    parse_mode='html'
                )
            else:
                await self._client.send_message(
                    message.peer_id,
                    result,
                    parse_mode='html'
                )
            
        except Exception:
            return

    @loader.command()
    async def tl(self, message):
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
