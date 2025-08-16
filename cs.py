import os
import time
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import ipwhois
from ipwhois import IPWhois
import socket
import re

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
    
    # 输入验证URL
    test_url = input("请输入要验证的URL: ").strip()
    if not test_url.startswith(('http://', 'https://')):
        test_url = 'http://' + test_url
    
    # 选择验证协议类型
    print("请选择验证协议类型:")
    print("1. HTTP代理验证")
    print("2. HTTPS代理验证")
    print("3. 自动检测(HTTP和HTTPS)")
    protocol_choice = input("请输入选项(1/2/3, 默认3): ").strip() or "3"
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认100): ") or 100)
    except:
        max_workers = 100
    
    print(f"开始验证 {len(proxies)} 个代理，使用 {max_workers} 线程...")
    
    valid_proxies = []
    timeout = 10
    
    def check_proxy(proxy):
        try:
            # 根据选择创建代理设置
            proxies_dict = {}
            if protocol_choice == "1":  # HTTP
                proxies_dict = {
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                }
            elif protocol_choice == "2":  # HTTPS
                proxies_dict = {
                    'http': f'https://{proxy}',
                    'https': f'https://{proxy}'
                }
            else:  # 自动检测
                # 先尝试HTTP
                http_proxy = {
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                }
                # 再尝试HTTPS
                https_proxy = {
                    'http': f'https://{proxy}',
                    'https': f'https://{proxy}'
                }
                
                # 测试HTTP
                try:
                    response = requests.get(
                        test_url, 
                        proxies=http_proxy, 
                        timeout=timeout,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    if response.status_code == 200:
                        return f"http://{proxy}"
                except:
                    pass
                
                # 测试HTTPS
                try:
                    response = requests.get(
                        test_url, 
                        proxies=https_proxy, 
                        timeout=timeout,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    if response.status_code == 200:
                        return f"https://{proxy}"
                except:
                    pass
                
                return None
            
            # 对于单一协议验证
            response = requests.get(
                test_url, 
                proxies=proxies_dict, 
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            if response.status_code == 200:
                return proxy
        except:
            pass
        return None
    
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
            result = future.result()
            if result:
                valid_proxies.append(result)
    
    # 保存有效代理
    output_file = os.path.join(os.getcwd(), 'http.txt')
    with open(output_file, 'w') as f:
        f.write('\n'.join(valid_proxies))
    
    print(f"验证完成！有效代理数: {len(valid_proxies)}")
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
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认50): ") or 50)
    except:
        max_workers = 50
    
    print(f"开始测速 {len(proxies)} 个代理，使用 {max_workers} 线程...")
    
    results = []
    timeout = 15
    
    def test_speed(proxy):
        try:
            proxies_dict = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            
            start_time = time.time()
            response = requests.get(
                test_url, 
                proxies=proxies_dict, 
                timeout=timeout,
                stream=True,
                headers={'User-Agent': 'Mozilla/5.0'}
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
            return (proxy, round(speed, 2))
        except:
            return (proxy, 0)
    
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
            future = executor.submit(test_speed, proxy)
            future.add_done_callback(lambda x: update_progress())
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    # 按速度降序排序
    results.sort(key=lambda x: x[1], reverse=True)
    
    # 保存测速结果
    output_file = os.path.join(os.getcwd(), 'cs.txt')
    with open(output_file, 'w') as f:
        for proxy, speed in results:
            if speed > 0:
                f.write(f"{proxy} - {speed} KB/s\n")
    
    print(f"测速完成！有效代理数: {len([r for r in results if r[1] > 0])}")
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
        print("1. 验证代理存活")
        print("2. 测速代理下载速度")
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
