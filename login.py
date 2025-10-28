import os
import asyncio
import aiohttp
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ===================== 配置 =====================
LOGIN_URL = "https://searcade.com/en/admin/servers/3759"

# ===================== Telegram 通知 =====================
async def tg_notify(message: str):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("Warning: 未设置 TG_BOT_TOKEN / TG_CHAT_ID，跳过通知")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
        except Exception as e:
            print(f"Warning: Telegram 消息发送失败: {e}")

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
                    data.add_field("parse_mode", "HTML")
                await session.post(url, data=data)
        except Exception as e:
            print(f"Warning: Telegram 图片发送失败: {e}")
        finally:
            try:
                os.remove(photo_path)
            except:
                pass

# ===================== 单账号登录 =====================
async def login_one(email: str, password: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(60000)

        result = {"email": email, "success": False}

        try:
            print(f"[{email}] 访问后台页面...")
            await page.goto(LOGIN_URL, wait_until="networkidle")

            current_url = page.url
            print(f"[{email}] 当前URL: {current_url}")

            # 如果已经在目标页面，说明已登录
            if "servers/3759" in current_url and "login" not in current_url:
                print(f"[{email}] 已登录！")
                result["success"] = True
                return result

            # 等待登录页加载
            await page.wait_for_selector('button:has-text("Login")', timeout=15000)
            print(f"[{email}] 检测到登录页")

            # 填写表单
            await page.fill('input[type="text"] >> nth=0', email)
            await page.fill('input[type="password"] >> nth=0', password)
            await page.click('button:has-text("Login")')
            print(f"[{email}] 提交登录")

            # 等待跳转回目标页
            await page.wait_for_url("**/servers/3759", timeout=20000)
            print(f"[{email}] 登录成功！")
            result["success"] = True

        except Exception as e:
            screenshot = f"error_{email.replace('@', '_')}.png"
            await page.screenshot(path=screenshot, full_page=True)
            await tg_notify_photo(screenshot, caption=f"<b>Failed: 登录失败</b>\n<code>{email}</code>\n<i>{str(e)}</i>\nURL: {page.url}")
            print(f"[{email}] 登录失败: {e}")
        finally:
            await context.close()
            await browser.close()
            return result

# ===================== 主流程 =====================
async def main():
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"登录任务开始: {start_time}")

    # 从环境变量读取账号
    accounts_str = os.getenv("LOGIN_ACCOUNTS")
    if not accounts_str:
        msg = f"<b>Failed: 登录任务失败</b>\n未配置任何账号\n开始时间: {start_time}"
        await tg_notify(msg)
        print(msg)
        return

    accounts = [a.strip() for a in accounts_str.split(",") if ":" in a]
    if not accounts:
        msg = f"<b>Failed: LOGIN_ACCOUNTS 格式错误</b>\n应为 email:password,email2:password2\n开始时间: {start_time}"
        await tg_notify(msg)
        print(msg)
        return

    # 并发登录
    tasks = []
    for acc in accounts:
        email, pwd = acc.split(":", 1)
        tasks.append(login_one(email, pwd))

    results = await asyncio.gather(*tasks, return_exceptions=False)

    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 构建消息
    msg_lines = [
        "<b>Login Task Completed</b>",
        f"开始时间: <code>{start_time}</code>",
        f"结束时间: <code>{end_time}</code>",
        f"总账号: <b>{len(results)}</b>",
        f"成功: <b>{success_count}</b>",
        f"失败: <b>{fail_count}</b>",
        "",
        "<b>详细结果：</b>"
    ]
    for r in results:
        status = "Success" if r["success"] else "Failed"
        msg_lines.append(f"<code>{r['email']}</code>: {status}")

    final_msg = "\n".join(msg_lines)
    await tg_notify(final_msg)
    print(final_msg)

# ===================== 启动 =====================
if __name__ == "__main__":
    asyncio.run(main())
