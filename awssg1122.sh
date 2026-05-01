#!/bin/bash
set -e

echo "🚀 开始执行 Debian 一键安装脚本..."

# 检查 root
if [ "$(id -u)" != "0" ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    exit 1
fi

# 检查 Debian
if ! grep -qi debian /etc/os-release; then
    echo "❌ 这个脚本只适用于 Debian"
    exit 1
fi

####################################
# 第一部分：基础环境准备
####################################

echo "📦 更新软件包并安装依赖..."
apt update -y
apt install -y curl wget cron ca-certificates

####################################
# 第二部分：安装 nyanpass 节点
####################################

echo "🚀 开始安装 nyanpass 节点..."
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t e2a21023-23fa-4c04-9944-473a51c39286 -u https://ny.qwqa.link"
echo "✅ nyanpass 节点安装命令已执行"

####################################

####################################
# 第四部分：覆盖 /etc/sysctl.conf
####################################

echo "⚙️ 正在覆盖 /etc/sysctl.conf ..."

cat > /etc/sysctl.conf << 'EOF'
fs.file-max = 6815744
net.ipv4.tcp_no_metrics_save=1
net.ipv4.tcp_ecn=0
net.ipv4.tcp_frto=0
net.ipv4.tcp_mtu_probing=0
net.ipv4.tcp_rfc1337=0
net.ipv4.tcp_sack=1
net.ipv4.tcp_fack=1
net.ipv4.tcp_window_scaling=1
net.ipv4.tcp_adv_win_scale=1
net.ipv4.tcp_moderate_rcvbuf=1
net.core.rmem_max=96300000
net.core.wmem_max=96300000
net.ipv4.tcp_rmem=4096 131072 96300000
net.ipv4.tcp_wmem=4096 131072 96300000
net.ipv4.udp_rmem_min=8192
net.ipv4.udp_wmem_min=8192
net.ipv4.ip_forward=1
net.ipv4.conf.all.route_localnet=1
net.ipv4.conf.all.forwarding=1
net.ipv4.conf.default.forwarding=1
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF

echo "🔄 正在应用 sysctl 参数..."
sysctl -p
sysctl --system

####################################
# 第五部分：下载脚本并添加 cron (awssg1 & awssg2)
####################################

# 1. 下载并配置 awssg11.sh
echo "🚀 开始下载 /root/awssg1.sh ..."
curl -fsSL https://raw.githubusercontent.com/zjj10086/sssssss/refs/heads/main/azjx.sh -o /root/awssg11.sh || {
    echo "❌ awssg11.sh 下载失败"
    exit 1
}
chmod +x /root/awssg11.sh

# 2. 下载并配置 awssg22.sh
echo "🚀 开始下载 /root/awssg22.sh ..."
# 请确保下面的 URL 地址正确指向你的 awssg22.sh 源码
curl -fsSL https://raw.githubusercontent.com/zjj10086/sssssss/refs/heads/main/awssg2.sh -o /root/awssg22.sh || {
    echo "❌ awssg22.sh 下载失败"
    exit 1
}
chmod +x /root/awssg22.sh

echo "🕒 正在写入定时任务..."
# 逻辑说明：
# grep -vE 会过滤掉包含这两个文件名的旧任务，防止多次运行脚本导致 crontab 爆炸
# 然后重新把两个任务追加进去
(
    crontab -l 2>/dev/null | grep -vE '/root/awssg11.sh|/root/awssg22.sh' || true
    echo "* * * * * /root/awssg11.sh >>/root/awssg11.log 2>&1"
    echo "* * * * * /root/awssg22.sh >>/root/awssg22.log 2>&1"
) | crontab -

echo "🔄 重启 cron 服务..."
systemctl restart cron 2>/dev/null || systemctl restart crond 2>/dev/null
systemctl enable cron >/dev/null 2>&1 || systemctl enable crond >/dev/null 2>&1 || true

echo "🔍 检查 BBR 状态..."
sysctl net.ipv4.tcp_congestion_control
sysctl net.core.default_qdisc

echo "🔍 当前 cron 任务如下："
crontab -l



####################################
# 完成提示
####################################

echo ""
echo "🎉 所有任务执行完成！"
echo "✅ Debian 环境依赖已安装"
echo "✅ nyanpass 节点已执行安装"
echo "✅ /etc/sysctl.conf 已覆盖"
echo "✅ BBR 参数已应用"
echo "✅ /root/azjx.sh 已下载并加入每分钟定时任务"
