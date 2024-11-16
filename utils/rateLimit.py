from collections import defaultdict, deque
from functools import wraps
from datetime import datetime
from fastapi import HTTPException

routerInvoke = defaultdict(lambda: defaultdict(deque))


def rateLimit(limit: int, window: int):
    '''
    {window}秒内请求不超过{limit}次
    '''
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if limit == -1:
                return await func(*args, **kwargs)

            key = func.__name__
            if 'request' in kwargs:
                uuid = kwargs['request'].client      # 用户IP地址, 在注册中使用
            elif 'info' in kwargs:
                uuid = kwargs['info'].userInfo.uuid  # 用户uuid, 在group中使用
            elif 'userInfo' in kwargs:
                uuid = kwargs['userInfo'].uuid       # 用户uuid, 在user中使用
            else:
                uuid = args[1]                       # 用户uuid,  在ws中使用

            currentTime = int(datetime.now().timestamp())
            queue = routerInvoke[key][uuid]
            while queue and currentTime - queue[0] > window:
                queue.popleft()
            if len(queue) >= limit:
                raise HTTPException(status_code=429, detail="请求过多，稍后重试")
            queue.append(currentTime)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
