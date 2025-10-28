# searcade-login-bot

这个项目自动化了 Searcade 登录流程，并且每 8 天通过 Telegram 发送登录结果通知。

脚本特点：

- 多账号同时登录  
- GitHub Actions 定时自动执行（例如每 10 天）  
- Telegram 实时通知登录结果  
- 自动截图失败账号页面  
- 并行执行提高效率  

---

## 功能特性

1. **多账号支持**  
   - 使用环境变量配置多个账号：  
     ```
     LOGIN_ACCOUNTS=email1:password1,email2:password2
     ```

2. **定时自动登录**  
   - 可通过 GitHub Actions 定时触发，实现自动周期登录。

3. **Telegram 通知**  
   - 登录成功或失败会发送消息  
   - 自动上传失败账号截图，便于快速排查问题

4. **并行登录**  
   - 使用 `asyncio.gather` 并行处理多个账号，提高登录效率

5. **详细执行统计**  
   - 显示开始/结束时间  
   - 总账号数、成功数、失败数  
   - 每个账号的登录结果  

---

## 环境变量配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `LOGIN_ACCOUNTS` | 多账号信息，用逗号分隔，每个账号 `email:password` | `user1@example.com:pass1,user2@example.com:pass2` |
| `TG_BOT_TOKEN` | Telegram Bot Token，用于发送通知 | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `TG_CHAT_ID` | Telegram 聊天 ID，用于发送通知 | `123456789` |

> 建议通过 GitHub Secrets 配置，保证账号安全。

---
