# searcade-login-bot

这个项目自动化了 Searcade 登录流程，并且每 8 天通过 Telegram 发送登录结果通知。

## 使用方法

### 1. 配置 `.env` 文件

在项目根目录下创建一个 `.env` 文件，内容如下：

```env
TG_BOT_TOKEN=你的Telegram机器人Token
TG_CHAT_ID=你的Telegram聊天ID
LOGIN_ACCOUNTS=email1:password1,email2:password2
