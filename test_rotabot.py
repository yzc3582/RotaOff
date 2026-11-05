# test_rotabot.py
import discord

async def test_bot_responds_to_ping(simcord_env):
    # 1. 创建一个虚拟服务器和频道
    guild = simcord_env.create_guild()
    channel = guild.create_text_channel("general")
    
    # 2. 创建一个虚拟用户
    alice = simcord_env.create_user("Alice")
    member = guild.add_member(alice)
    
    # 3. 模拟用户发送消息
    await member.send(channel, "!ping")  # 如果你的 RotaBot 使用前缀命令
    
    # 4. 断言：检查 Bot 最后发的消息内容
    assert channel.last_message.content == "Pong!"  # 根据你的 Bot 实际回复调整