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
        # 启动无头浏览器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(60000)  # 60秒全局超时

        result = {"email": email, "success": False}
        screenshot_path = None

        try:
            print(f"[{email}] 正在打开登录页...")
            await page.goto(LOGIN_URL, wait_until="networkidle")
            await page.wait_for_load_state("domcontentloaded")

            # ===== 邮箱输入：text=标签 >> input =====
            email_selector = 'text=Email address or username >> input'
            try:
                await page.wait_for_selector(email_selector, state="visible", timeout=15000)
                await page.fill(email_selector, email)
                print(f"[{email}] 邮箱填写成功")
            except PlaywrightTimeoutError:
                raise Exception("未找到邮箱输入框（text=Email address or username >> input）")

            # ===== 密码输入 =====
            password_selector = 'text=Password >> input'
            try:
                await page.wait_for_selector(password_selector, state="visible", timeout=10000)
                await page.fill(password_selector, password)
                print(f"[{email}] 密码填写成功")
            except PlaywrightTimeoutError:
                raise Exception("未找到密码输入框（text=Password >> input）")

            # ===== 点击登录按钮 =====
            login_btn_selector = 'button:has-text("Login")'
            try:
                await page.wait_for_selector(login_btn_selector, state="visible", timeout=10000)
                await page.click(login_btn_selector)
                print(f"[{email}] 点击登录按钮")
            except PlaywrightTimeoutError:
                raise Exception("未找到登录按钮（button:has-text('Login')）")

            # ===== 等待登录结果 =====
            try:
                await page.wait_for_url("**dashboard**", timeout=15000)
                result["success"] = True
                print(f"[{email}] 登录成功！")
            except:
                try:
                    await page.wait_for_url("**clientarea**", timeout=5000)
                    result["success"] = True
                    print(f"[{email}] 登录成功（clientarea）")
                except:
                    current_url = page.url
                    screenshot_path = f"login_failed_{email.replace('@', '_')}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    await tg_notify_photo(screenshot_path,
                                        caption=f"<b>Failed: 登录失败</b>\n"
                                                f"<code>{email}</code>\n"
                                                f"URL: {current_url}")
                    print(f"[{email}] 登录失败，当前URL: {current_url}")

        except Exception as e:
            error_msg = str(e)
            screenshot_path = f"error_{email.replace('@', '_')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            await tg_notify_photo(screenshot_path,
                                caption=f"<b>Warning: 登录出错</b>\n"
                                        f"<code>{email}</code>\n"
                                        f"<i>{error_msg}</i>")
            print(f"[{email}] 登录出错: {error_msg}")

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
