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
        browser = await p.chromium.launch(headless=False)  # 先改成 False 看效果！
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(60000)

        result = {"email": email, "success": False}
        debug_html = f"debug_html_{email.replace('@', '_')}.html"
        debug_screenshot = f"debug_screen_{email.replace('@', '_')}.png"

        try:
            print(f"[{email}] 打开页面...")
            await page.goto(LOGIN_URL, wait_until="networkidle")

            # ===== 关键：保存 HTML 和截图用于调试 =====
            html_content = await page.content()
            with open(debug_html, "w", encoding="utf-8") as f:
                f.write(html_content)
            await page.screenshot(path=debug_screenshot, full_page=True)
            await tg_notify_photo(debug_screenshot, caption=f"<b>Debug: 页面已加载</b>\n<code>{email}</code>\n<i>检查 HTML 是否包含登录表单</i>")

            # 打印页面中所有包含 "email" 或 "username" 的文本
            text_elements = await page.locator('*:has-text("email"), *:has-text("username"), *:has-text("Email"), *:has-text("User")').all()
            print(f"[{email}] 找到 {len(text_elements)} 个可能的相关文本：")
            for el in text_elements[:10]:
                text = await el.text_content()
                print(f"  → {text.strip()[:100]}")

            # ===== 尝试多种选择器（容错）=====
            email_selectors = [
                'text=Email address or username >> input',
                'text=Email or username >> input',
                'text=Email >> input',
                'text=Username >> input',
                'input[placeholder*="email" i]',     # 忽略大小写
                'input[placeholder*="user" i]',
                'input[name*="email" i]',
                'input[name*="user" i]',
                'input[name*="login" i]',
                'input[type="text"]',
                'input[type="email"]',
            ]

            email_selector = None
            for sel in email_selectors:
                try:
                    if await page.locator(sel).is_visible(timeout=5000):
                        email_selector = sel
                        print(f"[{email}] 使用选择器成功: {sel}")
                        break
                except:
                    continue

            if not email_selector:
                raise Exception(f"所有邮箱选择器都失败！\n已保存 HTML: {debug_html}\n请手动检查")

            await page.fill(email_selector, email)
            print(f"[{email}] 邮箱填写完成")

            # 密码同理
            pwd_selectors = [
                'text=Password >> input',
                'input[type="password"]',
                'input[name*="pass" i]',
            ]
            pwd_selector = None
            for sel in pwd_selectors:
                if await page.locator(sel).is_visible(timeout=3000):
                    pwd_selector = sel
                    break
            if not pwd_selector:
                raise Exception("未找到密码输入框")
            await page.fill(pwd_selector, password)

            # 登录按钮
            await page.click('button:has-text("Login")', timeout=10000)

            # 等待结果
            await page.wait_for_url("**dashboard**", timeout=15000)
            result["success"] = True

        except Exception as e:
            error_msg = str(e)
            await page.screenshot(path=f"error_{email.replace('@', '_')}.png", full_page=True)
            await tg_notify_photo(f"error_{email.replace('@', '_')}.png",
                                caption=f"<b>Failed: 登录失败</b>\n<code>{email}</code>\n<i>{error_msg}</i>\n<a href='file://{os.path.abspath(debug_html)}'>查看HTML</a>")
            print(f"[{email}] 出错: {error_msg}")
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
