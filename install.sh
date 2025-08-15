read -p "输入 'y' 继续安装或输入其他退出: " choice

if [ "$choice" != "y" ]; then
  echo "退出安装"
  script_path=$(readlink -f "$0")
  rm "$script_path"
  history -c && rm ~/.bash_history
  exit 0
fi

chmod +x *

red=$(tput setaf 1);
white=$(tput setaf 7);
gren=$(tput setaf 2);

echo -e  "\n${gren}欢迎使用CC环境安装脚本 适用于Ubuntu\n${white}";

apt update

apt install nodejs npm  -y

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.38.0/install.sh | bash

source ~/.bashrc

nvm --version;

nvm install node 


npm i net http2 tls  cluster url crypto user-agents fs header-generator fake-useragent
npm i randomstring string-random
npm i user-agents
npm i url fs http2 http  tls  net  request cluster fake-useragent randomstring;
apt install zmap -y
apt install golang-go -y
apt install gccgo-go  -y
npm i events randomstring url path cluster


apt -y install curl dirmngr apt-transport-https lsb-release ca-certificates;curl -sL https://deb.nodesource.com/setup_12.x |  -E bash -; apt -y install nodejs; apt -y install gcc g++ make; apt -y install htop vnstat; apt-get install -y unzip; apt -y install screen; apt -y install unrar;npm i await-timeout;npm i console-log-level;npm i events; npm i request;npm i chalk; npm i hpagent; npm i got; npm i crypto; npm i cheerio; npm i child_process events fs colors request playwright ; npm i axios; npm i https; npm i request-curl;npm i user-agents; npm i uuid; npm i tmp-promise; npm i puppeteer-extra;npm i puppeteer-extra-plugin-stealth;npm i sleep-promise; npm i puppeteer-extra-plugin-adblocker
echo -e  "\n${gren}进入下一安装阶段\n${white}"
sleep 6
npm install puppeteer cli-color request fake-useragent axios header-generator user-agents
apt install -y gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils wget
apt-get install -y libgbm-dev
echo -e "\n${red}更新Node.JS \n${white}"
npm install n -g
n stable
npm cache clean -f
sleep 6
script_path=$(readlink -f "$0")
rm "$script_path"
history -c && rm ~/.bash_history
echo -e  "\n${gren}安装完毕 重新启动中\n${white}";reboot