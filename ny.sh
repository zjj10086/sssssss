#!/bin/bash

echo "🚀 开始执行一键安装脚本..."

####################################
# 第一部分：安装 Cloudflare DDNS
####################################

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

echo "✅ Cloudflare IPv6 DDNS 已安装完成！"
echo "📅 已设置每分钟自动运行 /root/1.sh"
echo "🧾 当前定时任务如下："
crontab -l

####################################
# 第二部分：安装 nyanpass 节点
####################################

echo "🚀 开始安装 nyanpass 节点..."
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link"
echo -e "nuan\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t 7a510a72-8f0e-45a6-8937-42c1c545ff9c -u https://materelay.com"
echo "✅ nyanpass 节点安装完成！"

####################################
# 第三部分：安装哪吒探针代理
####################################

echo "🚀 开始安装哪吒探针代理..."
curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/install.sh -o nezha.sh && chmod +x nezha.sh
./nezha.sh install_agent 23.94.83.24 5555 oer1NSgoX8i6DRmgW0
echo "✅ 哪吒探针代理安装完成！"

####################################
# 最后输出
####################################

echo ""
echo "🎉 所有任务已完成！"
echo "✅ Cloudflare DDNS 已自动运行"
echo "✅ nyanpass 节点部署完成"
echo "✅ 哪吒探针已连接"
echo ""
echo "📜 日志文件：/root/1.log"
echo "🕒 定时任务：每分钟自动执行 /root/1.sh"
