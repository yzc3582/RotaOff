import asyncio
import simcord
from bot import bot

async def main():
    global bot
    async with simcord.run(bot) as simcord_env:
        # 1. 搭建虚拟环境（频道、用户等）
        channel = simcord_env.create_guild().create_text_channel("general")
        user = simcord_env.guild.add_member(simcord_env.create_user("tester"))

        # 2. 触发一个会产生交互组件（如按钮）的指令
        await user.slash(channel, "login qrcode", server_code="cn")
        # await user.slash(channel, "some-command-with-buttons")
        # 或者 await user.send(channel, "!command-with-buttons")

        # 3. 启动 Preview 服务
        # port 参数可固定端口，方便反复访问
        async with simcord_env.preview(port=6791,channel=channel,viewers=[user]) as preview:
            print(f"Preview URL: {preview.url}")
            # 4. 程序暂停，等待你在浏览器中完成操作
            await preview.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())