![Mk.IX-Server](https://socialify.git.ci/123summertime/Mk.IX-Server/image?name=1&owner=1&theme=Dark)

# 介绍

`Mk.IX-Server` 是基于 `FastAPI`和`MongoDB` 构建的即时通讯 (IM) 后端。

## 安装

### 生产环境
将使用`docker-compose`进行部署，确保已安装`docker`及`docker-compose`的软件包

修改`config.yaml`
* 更改`Auth.SECRET_KEY`为其它的值，不要使用默认值。
* 更改`Auth.SALT`为其它的值，不要使用默认值。
* 更改`Database.HOST`为`mongodb`
* 其它选项按需修改

构建镜像
```bash
docker-compose build
```

启动服务器
```bash
docker-compse up -d
```

### 开发环境

* python 3.11
* MongoDB
* FFmpeg (用于语音类型消息)

```bash
git clone https://github.com/123summertime/Mk.IX-Server.git

cd Mk.IX-Server

pip install -r requirements.txt

uvicorn app:app --log-config logging.yaml
```

## API文档
启动后访问[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 许可

本项目基于 [AGPL License](LICENSE) 进行许可。