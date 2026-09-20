KARRIES 禾一斯服务器部署说明

一、上传前检查

解压后必须能看到以下文件：

  backend/app/server_main.py
  external/social-auto-upload-xiaohongshu/uploader/xiaohongshu_uploader/main.py
  web/customer/index.html
  web/manager/manager.html
  web/developer/developer.html
  deploy/server/install.sh

external 目录是小红书扫码登录和发布功能的运行时依赖，不能删除。

二、上传与安装

使用腾讯云文件管理器将解压后的整个 karries-server-* 文件夹上传到：

  /home/ubuntu/

把下面命令中的 <上传后的文件夹名> 替换为实际名称：

  sudo mkdir -p /opt/karries
  sudo cp -a /home/ubuntu/<上传后的文件夹名>/. /opt/karries/
  cd /opt/karries
  sudo bash deploy/server/install.sh YOUR_SERVER_IP_OR_DOMAIN

首次安装会随机生成数据库密码、管理端密码、开发者端密码以及服务密钥。
重复执行安装脚本会沿用服务器上已有的安全密码，不会清空业务数据库。

三、查看访问地址和初始账号

安装完成后脚本会输出用户端、管理端、开发者端和健康检查地址。
初始账号与随机密码仅写入 root 可读文件：

  sudo cat /root/karries-initial-credentials

首次登录后请立即修改后台密码，并删除该凭据文件：

  sudo rm /root/karries-initial-credentials

员工账号不预置，由管理员在管理端创建。

四、上线验收

  sudo systemctl status karries-api karries-publish-worker nginx mysql
  curl -fsS http://127.0.0.1:8765/api/health
  curl -fsS http://127.0.0.1:8765/api/ready
  sudo bash deploy/server/smoke-test.sh http://YOUR_SERVER_IP

登录用户端后还必须使用专门的验收账号完成：

  1. 生成并显示小红书登录二维码；
  2. 手机扫码后账号状态变为正常；
  3. 图文发布、视频发布、失败重试和人工接管。

五、域名和 HTTPS

域名解析生效后执行：

  sudo bash deploy/server/enable-https.sh your-domain.com ops@example.com
  sudo bash deploy/server/smoke-test.sh https://your-domain.com

六、升级前备份与回滚

已有部署升级前先执行：

  sudo systemctl start karries-backup.service
  sudo journalctl -u karries-backup.service -n 100 --no-pager

保留上一份完整程序目录和最新备份。若新版本健康检查失败，立即停止开放流量，
恢复上一份程序并按 deploy/server/OPERATIONS.md 的恢复步骤处理数据库和素材。
