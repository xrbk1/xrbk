import os
import time
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import ipwhois
from ipwhois import IPWhois
import socket
import re
import random
import urllib3
from urllib.parse import urlparse

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 全局设置
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1'
]

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

def validate_proxies():
    # 选择代理文件
    file_path = input("请输入代理文件路径: ").strip()
    if not os.path.exists(file_path):
        print("文件不存在！")
        return
    
    # 读取代理列表
    with open(file_path, 'r') as f:
        proxies = [line.strip() for line in f.readlines() if line.strip()]
    
    if not proxies:
        print("文件中没有找到有效的代理")
        return
    
    # 输入验证URL（多个）
    urls_input = input("请输入要验证的URL（多个用逗号分隔）: ").strip()
    test_urls = [url.strip() for url in urls_input.split(',') if url.strip()]
    
    if not test_urls:
        print("未输入任何URL！")
        return
    
    # 确保URL格式正确
    for i, url in enumerate(test_urls):
        if not url.startswith(('http://', 'https://')):
            test_urls[i] = 'http://' + url
    
    # 选择验证协议类型
    print("\n请选择要验证的代理协议:")
    print("1. HTTP")
    print("2. HTTPS")
    print("3. SOCKS4")
    print("4. SOCKS5")
    print("5. 全部协议")
    protocol_choice = input("请输入选项(1-5, 多个用逗号分隔, 默认5): ").strip() or "5"
    
    # 解析协议选择
    selected_protocols = []
    if protocol_choice == "5":
        selected_protocols = ['http', 'https', 'socks4', 'socks5']
    else:
        choices = protocol_choice.split(',')
        for choice in choices:
            if choice.strip() == '1':
                selected_protocols.append('http')
            elif choice.strip() == '2':
                selected_protocols.append('https')
            elif choice.strip() == '3':
                selected_protocols.append('socks4')
            elif choice.strip() == '4':
                selected_protocols.append('socks5')
    
    if not selected_protocols:
        print("未选择任何协议！")
        return
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认100): ") or 100)
    except:
        max_workers = 100
    
    print(f"\n开始验证 {len(proxies)} 个代理，使用 {max_workers} 线程...")
    print(f"验证协议: {', '.join(selected_protocols)}")
    print(f"验证URL: {', '.join(test_urls)}")
    
    # 存储结果
    valid_proxies = {}  # ip:port -> 支持的协议列表
    timeout = 10
    required_success = len(test_urls) - 1  # 需要成功的URL数量
    
    def check_proxy(proxy):
        """检查单个代理是否可用"""
        proxy_supported = []
        
        for protocol in selected_protocols:
            proxies_dict = {}
            
            if protocol == 'http':
                proxies_dict = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
            elif protocol == 'https':
                proxies_dict = {'http': f'https://{proxy}', 'https': f'https://{proxy}'}
            elif protocol == 'socks4':
                proxies_dict = {'http': f'socks4://{proxy}', 'https': f'socks4://{proxy}'}
            elif protocol == 'socks5':
                proxies_dict = {'http': f'socks5://{proxy}', 'https': f'socks5://{proxy}'}
            
            success_count = 0
            for url in test_urls:
                try:
                    # 忽略SSL证书验证
                    response = requests.get(
                        url, 
                        proxies=proxies_dict, 
                        timeout=timeout,
                        headers=get_random_headers(),
                        verify=False  # 关键修改：忽略证书验证
                    )
                    if 200 <= response.status_code < 400:
                        success_count += 1
                except Exception as e:
                    # 忽略所有连接错误
                    pass
            
            # 检查是否满足成功条件
            if success_count > required_success:
                proxy_supported.append(protocol)
                
                # 对于HTTP代理，自动检查是否支持HTTPS
                if protocol == 'http' and 'https' not in selected_protocols:
                    try:
                        https_proxies = {'http': f'https://{proxy}', 'https': f'https://{proxy}'}
                        response = requests.get(
                            random.choice(test_urls), 
                            proxies=https_proxies, 
                            timeout=timeout,
                            headers=get_random_headers(),
                            verify=False  # 关键修改：忽略证书验证
                        )
                        if 200 <= response.status_code < 400:
                            proxy_supported.append('https')
                    except:
                        pass
        
        return proxy, proxy_supported
    
    # 进度计数器
    processed = 0
    total = len(proxies)
    
    def update_progress():
        nonlocal processed
        processed += 1
        if processed % 50 == 0 or processed == total:
            print(f"已处理: {processed}/{total} ({processed/total*100:.1f}%)")
    
    # 使用线程池处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for proxy in proxies:
            future = executor.submit(check_proxy, proxy)
            future.add_done_callback(lambda x: update_progress())
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            proxy, protocols = future.result()
            if protocols:
                valid_proxies[proxy] = protocols
    
    # 保存有效代理
    output_file = os.path.join(os.getcwd(), 'http.txt')
    
    with open(output_file, 'w') as f:
        # 区域1: 只显示IP和端口
        f.write("[区域1: IP:PORT]\n")
        for proxy in valid_proxies.keys():
            f.write(f"{proxy}\n")
        
        f.write("\n\n[区域2: 按协议分类]\n")
        
        # 区域2: 按协议分类显示
        protocol_map = {
            'http': "HTTP代理:",
            'https': "HTTPS代理:",
            'socks4': "SOCKS4代理:",
            'socks5': "SOCKS5代理:"
        }
        
        for protocol, title in protocol_map.items():
            f.write(f"\n{title}\n")
            for proxy, protocols in valid_proxies.items():
                if protocol in protocols:
                    if protocol == 'http':
                        f.write(f"http://{proxy}\n")
                    elif protocol == 'https':
                        f.write(f"https://{proxy}\n")
                    elif protocol == 'socks4':
                        f.write(f"socks4://{proxy}\n")
                    elif protocol == 'socks5':
                        f.write(f"socks5://{proxy}\n")
    
    print(f"\n验证完成！有效代理数: {len(valid_proxies)}")
    print(f"结果已保存到: {output_file}")

def speed_test_proxies():
    # 选择代理文件
    file_path = input("请输入代理文件路径: ").strip()
    if not os.path.exists(file_path):
        print("文件不存在！")
        return
    
    # 读取代理列表
    with open(file_path, 'r') as f:
        proxies = [line.strip() for line in f.readlines() if line.strip()]
    
    if not proxies:
        print("文件中没有找到有效的代理")
        return
    
    # 输入测速URL
    test_url = input("请输入要测速的URL: ").strip()
    if not test_url.startswith(('http://', 'https://')):
        test_url = 'http://' + test_url
    
    # 选择测速协议
    print("\n请选择测速使用的代理协议:")
    print("1. HTTP")
    print("2. HTTPS")
    print("3. SOCKS4")
    print("4. SOCKS5")
    print("5. 全部协议（自动识别）")
    protocol_choice = input("请输入选项(1-5, 默认5): ").strip() or "5"
    
    # 解析协议选择
    if protocol_choice == "5":
        selected_protocols = ['http', 'https', 'socks4', 'socks5']
        auto_detect = True
    else:
        selected_protocols = []
        protocol_map = {
            '1': 'http',
            '2': 'https',
            '3': 'socks4',
            '4': 'socks5'
        }
        protocol = protocol_map.get(protocol_choice, 'http')
        selected_protocols = [protocol]
        auto_detect = False
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认50): ") or 50)
    except:
        max_workers = 50
    
    print(f"\n开始测速 {len(proxies)} 个代理，使用 {max_workers} 线程...")
    print(f"测速协议: {', '.join(selected_protocols) if auto_detect else selected_protocols[0]}")
    
    # 存储结果
    region1_results = []  # (ip:port, speed)
    region2_results = []  # (protocol:ip:port, speed)
    timeout = 20
    
    def test_speed_for_protocol(proxy, protocol):
        """测试特定协议的代理速度"""
        try:
            if protocol == 'http':
                proxies_dict = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
                prefix = "http://"
            elif protocol == 'https':
                proxies_dict = {'http': f'https://{proxy}', 'https': f'https://{proxy}'}
                prefix = "https://"
            elif protocol == 'socks4':
                proxies_dict = {'http': f'socks4://{proxy}', 'https': f'socks4://{proxy}'}
                prefix = "socks4://"
            elif protocol == 'socks5':
                proxies_dict = {'http': f'socks5://{proxy}', 'https': f'socks5://{proxy}'}
                prefix = "socks5://"
            
            start_time = time.time()
            # 忽略SSL证书验证
            response = requests.get(
                test_url, 
                proxies=proxies_dict, 
                timeout=timeout,
                stream=True,
                headers=get_random_headers(),
                verify=False  # 关键修改：忽略证书验证
            )
            response.raise_for_status()
            
            # 读取1MB数据计算速度
            chunk_size = 1024
            total_bytes = 0
            max_bytes = 1024 * 1024  # 1MB
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                total_bytes += len(chunk)
                if total_bytes >= max_bytes:
                    break
            
            elapsed = time.time() - start_time
            speed = total_bytes / elapsed / 1024  # KB/s
            return prefix, round(speed, 2)
        except Exception as e:
            # 忽略所有连接错误
            return None, 0
    
    def test_proxy(proxy):
        """测试单个代理的速度"""
        proxy_results = []
        fastest_speed = 0
        fastest_protocol = ""
        
        # 测试所有选择的协议
        for protocol in selected_protocols:
            prefix, speed = test_speed_for_protocol(proxy, protocol)
            if speed > 0:
                # 记录区域2结果
                proxy_addr = f"{prefix}{proxy}"
                region2_results.append((proxy_addr, speed))
                proxy_results.append((prefix, speed))
                
                # 记录最快协议
                if speed > fastest_speed:
                    fastest_speed = speed
                    fastest_protocol = prefix
        
        # 如果有可用的协议，记录区域1结果
        if fastest_speed > 0:
            region1_results.append((proxy, fastest_speed, fastest_protocol))
        
        return proxy, proxy_results
    
    # 进度计数器
    processed = 0
    total = len(proxies)
    
    def update_progress():
        nonlocal processed
        processed += 1
        if processed % 50 == 0 or processed == total:
            print(f"已处理: {processed}/{total} ({processed/total*100:.1f}%)")
    
    # 使用线程池处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for proxy in proxies:
            future = executor.submit(test_proxy, proxy)
            future.add_done_callback(lambda x: update_progress())
            futures.append(future)
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            pass  # 结果已经在回调中收集
    
    # 按速度降序排序
    region1_results.sort(key=lambda x: x[1], reverse=True)
    region2_results.sort(key=lambda x: x[1], reverse=True)
    
    # 保存测速结果
    output_file = os.path.join(os.getcwd(), 'cs.txt')
    with open(output_file, 'w') as f:
        # 区域1: IP:端口 速度
        f.write("[区域1: IP:PORT 速度]\n")
        f.write("=" * 50 + "\n")
        for proxy, speed, protocol in region1_results:
            f.write(f"{proxy} - {speed} KB/s\n")
        
        # 区域2: 协议:IP:端口 速度
        f.write("\n\n[区域2: 协议:IP:PORT 速度]\n")
        f.write("=" * 50 + "\n")
        for proxy_addr, speed in region2_results:
            f.write(f"{proxy_addr} - {speed} KB/s\n")
    
    # 统计信息
    valid_proxies_count = len(region1_results)
    total_speeds = sum(item[1] for item in region1_results)
    avg_speed = total_speeds / valid_proxies_count if valid_proxies_count > 0 else 0
    
    print(f"\n测速完成！有效代理数: {valid_proxies_count}")
    print(f"最高速度: {region1_results[0][1] if region1_results else 0} KB/s")
    print(f"平均速度: {avg_speed:.2f} KB/s")
    print(f"结果已保存到: {output_file}")

def detect_proxy_countries():
    # 选择代理文件
    file_path = input("请输入代理文件路径: ").strip()
    if not os.path.exists(file_path):
        print("文件不存在！")
        return
    
    # 读取代理列表
    with open(file_path, 'r') as f:
        proxies = [line.strip() for line in f.readlines() if line.strip()]
    
    if not proxies:
        print("文件中没有找到有效的代理")
        return
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认50): ") or 50)
    except:
        max_workers = 50
    
    print(f"开始检测 {len(proxies)} 个代理的国家信息，使用 {max_workers} 线程...")
    
    # 存储结果：国家 -> [代理列表]
    country_proxies = {}
    
    # 提取IP地址的正则表达式
    ip_pattern = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    
    def extract_ip(proxy_str):
        """从代理字符串中提取IP地址"""
        match = ip_pattern.search(proxy_str)
        if match:
            return match.group(0)
        # 尝试解析主机名
        parts = proxy_str.split(':')
        if len(parts) >= 2:
            host = parts[0]
            try:
                return socket.gethostbyname(host)
            except:
                pass
        return None
    
    def get_country(proxy):
        """获取代理所属国家"""
        try:
            ip = extract_ip(proxy)
            if not ip:
                return "Unknown", proxy
            
            # 使用ipwhois查询国家信息
            obj = IPWhois(ip)
            results = obj.lookup_rdap()
            country = results.get('asn_country', 'Unknown')
            
            # 如果未获取到国家信息，尝试备用方法
            if country == 'Unknown':
                try:
                    # 使用HTTP而不是HTTPS，避免证书问题
                    response = requests.get(f"http://ipinfo.io/{ip}/country", timeout=5)
                    if response.status_code == 200:
                        country = response.text.strip() or 'Unknown'
                except:
                    pass
            
            return country, proxy
        except:
            return "Unknown", proxy
    
    # 进度计数器
    processed = 0
    total = len(proxies)
    
    def update_progress():
        nonlocal processed
        processed += 1
        if processed % 50 == 0 or processed == total:
            print(f"已处理: {processed}/{total} ({processed/total*100:.1f}%)")
    
    # 使用线程池处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for proxy in proxies:
            future = executor.submit(get_country, proxy)
            future.add_done_callback(lambda x: update_progress())
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            country, proxy = future.result()
            if country not in country_proxies:
                country_proxies[country] = []
            country_proxies[country].append(proxy)
    
    # 按国家名称排序
    sorted_countries = sorted(country_proxies.keys())
    
    # 保存结果
    output_file = os.path.join(os.getcwd(), 'gj.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        for country in sorted_countries:
            f.write(f"{country}:\n")
            for proxy in country_proxies[country]:
                f.write(f"{proxy}\n")
            f.write("\n")
    
    print(f"国家检测完成！已检测 {len(proxies)} 个代理")
    print(f"发现 {len(country_proxies)} 个国家")
    print(f"结果已保存到: {output_file}")

def main():
    while True:
        print("\n" + "="*50)
        print("代理工具菜单")
        print("1. 验证代理存活 (支持HTTP/HTTPS/SOCKS4/SOCKS5)")
        print("2. 测速代理下载速度 (支持HTTP/HTTPS/SOCKS4/SOCKS5/自动识别)")
        print("3. 检测代理国家")
        print("4. 退出")
        print("="*50)
        
        choice = input("请选择功能 (1/2/3/4): ").strip()
        
        if choice == '1':
            validate_proxies()
        elif choice == '2':
            speed_test_proxies()
        elif choice == '3':
            detect_proxy_countries()
        elif choice == '4':
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main()
