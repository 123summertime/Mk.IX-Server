from stateCode import PermissionLevel
from schema.user import UserSchema
from schema.group import GroupSchema
from schema.payload import Info
from depend.getInfo import getSelfInfo, getGroupInfo

from fastapi import HTTPException, Depends, Path


class checkPermission:
    '''
    在有权限的情况下，返回群信息及自己的信息
    '''
    def __init__(self, level):
        self.level = level

    def __call__(self,
                 groupInfo: GroupSchema = Depends(getGroupInfo),
                 userInfo: UserSchema = Depends(getSelfInfo)) -> Info:

        if self.level == PermissionLevel.OWNER:
            if userInfo.id != groupInfo.owner:
                raise HTTPException(status_code=403, detail="仅群主可操作")

        if self.level == PermissionLevel.ADMIN:
            if userInfo.id != groupInfo.owner and userInfo.id not in groupInfo.admin:
                raise HTTPException(status_code=403, detail="需要管理员权限")

        if self.level == PermissionLevel.USER:
            if userInfo.id not in groupInfo.user:
                raise HTTPException(status_code=403, detail="不在群内")

        info = {
            "groupInfo": groupInfo,
            "userInfo": userInfo
        }

        return Info.parse_obj(info)


NonePermission = checkPermission(PermissionLevel.NONE)
UserPermission = checkPermission(PermissionLevel.USER)
AdminPermission = checkPermission(PermissionLevel.ADMIN)
OwnerPermission = checkPermission(PermissionLevel.OWNER)
