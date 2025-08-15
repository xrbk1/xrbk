#!/bin/bash

# 检查参数数量
if [ "$#" -lt 3 ]; then
  echo "Usage: sh tcp.sh <ip> <port> <time> [threads]"
  exit 1
fi

# 参数赋值
IP=$1
PORT=$2
TIME=$3
THREADS=${4:-50} # 默认线程数为50

# 运行Node.js脚本
node tcp.js $IP $PORT $TIME $THREADS
