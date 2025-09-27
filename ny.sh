#!/bin/bash

# 执行安装命令并自动输入
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link""

# 执行新的 bash 命令（无预输入）

# 安装 Nezha 监控代理
curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/install.sh -o nezha.sh && chmod +x nezha.sh && ./nezha.sh install_agent 23.94.83.24 5555 oer1NSgoX8i6DRmgW0

# 完成提示
echo "所有命令执行完毕！"
