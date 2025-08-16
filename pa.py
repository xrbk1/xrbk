import requests
from bs4 import BeautifulSoup
import re
import time
import random
import concurrent.futures
from fake_useragent import UserAgent

def fetch_proxies():
    """从多个免费代理网站抓取代理IP"""
    proxies = set()
    ua = UserAgent()
    
    # 扩展的代理源列表（总计20+个来源）
    sources = [
        # 国际代理源
        {"name": "FreeProxyList", "url": "https://www.free-proxy-list.net/", "type": "table", "class": "table table-striped table-bordered"},
        {"name": "SSLProxies", "url": "https://www.sslproxies.org/", "type": "table", "class": "table table-striped table-bordered"},
        {"name": "USProxy", "url": "https://www.us-proxy.org/", "type": "table", "class": "table table-striped table-bordered"},
        {"name": "UKProxy", "url": "https://free-proxy-list.net/uk-proxy.html", "type": "table", "class": "table table-striped table-bordered"},
        {"name": "ProxyScrape", "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all", "type": "plain"},
        {"name": "ProxyListPlus", "url": "https://list.proxylistplus.com/Fresh-HTTP-Proxy-List-1", "type": "table", "id": "page"},
        {"name": "Geonode", "url": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc", "type": "json"},
        {"name": "OpenProxy", "url": "https://openproxy.space/list/http", "type": "plain"},
        {"name": "ProxyListDownload", "url": "https://www.proxy-list.download/api/v1/get?type=http", "type": "plain"},
        {"name": "SpysMe", "url": "https://spys.me/proxy.txt", "type": "plain"},
        
        # 国内代理源
        {"name": "快代理", "url": "https://www.kuaidaili.com/free/", "type": "table", "class": "table table-bordered table-striped"},
        {"name": "西刺代理", "url": "https://www.xicidaili.com/wt/", "type": "table", "id": "ip_list"},
        {"name": "66代理", "url": "http://www.66ip.cn/", "type": "div", "id": "main"},
        {"name": "89代理", "url": "http://www.89ip.cn/", "type": "table", "class": "layui-table"},
        {"name": "云代理", "url": "http://www.ip3366.net/free/", "type": "table", "class": "table table-bordered table-striped"},
        {"name": "无忧代理", "url": "http://www.data5u.com/", "type": "ul", "class": "l2"},
        {"name": "站大爷", "url": "https://www.zdaye.com/dayProxy.html", "type": "table", "class": "cont"},
        {"name": "小幻代理", "url": "https://ip.ihuan.me/", "type": "table", "class": "table table-hover table-bordered"},
        {"name": "泥马代理", "url": "https://www.nimadaili.com/", "type": "table", "class": "fl-table"},
        {"name": "高可用代理", "url": "https://ip.jiangxianli.com/", "type": "table", "class": "layui-table"},
        {"name": "小舒代理", "url": "http://www.xsdaili.cn/", "type": "div", "class": "cont"},
        {"name": "太阳代理", "url": "http://www.taiyanghttp.com/", "type": "table", "class": "table table-bordered"},
    ]

    # 使用线程池并发抓取
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        future_to_source = {
            executor.submit(
                scrape_source, 
                source, 
                ua.random
            ): source for source in sources
        }
        
        for future in concurrent.futures.as_completed(future_to_source):
            source = future_to_source[future]
            try:
                results = future.result()
                if results:
                    proxies.update(results)
                    print(f"[{source['name']}] 获取 {len(results)} 个代理")
            except Exception as e:
                print(f"[{source['name']}] 抓取出错: {str(e)}")
    
    return list(proxies)

def scrape_source(source, user_agent):
    """抓取单个代理源"""
    try:
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 添加随机延迟防止被封
        time.sleep(random.uniform(0.5, 2.5))
        
        response = requests.get(
            source['url'], 
            headers=headers, 
            timeout=15,
            allow_redirects=True
        )
        
        # 检查响应状态
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        # 根据源类型调用不同的解析器
        if source['type'] == 'json':
            return parse_json(response.json())
        elif source['type'] == 'plain':
            return parse_plain_text(response.text)
        else:
            return parse_html(response.text, source)
            
    except Exception as e:
        raise Exception(f"请求失败: {str(e)}")

def parse_html(html, source):
    """解析HTML页面获取代理"""
    soup = BeautifulSoup(html, 'html.parser')
    proxies = set()
    
    # 根据配置查找目标元素
    if 'id' in source:
        container = soup.find(source['type'], id=source['id'])
    elif 'class' in source:
        container = soup.find(source['type'], class_=source['class'])
    else:
        container = None
    
    if not container:
        # 尝试备用选择器
        container = soup.find('table') or soup.find('div')
        if not container:
            return set()
    
    # 提取代理数据
    if container.name == 'table':
        rows = container.find_all('tr')[1:]  # 跳过表头
        for row in rows:
            cols = [col.text.strip() for col in row.find_all('td')]
            if len(cols) >= 2:
                ip, port = cols[0], cols[1]
                if validate_ip_port(ip, port):
                    proxies.add(f"{ip}:{port}")
    
    elif container.name == 'div' or container.name == 'ul':
        items = container.find_all(['div', 'li'])
        for item in items:
            text = item.get_text()
            # 使用正则匹配IP:PORT模式
            matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b', text)
            for match in matches:
                ip, port = match.split(':')
                if validate_ip_port(ip, port):
                    proxies.add(match)
    
    return proxies

def parse_plain_text(text):
    """解析纯文本格式的代理列表"""
    proxies = set()
    # 匹配所有IP:PORT格式的字符串
    matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b', text)
    for match in matches:
        ip, port = match.split(':')
        if validate_ip_port(ip, port):
            proxies.add(match)
    return proxies

def parse_json(data):
    """解析JSON格式的代理列表"""
    proxies = set()
    
    # 处理不同JSON结构
    if 'data' in data:
        items = data['data']
    elif 'proxies' in data:
        items = data['proxies']
    elif isinstance(data, list):
        items = data
    else:
        return set()
    
    for item in items:
        if 'ip' in item and 'port' in item:
            ip, port = str(item['ip']), str(item['port'])
        elif 'address' in item and 'port' in item:
            ip, port = str(item['address']), str(item['port'])
        elif 'proxy' in item:
            parts = item['proxy'].split(':')
            if len(parts) == 2:
                ip, port = parts
            else:
                continue
        else:
            continue
        
        if validate_ip_port(ip, port):
            proxies.add(f"{ip}:{port}")
    
    return proxies

def validate_ip_port(ip, port):
    """验证IP和端口格式是否有效"""
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
        return False
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        return False
    return True

def validate_proxy(proxy, timeout=8):
    """验证代理是否可用"""
    try:
        test_urls = [
            "http://httpbin.org/ip",
            "http://icanhazip.com",
            "http://ipinfo.io/ip"
        ]
        
        proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        
        # 随机选择一个测试URL
        test_url = random.choice(test_urls)
        
        response = requests.get(
            test_url, 
            proxies=proxies, 
            timeout=timeout,
            headers={'User-Agent': UserAgent().random}
        )
        
        return response.status_code == 200
    except:
        return False

def save_to_file(proxies):
    """保存有效代理到文件"""
    print(f"开始验证 {len(proxies)} 个代理的可用性...")
    
    valid_proxies = []
    total = len(proxies)
    
    # 使用进程池并行验证
    with concurrent.futures.ThreadPoolExecutor(max_workers=300) as executor:
        future_to_proxy = {executor.submit(validate_proxy, proxy): proxy for proxy in proxies}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_proxy)):
            proxy = future_to_proxy[future]
            try:
                if future.result():
                    valid_proxies.append(proxy)
            except:
                pass
            
            # 每50个显示一次进度
            if (i + 1) % 50 == 0:
                print(f"验证进度: {i+1}/{total} | 有效代理: {len(valid_proxies)}")
    
    # 保存到文件
    with open('pa.txt', 'w') as f:
        for proxy in valid_proxies:
            f.write(f"{proxy}\n")
    
    print(f"保存 {len(valid_proxies)} 个有效代理到 pa.txt")
    return len(valid_proxies)

if __name__ == "__main__":
    start_time = time.time()
    
    try:
        print("开始抓取代理...")
        proxies = fetch_proxies()
        print(f"共获取 {len(proxies)} 个原始代理")
        
        if proxies:
            valid_count = save_to_file(proxies)
            print(f"有效代理率: {valid_count/len(proxies)*100:.1f}%")
        else:
            print("未获取到代理，请检查网络或网站结构变化")
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
    finally:
        print(f"总耗时: {time.time()-start_time:.2f}秒")
