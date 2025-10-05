#!/bin/bash

# ===========================
# 自动安装 DDNS + Nyanpass + Nezha
# ===========================

# --- 1. 安装并配置 DDNS (Cloudflare + Telegram) ---
echo "[INFO] 开始安装 DDNS..."
bash <(wget -qO- https://raw.githubusercontent.com/mocchen/cssmeihua/mochen/shell/ddns.sh) <<EOF
tutu119216@gmail.com
6HuEmDY_BRwvHhbMSsESOie2IOKM61Qvahw0pB8f

y
aws1485-28-12wa.484845845.xyz
y
8371117300:AAHHMYPBTx8SAxhfexcw3jTcQMVVSOuDc
6133126873
EOF

echo "[INFO] DDNS 配置完成！"

# --- 2. 安装 Nyanpass ---
echo "[INFO] 开始安装 Nyanpass..."
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link"
echo -e "nuan\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t 7a510a72-8f0e-45a6-8937-42c1c545ff9c -u https://materelay.com"

# --- 3. 安装 Nezha 监控代理 ---
echo "[INFO] 开始安装 Nezha 监控代理..."
curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/install.sh -o nezha.sh
chmod +x nezha.sh
./nezha.sh install_agent 23.94.83.24 5555 oer1NSgoX8i6DRmgW0

# --- 4. 完成提示 ---
echo "[INFO] 所有命令执行完毕！"
