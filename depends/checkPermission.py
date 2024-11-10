from functools import reduce

from fastapi import HTTPException, Depends, Path

from depends.getInfo import getSelfInfo, getGroupInfo, getUserInfo, getSelfRequest, getUserRequest, getRequest
from schema.group import GroupSchema, Info
from schema.user import UserSchema
from schema.storage import RequestMsgSchema, FileStorageSchema
from utils.crud import GROUP_REQUEST, FRIEND_REQUEST, FS
from public.stateCode import RequestState
from public.const import Limits
from utils.helper import timestamp


# member为群内所有成员，包括群主及管理员
class PermissionValidate:
    @staticmethod
    def owner(groupInfo: GroupSchema,
              userInfo: UserSchema,
              **kwargs) -> bool:
        if userInfo.id != groupInfo.owner:
            raise HTTPException(status_code=403, detail="不是该群群主")
        return True

    @staticmethod
    def notOwner(groupInfo: GroupSchema,
                 userInfo: UserSchema,
                 **kwargs) -> bool:
        if userInfo.id == groupInfo.owner:
            raise HTTPException(status_code=403, detail="群主不允许操作")
        return True

    @staticmethod
    def admin(groupInfo: GroupSchema,
              userInfo: UserSchema,
              **kwargs) -> bool:
        if userInfo.id != groupInfo.owner and userInfo.id not in groupInfo.admin:
            raise HTTPException(status_code=403, detail="不是该群群主/管理员")
        return True

    @staticmethod
    def notAdmin(groupInfo: GroupSchema,
                 userInfo: UserSchema,
                 **kwargs) -> bool:
        if userInfo.id == groupInfo.owner or userInfo.id in groupInfo.admin:
            raise HTTPException(status_code=403, detail="群主/管理员不允许操作")
        return True

    @staticmethod
    def member(groupInfo: GroupSchema,
               userInfo: UserSchema,
               **kwargs) -> bool:
        if userInfo.id not in groupInfo.user:
            raise HTTPException(status_code=403, detail="不是该群成员")
        return True

    @staticmethod
    def notMember(groupInfo: GroupSchema,
                  userInfo: UserSchema,
                  **kwargs) -> bool:
        if userInfo.id in groupInfo.user:
            raise HTTPException(status_code=403, detail="该群成员不允许操作")
        return True

    @staticmethod
    def notLimit(groupInfo: GroupSchema,
                 userInfo: UserSchema,
                 **kwargs) -> bool:
        return True


class TargetValidate:
    @staticmethod
    def owner(groupInfo: GroupSchema,
              targetInfo: UserSchema,
              **kwargs) -> bool:
        if targetInfo.id != groupInfo.owner:
            raise HTTPException(status_code=403, detail="操作对象必须是群主")
        return True

    @staticmethod
    def notOwner(groupInfo: GroupSchema,
                 targetInfo: UserSchema,
                 **kwargs) -> bool:
        if targetInfo.id == groupInfo.owner:
            raise HTTPException(status_code=403, detail="操作对象不能是群主")
        return True

    @staticmethod
    def admin(groupInfo: GroupSchema,
              targetInfo: UserSchema,
              **kwargs) -> bool:
        if targetInfo.id not in groupInfo.admin:
            raise HTTPException(status_code=403, detail="操作对象必须是管理员")
        return True

    @staticmethod
    def notAdmin(groupInfo: GroupSchema,
                 targetInfo: UserSchema,
                 **kwargs) -> bool:
        if targetInfo.id in groupInfo.admin:
            raise HTTPException(status_code=403, detail="操作对象必须不是管理员")
        return True

    @staticmethod
    def member(groupInfo: GroupSchema,
               targetInfo: UserSchema,
               **kwargs) -> bool:
        if targetInfo.id not in groupInfo.user:
            raise HTTPException(status_code=403, detail="操作对象必须是该群成员")
        return True

    @staticmethod
    def notMember(groupInfo: GroupSchema,
                  targetInfo: UserSchema,
                  **kwargs) -> bool:
        if targetInfo.id in groupInfo.user:
            raise HTTPException(status_code=403, detail="操作对象必须不是该群成员")
        return True

    @staticmethod
    def notSelf(userInfo: UserSchema,
                targetInfo: UserSchema,
                **kwargs) -> bool:
        if userInfo.id == targetInfo.id:
            raise HTTPException(status_code=403, detail="不允许对自己操作")
        return True

    @staticmethod
    def notLimit(groupInfo: GroupSchema,
                 targetInfo: UserSchema,
                 **kwargs) -> bool:
        return True


# 申请类消息验证
class RequestValidate:
    @staticmethod
    def exist(requestInfo: RequestMsgSchema,
              **kwargs) -> bool:
        if not requestInfo:
            raise HTTPException(status_code=404, detail="该申请不存在或已过期")
        if requestInfo.state != RequestState.PENDING.value:
            raise HTTPException(status_code=403, detail="该申请已被处理")
        return True

    @staticmethod
    def notExist(requestInfo: RequestMsgSchema,
                 **kwargs) -> bool:
        if requestInfo \
                and requestInfo.state == RequestState.PENDING.value \
                and int(timestamp()) - int(requestInfo.time) < int(Limits.REQUEST_EXPIRE_MINUTES.value * 60 * 1000):
            raise HTTPException(status_code=403, detail="申请中，等待审核")
        return True


class outputFileValidate:
    @staticmethod
    def exists(group: str = Path(...),
               hashcode: str = Path(...)) -> FileStorageSchema:
        file = FS.query(hashcode)
        if not file:
            raise HTTPException(status_code=404, detail=f"文件不存在或已过期")
        if group not in file.group or file.group[group] <= 0:
            raise HTTPException(status_code=403, detail=f"文件不属于该群")
        return file


class CheckerBase:
    def __init__(self, *args: PermissionValidate | TargetValidate | RequestValidate):
        self.checkers = args

    def __call__(self,
                 userInfo: UserSchema | None = None,
                 groupInfo: GroupSchema | None = None,
                 targetInfo: UserSchema | None = None,
                 requestInfo: RequestMsgSchema | None = None) -> Info:

        for checker in self.checkers:
            checker(groupInfo=groupInfo, userInfo=userInfo, targetInfo=targetInfo, requestInfo=requestInfo)

        info = {
            "userInfo": userInfo,
            "groupInfo": groupInfo,
            "targetInfo": targetInfo,
            "requestInfo": requestInfo,
        }
        return Info.model_validate(info)


class CheckPermission(CheckerBase):
    """用户必须有权限才能操作"""
    def __call__(self,
                 userInfo: UserSchema = Depends(getSelfInfo),
                 groupInfo: GroupSchema = Depends(getGroupInfo)) -> Info:
        return super().__call__(userInfo=userInfo, groupInfo=groupInfo)


class CheckTarget(CheckerBase):
    """被操作用户必须具有对应身份"""
    def __call__(self,
                 userInfo: UserSchema = Depends(getSelfInfo),
                 groupInfo: GroupSchema = Depends(getGroupInfo),
                 targetInfo: UserSchema = Depends(getUserInfo)) -> Info:
        return super().__call__(userInfo=userInfo, targetInfo=targetInfo, groupInfo=groupInfo)


class CheckRequest(CheckerBase):
    """
    检查申请
    """
    def __init__(self,
                 userInfo: UserSchema,
                 isGroupRequest: bool,
                 group: str = None,
                 uuid: str = None,
                 time: str = None,
                 checkers: list = []):
        self.userInfo = userInfo
        self.isGroupRequest = isGroupRequest
        self.group = group
        self.uuid = uuid
        self.time = time
        self.checkers = checkers

    def __call__(self):
        requestInfo = getRequest(self.userInfo, self.isGroupRequest, self.group or self.uuid, self.time)
        targetInfo = None
        if self.time and requestInfo:
            targetInfo = getUserInfo(requestInfo.senderID)
        elif self.uuid:
            targetInfo = getUserInfo(self.uuid)
        return super().__call__(userInfo=self.userInfo, targetInfo=targetInfo, requestInfo=requestInfo)
