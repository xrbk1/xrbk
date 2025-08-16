import os
import re
import time
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from socks import create_connection, PROXY_TYPES
import socket
from urllib.parse import urlparse

# 全局配置
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
TIMEOUT = 15  # 单次请求超时时间
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

# 配置重试策略
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
SESSION.mount("http://", adapter)
SESSION.mount("https://", adapter)

def parse_proxy(proxy_str, protocol):
    """解析代理字符串并返回格式化代理地址"""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    
    # 处理带协议前缀的代理
    if "://" in proxy_str:
        parts = proxy_str.split("://", 1)
        return f"{parts[0]}://{parts[1]}"
    
    # 处理IP:PORT格式
    if ":" in proxy_str:
        return f"{protocol}://{proxy_str}"
    
    return None

def test_connection(proxy, test_url, protocol, max_retries=0):
    """测试代理连接性"""
    proxies = {}
    proxy_type = proxy.split("://")[0].lower()
    
    # 设置代理字典
    if proxy_type in ['http', 'https']:
        proxies = {"http": proxy, "https": proxy}
    elif proxy_type in ['socks4', 'socks5']:
        proxies = {"http": f"socks5://{proxy.split('://')[1]}", 
                  "https": f"socks5://{proxy.split('://')[1]}"}
    
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            response = SESSION.get(
                test_url, 
                proxies=proxies, 
                timeout=TIMEOUT,
                verify=False  # 忽略SSL证书验证
            )
            response.raise_for_status()
            latency = int((time.time() - start_time) * 1000)  # 毫秒
            return True, latency
        except Exception as e:
            if attempt >= max_retries:
                return False, 0
    return False, 0

def test_download_speed(proxy, test_url, protocol, max_retries=0):
    """测试代理下载速度"""
    proxies = {}
    proxy_type = proxy.split("://")[0].lower()
    
    if proxy_type in ['http', 'https']:
        proxies = {"http": proxy, "https": proxy}
    elif proxy_type in ['socks4', 'socks5']:
        proxies = {"http": f"socks5://{proxy.split('://')[1]}", 
                  "https": f"socks5://{proxy.split('://')[1]}"}
    
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            with SESSION.get(
                test_url, 
                proxies=proxies, 
                stream=True,
                timeout=TIMEOUT,
                verify=False
            ) as response:
                response.raise_for_status()
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        total_bytes += len(chunk)
                        # 测试10秒后中断
                        if time.time() - start_time > 10:
                            break
            
            duration = time.time() - start_time
            speed = total_bytes / duration / 1024  # KB/s
            return True, round(speed, 2)
        except Exception as e:
            if attempt >= max_retries:
                return False, 0
    return False, 0

def process_file(file_path, protocol):
    """处理代理文件并返回有效代理列表"""
    valid_proxies = []
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return valid_proxies
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for line in lines:
        proxy = parse_proxy(line, protocol)
        if proxy:
            valid_proxies.append(proxy)
    
    return valid_proxies

def main():
    print("=" * 50)
    print("代理工具 v1.0")
    print("1. 代理验证 (存活检测)")
    print("2. 代理测速 (下载速度)")
    print("=" * 50)
    
    choice = input("请选择功能 (1/2): ").strip()
    
    if choice == '1':
        file_path = input("请输入代理文件路径: ").strip()
        print("可选协议: http, https, socks4, socks5, all")
        protocol_choice = input("请选择协议: ").lower().strip()
        
        protocols = []
        if protocol_choice == 'all':
            protocols = ['http', 'https', 'socks4', 'socks5']
        elif protocol_choice in ['http', 'https', 'socks4', 'socks5']:
            protocols = [protocol_choice]
        else:
            print("无效的协议选择!")
            return
        
        test_url = input("请输入测试URL: ").strip()
        max_retries = int(input("输入重试次数 (0=不重试): "))
        threads = int(input("输入线程数: "))
        
        # 处理所有协议
        all_proxies = []
        for proto in protocols:
            all_proxies.extend(process_file(file_path, proto))
        
        print(f"找到 {len(all_proxies)} 个代理，开始验证...")
        
        valid_proxies = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    test_connection, 
                    proxy, 
                    test_url, 
                    proxy.split("://")[0],
                    max_retries
                ): proxy for proxy in all_proxies
            }
            
            for future in concurrent.futures.as_completed(futures):
                proxy = futures[future]
                try:
                    success, latency = future.result()
                    if success:
                        print(f"[✓] {proxy} 有效 | 延迟: {latency}ms")
                        valid_proxies.append(proxy)
                    else:
                        print(f"[✗] {proxy} 无效")
                except Exception as e:
                    print(f"[!] {proxy} 测试出错: {str(e)}")
        
        # 保存结果
        with open("http.txt", "w", encoding="utf-8") as f:
            for proxy in valid_proxies:
                f.write(f"{proxy}\n")
        print(f"验证完成! 有效代理已保存到 http.txt (总数: {len(valid_proxies)})")
    
    elif choice == '2':
        file_path = input("请输入代理文件路径: ").strip()
        print("可选协议: http, https, socks4, socks5, all")
        protocol_choice = input("请选择协议: ").lower().strip()
        
        protocols = []
        if protocol_choice == 'all':
            protocols = ['http', 'https', 'socks4', 'socks5']
        elif protocol_choice in ['http', 'https', 'socks4', 'socks5']:
            protocols = [protocol_choice]
        else:
            print("无效的协议选择!")
            return
        
        test_url = input("请输入测速文件URL: ").strip()
        max_retries = int(input("输入重试次数 (0=不重试): "))
        threads = int(input("输入线程数: "))
        
        # 处理所有协议
        all_proxies = []
        for proto in protocols:
            all_proxies.extend(process_file(file_path, proto))
        
        print(f"找到 {len(all_proxies)} 个代理，开始测速...")
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    test_download_speed, 
                    proxy, 
                    test_url, 
                    proxy.split("://")[0],
                    max_retries
                ): proxy for proxy in all_proxies
            }
            
            for future in concurrent.futures.as_completed(futures):
                proxy = futures[future]
                try:
                    success, speed = future.result()
                    if success:
                        print(f"[✓] {proxy} 速度: {speed} KB/s")
                        results.append((proxy, speed))
                    else:
                        print(f"[✗] {proxy} 测速失败")
                except Exception as e:
                    print(f"[!] {proxy} 测速出错: {str(e)}")
        
        # 按速度排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        # 保存结果
        with open("cs.txt", "w", encoding="utf-8") as f:
            for proxy, speed in results:
                f.write(f"{proxy} | {speed} KB/s\n")
        print(f"测速完成! 结果已保存到 cs.txt (总数: {len(results)})")
    
    else:
        print("无效选择!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已终止")
    except Exception as e:
        print(f"发生错误: {str(e)}")
