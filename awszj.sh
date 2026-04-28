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
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link"
echo "✅ nyanpass 节点安装命令已执行"

####################################
# 第三部分：安装哪吒探针 Agent
####################################

echo "🚀 开始安装哪吒探针 Agent..."
curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/agent/install.sh -o agent.sh && chmod +x agent.sh && env NZ_SERVER=tz.xn--diqv0fut7b.cc:443 NZ_TLS=true NZ_CLIENT_SECRET=WZ2ilygdvn1mCshOaeqfX5GhE0RmXWob NZ_UUID=ac745083-aee5-4715-814a-d1eb1d2788f0 ./agent.sh
echo "✅ 哪吒探针安装命令已执行"

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



echo "🔍 检查 BBR 状态..."
sysctl net.ipv4.tcp_congestion_control
sysctl net.core.default_qdisc





####################################
# 完成提示
####################################

echo ""
echo "🎉 所有任务执行完成！"
echo "✅ Debian 环境依赖已安装"
echo "✅ nyanpass 节点已执行安装"
echo "✅ 哪吒探针已执行安装"
echo "✅ /etc/sysctl.conf 已覆盖"
echo "✅ BBR 参数已应用"
