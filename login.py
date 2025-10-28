import os
import asyncio
import aiohttp
from datetime import datetime
from playwright.async_api import async_playwright

LOGIN_URL = "https://searcade.com/en/admin/servers/3759"

# ===================== Telegram 通知 =====================
async def tg_notify(message: str):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ 未设置 TG_BOT_TOKEN / TG_CHAT_ID，跳过通知")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, data={"chat_id": chat_id, "text": message})
        except Exception as e:
            print(f"⚠️ Telegram 消息发送失败: {e}")

async def tg_notify_photo(photo_path: str, caption: str = ""):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    async with aiohttp.ClientSession() as session:
        try:
            with open(photo_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", chat_id)
                data.add_field("photo", f, filename=os.path.basename(photo_path))
                if caption:
                    data.add_field("caption", caption)
                await session.post(url, data=data)
        except Exception as e:
            print(f"⚠️ Telegram 图片发送失败: {e}")

# ===================== 单账号登录 =====================
async def login_one(email, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(60000)
        result = {"email": email, "success": False}

        try:
            await page.goto(LOGIN_URL)

            # ===== 邮箱输入 =====
            email_selector = 'input[placeholder*="Email"], input[name="Email Address"], input[type="Email address or username"]'
            await page.wait_for_selector(email_selector)
            await page.fill(email_selector, email)

            # ===== 密码输入 =====
            await page.fill('input[type="Password"]', password)

            # ===== 登录按钮 =====
            await page.click('button:has-text("Login")')
            await page.wait_for_timeout(5000)

            current_url = page.url
            if "dashboard" in current_url or "clientarea" in current_url:
                result["success"] = True
            else:
                screenshot = f"login_failed_{email.replace('@', '_')}.png"
                await page.screenshot(path=screenshot, full_page=True)
                await tg_notify_photo(screenshot, caption=f"❌ 登录失败: {email}, URL: {current_url}")

        except Exception as e:
            screenshot = f"error_{email.replace('@', '_')}.png"
            await page.screenshot(path=screenshot, full_page=True)
            await tg_notify_photo(screenshot, caption=f"⚠️ 账号 {email} 登录出错: {e}")
        finally:
            await context.close()
            await browser.close()
            return result

# ===================== 主流程 =====================
async def main():
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 从环境变量中获取 LOGIN_ACCOUNTS
    accounts_str = os.getenv("LOGIN_ACCOUNTS")
    if not accounts_str:
        await tg_notify(f"❌ 登录任务失败：未配置任何账号\n开始时间: {start_time}")
        return

    accounts = [a.strip() for a in accounts_str.split(",") if ":" in a]
    if not accounts:
        await tg_notify(f"❌ LOGIN_ACCOUNTS 格式错误，应为 email:password,email2:password2\n开始时间: {start_time}")
        return

    # 并行登录所有账号
    tasks = []
    for acc in accounts:
        email, password = acc.split(":", 1)
        tasks.append(login_one(email, password))

    results = await asyncio.gather(*tasks)

    # 统计成功/失败
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg_lines = [
        f"🕑 登录任务完成",
        f"开始时间: {start_time}",
        f"结束时间: {end_time}",
        f"总账号数: {len(results)}",
        f"成功: {success_count}",
        f"失败: {fail_count}",
        "详细结果:"
    ]
    for r in results:
        status = "✅ 成功" if r["success"] else "❌ 失败"
        msg_lines.append(f"{r['email']}: {status}")

    await tg_notify("\n".join(msg_lines))
    print("\n".join(msg_lines))

if __name__ == "__main__":
    asyncio.run(main())
