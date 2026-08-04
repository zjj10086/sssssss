#!/bin/bash
set -Eeuo pipefail

AWS_GFW_WATCH_URL="https://raw.githubusercontent.com/zjj10086/sssssss/refs/heads/main/1.py"
AWS_GFW_WATCH_PATH="/root/1.py"

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
apt install -y curl wget cron ca-certificates python3

echo "🐍 Python 版本：$(python3 --version 2>&1)"

####################################
# 第二部分：安装 nyanpass 节点
####################################

echo "🚀 开始安装 nyanpass 节点..."
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link"
echo -e "1\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t e2cffc11-ba17-4de5-8d17-7b5719d43680 -u https://ny.qwqa.link"
echo "✅ nyanpass 节点安装命令已执行"

####################################
# 第三部分：安装 Komari Agent
####################################

echo "🚀 开始安装 Komari Agent..."
wget -qO- https://raw.githubusercontent.com/komari-monitor/komari-agent/refs/heads/main/install.sh | bash -s -- \
  -e https://tz.xn--diqv0fut7b.cc \
  -t MqEtF56KG8h0PZ5Axrk5zI
echo "✅ Komari Agent 安装命令已执行"

####################################
# 第四部分：安装 AWS TCP 检测与换 IP 服务
####################################

echo "🌐 正在下载 AWS TCP 检测与换 IP 脚本..."
rm -f -- "/root/aws_gfw_watch.py" "${AWS_GFW_WATCH_PATH}"
curl -4 -fL \
  --retry 3 \
  --retry-delay 2 \
  --connect-timeout 15 \
  --max-time 120 \
  -H "Cache-Control: no-cache" \
  -H "Pragma: no-cache" \
  "${AWS_GFW_WATCH_URL}?cachebust=$(date +%s)-$$" \
  -o "${AWS_GFW_WATCH_PATH}"
chmod 700 "${AWS_GFW_WATCH_PATH}"

echo "🔍 正在校验 Python 脚本..."
python3 - "${AWS_GFW_WATCH_PATH}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
compile(source, str(path), "exec")

required = (
    "AWS_SB_SHARE_TOKEN",
    "BARK_URL",
    "sx-cu-v4.ip.zstaticcdn.com:80",
    "sx-cu-v6.ip.zstaticcdn.com:80",
    "pending_ipv4_notification",
    "pending_ipv6_cleanup",
    "ExecStart=/root/1.py",
    "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",
    "--install",
)
missing = [item for item in required if item not in source]
if missing:
    raise SystemExit(f"下载的 Python 脚本缺少必要内容：{','.join(missing)}")
PY

echo "⚙️ 正在安装并启动 aws-gfw-watch systemd 服务..."
rm -f -- "/opt/aws-gfw-watch/aws_gfw_watch.py" "/opt/aws-gfw-watch/1.py"
python3 "${AWS_GFW_WATCH_PATH}" --install
rmdir /opt/aws-gfw-watch 2>/dev/null || true
systemctl is-enabled --quiet aws-gfw-watch
systemctl is-active --quiet aws-gfw-watch
echo "✅ AWS TCP 检测服务已启动，每 120 秒检测一次，无需 cron"

####################################
# 第五部分：覆盖 /etc/sysctl.conf
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
echo "✅ Komari Agent 已执行安装"
echo "✅ AWS TCP 检测与自动换 IP 服务已启动"
echo "✅ /etc/sysctl.conf 已覆盖"
echo "✅ BBR 参数已应用"
echo ""
echo "查看 AWS 检测日志：journalctl -u aws-gfw-watch -f"
