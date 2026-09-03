#!/bin/bash
set -Eeuo pipefail

echo "🚀 开始执行 Debian 一键安装脚本..."

####################################
# 检查环境
####################################

if [ "$(id -u)" != "0" ]; then
  echo "❌ 请使用 root 用户运行此脚本"
  exit 1
fi

if ! grep -qi debian /etc/os-release; then
  echo "❌ 这个脚本只适用于 Debian"
  exit 1
fi

####################################
# 第一部分：基础环境准备
####################################

echo "📦 更新软件包并安装基础依赖..."
apt update -y
apt install -y curl wget ca-certificates cron python3

echo "🐍 Python 版本：$(python3 --version 2>&1)"

####################################
# 第二部分：安装 nyanpass 节点
####################################

echo "🚀 开始安装 nyanpass 节点..."

echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 150a70a9-8235-4baf-8d1f-8fd1838e3357 -u https://ny.qwqa.link"

echo "✅ nyanpass 节点安装命令已执行"

####################################
# 第三部分：安装 Komari Agent 探针
####################################

echo "🚀 开始安装 Komari Agent 探针..."

wget -qO- https://raw.githubusercontent.com/komari-monitor/komari-agent/refs/heads/main/install.sh | bash -s -- \
  -e https://tz.xn--diqv0fut7b.cc \
  -t RQqFAmcl8lZZwy5jxsxLFP

echo "✅ Komari Agent 探针安装命令已执行"

####################################
# 完成提示
####################################

echo ""
echo "🎉 所有任务执行完成！"
echo "✅ Debian 基础环境依赖已安装"
echo "✅ nyanpass 节点已执行安装"
echo "✅ Komari Agent 探针已执行安装"
echo ""
