#!/bin/bash

echo "🚀 开始执行一键安装脚本..."

####################################
# 第一部分：基础环境准备
####################################

apt update -y
apt install -y curl wget cron

####################################
# 第二部分：安装 nyanpass 节点
####################################

echo "🚀 开始安装 nyanpass 节点..."
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) \
rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link"

echo "✅ nyanpass 节点安装完成！"

####################################
# 第三部分：安装哪吒探针 Agent
####################################

echo "🚀 开始安装哪吒探针 Agent..."

curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/agent/install.sh -o agent.sh
chmod +x agent.sh

env \
NZ_SERVER=tz.xn--diqv0fut7b.cc:443 \
NZ_TLS=true \
NZ_CLIENT_SECRET=WZ2ilygdvn1mCshOaeqfX5GhE0RmXWob \
NZ_UUID=f131a9ff-43a6-fd49-2cf3-4641ef17c025 \
./agent.sh

echo "✅ 哪吒探针已安装并尝试连接"

####################################
# 第四部分：系统网络优化（BBR + IPv6）
####################################

cat > /etc/sysctl.conf << EOF
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
# 只需要调以下四个参数值
# net.core.rmem_max
# net.core.wmem_max
# net.ipv4.tcp_rmem
# net.ipv4.tcp_wmem
# 计算公式 带宽 * 字节数 * RTT延迟 / 8 = BDP_Max
# 计算出的最大值填入 net.core.rmem_max net.core.wmem_max 这两个最大值需要一致，只需要用speedtest_cli测试出来的值套用计算公式计算出来即可，测试出来的值进行四舍五入计算后再套用公式进行计算
# 计算出来的最大值需要填写 net.ipv4.tcp_rmem net.ipv4.tcp_wmem 最后一个值里去
# 参数值释义
# net.core.rmem_max 下行带宽
# net.core.wmem_max 上行带宽
# net.ipv4.tcp_rmem ipv4下行带宽参数
# net.ipv4.tcp_wmem ipv4上行带宽参数
# net.ipv4.tcp_rmem=4096 524288 30000000 这三个值默认排序是，最小值、默认值、最大值，一般只需要调默认值和最大值，最小值不做更改
# Speedtest_cli 安装命令
# apt install sudo -y && curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash && apt-get install speedtest && speedtest -y
# Speedtest_cli 常用命令
# speedtest -L 查看最近VPS测速点
# speedtest -s 测速点id
# speedtest 不加任何参数，直接进行测速 （不推荐，默认测速点不一定是距离服务器最近的）
# 本TCP网络参数模板取自BageVM默认参数模板进行修改
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
sysctl -p && sysctl --system


####################################
# 完成提示
####################################

echo ""
echo "🎉 所有任务已完成！"
echo "✅ nyanpass 节点：已部署"
echo "✅ 哪吒探针：已连接"
echo "✅ 系统网络参数已优化"
