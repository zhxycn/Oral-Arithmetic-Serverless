import base64
import json
import os
import time
import uuid

import boto3

# 数据表
AUTH_TABLE = "Oral-Arithmetic-Auth"
SESSION_TABLE = "Oral-Arithmetic-Session"
USER_TABLE = "Oral-Arithmetic-User"
QUIZ_TABLE = "Oral-Arithmetic-Quiz"

# 环境变量
FRONT_END_URL = os.environ["FRONT_END_URL"]

# 初始化 DynamoDB 资源
dynamodb = boto3.resource("dynamodb")


def get_uid_from_cookie(cookie: dict) -> int:
    """
    通过 Cookie 获取 UID

    :param cookie: Cookie
    :return: UID
    """
    # 检查参数是否为空
    if not cookie:
        raise ValueError("Missing parameter")

    # 解析 Cookie
    cookie_dict = {i.split("=")[0].strip(): i.split("=")[1].strip() for i in cookie}
    session = cookie_dict.get("session")

    # 定义数据表
    session_table = dynamodb.Table(SESSION_TABLE)

    # 获取 UID
    data = session_table.get_item(Key={"session": session})
    if "Item" in data:
        expiration = data["Item"].get("expiration")
        if expiration < int(time.time()):
            raise ValueError("Session expired")
        return data["Item"].get("uid")
    else:
        raise ValueError("Missing parameter")


def get(uid: int) -> dict:
    """
    获取用户数据

    :param uid: UID
    """
    # 检查参数是否为空
    if uid is None:
        raise ValueError("Missing parameter")

    # 定义数据表
    user_table = dynamodb.Table(USER_TABLE)

    # 读取 DynamoDB
    data = user_table.get_item(Key={"uid": uid})

    if "Item" in data:
        userdata = data["Item"]
        userdata = json.loads(json.dumps(userdata, default=str))
        return userdata
    else:
        raise ValueError("Missing parameter")


def lambda_handler(event, context):
    # 获取 HTTP 请求方法
    http_method = event["requestContext"]["http"]["method"]

    # 处理 OPTIONS 请求
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": FRONT_END_URL,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "content-type",
                "Access-Control-Allow-Credentials": True,
            },
            "body": "",
        }

    # 获取事件类型
    try:
        event_type = event["queryStringParameters"]["type"]
    except KeyError:
        return {
            "statusCode": 400,
            "headers": {
                "Access-Control-Allow-Origin": FRONT_END_URL,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "content-type",
                "Access-Control-Allow-Credentials": True,
            },
            "body": json.dumps({"message": "缺少参数"}),
        }

    # 解析请求体
    body = (
        (
            json.loads(base64.b64decode(event["body"]).decode("utf-8"))
            if event.get("isBase64Encoded")
            else json.loads(event["body"])
        )
        if "body" in event
        else None
    )

    # 读取用户数据
    if event_type == "get":
        try:
            uid = get_uid_from_cookie(event["cookies"])
            userdata = get(uid)
            return {
                "statusCode": 201,
                "headers": {
                    "Access-Control-Allow-Origin": FRONT_END_URL,
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "content-type",
                    "Access-Control-Allow-Credentials": True,
                },
                "body": json.dumps(userdata),
            }
        except ValueError as e:
            return {
                "statusCode": 400,
                "headers": {
                    "Access-Control-Allow-Origin": FRONT_END_URL,
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "content-type",
                    "Access-Control-Allow-Credentials": True,
                },
                "body": json.dumps({"message": str(e)}),
            }

    return {
        "statusCode": 400,
        "headers": {
            "Access-Control-Allow-Origin": FRONT_END_URL,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Credentials": True,
        },
        "body": ({"message": "参数错误"}),
    }
