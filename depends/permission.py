from fastapi import HTTPException, Depends

from depends.getInfo import getSelfInfo, getGroupInfo, getUserInfo
from schema.group import GroupSchema, Info
from schema.user import UserSchema


# 用户必须有权限才能操作
# member为群内所有成员，包括群主及管理员
class Permission:
    @staticmethod
    def owner(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        if userInfo.id != groupInfo.owner:
            raise HTTPException(status_code=403, detail="不是该群群主")
        return True

    @staticmethod
    def notOwner(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        if userInfo.id == groupInfo.owner:
            raise HTTPException(status_code=403, detail="群主不允许操作")
        return True

    @staticmethod
    def admin(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        if userInfo.id != groupInfo.owner and userInfo.id not in groupInfo.admin:
            raise HTTPException(status_code=403, detail="不是该群群主/管理员")
        return True

    @staticmethod
    def notAdmin(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        if userInfo.id == groupInfo.owner or userInfo.id in groupInfo.admin:
            raise HTTPException(status_code=403, detail="群主/管理员不允许操作")
        return True

    @staticmethod
    def member(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        if userInfo.id not in groupInfo.user:
            raise HTTPException(status_code=403, detail="不是该群成员")
        return True

    @staticmethod
    def notMember(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        if userInfo.id in groupInfo.user:
            raise HTTPException(status_code=403, detail="该群成员不允许操作")
        return True

    @staticmethod
    def notLimit(groupInfo: GroupSchema, userInfo: UserSchema, **kwargs) -> bool:
        return True


# 被操作用户必须具有对应身份
class TargetValidate:
    @staticmethod
    def owner(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if targetInfo.id != groupInfo.owner:
            raise HTTPException(status_code=403, detail="操作对象必须是群主")
        return True

    @staticmethod
    def notOwner(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if targetInfo.id == groupInfo.owner:
            raise HTTPException(status_code=403, detail="操作对象不能是群主")
        return True

    @staticmethod
    def admin(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if targetInfo.id not in groupInfo.admin:
            raise HTTPException(status_code=403, detail="操作对象必须是管理员")
        return True

    @staticmethod
    def notAdmin(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if targetInfo.id in groupInfo.admin:
            raise HTTPException(status_code=403, detail="操作对象必须不是管理员")
        return True

    @staticmethod
    def member(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if targetInfo.id not in groupInfo.user:
            raise HTTPException(status_code=403, detail="操作对象必须是该群成员")
        return True

    @staticmethod
    def notMember(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if targetInfo.id in groupInfo.user:
            raise HTTPException(status_code=403, detail="操作对象必须不是该群成员")
        return True

    @staticmethod
    def notSelf(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        if userInfo.id == targetInfo.id:
            raise HTTPException(status_code=403, detail="不允许对自己操作")
        return True

    @staticmethod
    def notLimit(groupInfo: GroupSchema, userInfo: UserSchema, targetInfo: UserSchema) -> bool:
        return True


class CheckPermission:
    def __init__(self, *args: Permission | TargetValidate):
        self.checkers = args

    def __call__(self,
                 groupInfo: GroupSchema | None = Depends(getGroupInfo),
                 userInfo: UserSchema = Depends(getSelfInfo),
                 targetInfo: UserSchema | None = Depends(getUserInfo)) -> Info:

        for checker in self.checkers:
            checker(groupInfo=groupInfo, userInfo=userInfo, targetInfo=targetInfo)

        info = {
            "groupInfo": groupInfo,
            "userInfo": userInfo,
            "targetInfo": targetInfo,
        }

        return Info.model_validate(info)
