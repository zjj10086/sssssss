#!/bin/bash

# 更新系统与安装 cron
apt update -y
apt install -y cron

# 启用并启动 cron 服务
systemctl enable cron
systemctl start cron

# 下载 DDNS 主脚本
curl -fsSL https://raw.githubusercontent.com/zjj10086/sssssss/refs/heads/main/1.sh -o /root/1.sh
chmod +x /root/1.sh

# 设置定时任务（每分钟执行一次）
(crontab -l 2>/dev/null | grep -v "/root/1.sh"; echo "* * * * * /root/1.sh >/root/1.log 2>&1") | crontab -

# 重启 cron 服务
systemctl restart cron

# 完成提示
echo "✅ Cloudflare IPv6 DDNS 已安装完成！"
echo "📅 已设置每分钟自动运行 /root/1.sh"
echo "🧾 当前定时任务："
crontab -l
