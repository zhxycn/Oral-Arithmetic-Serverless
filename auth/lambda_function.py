import base64
import hashlib
import json
import os
import random
import time
import uuid

import bcrypt
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


def register(email: str, nickname: str, password: str) -> None:
    """
    注册

    :param email: 邮箱
    :param nickname: 昵称
    :param password: 密码
    :raise ValueError: 参数为空或邮箱已存在
    """
    # 检查参数是否为空
    if not email or not nickname or not password:
        raise ValueError("Missing parameter")

    # 定义数据表
    auth_table = dynamodb.Table(AUTH_TABLE)
    user_table = dynamodb.Table(USER_TABLE)

    # 检查邮箱是否存在
    if auth_table.get_item(Key={"email": email}).get("Item"):
        raise ValueError("邮箱已存在")

    # 对密码进行加密
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    # 生成 UID
    while True:
        uid = int(str(uuid.uuid4().int)[:8])
        data = user_table.get_item(Key={"uid": uid})
        if "Item" in data:
            continue
        else:
            break

    # 存入 DynamoDB
    auth_item = {
        "email": email,
        "password": hashed_password.decode("utf-8"),
        "uid": uid,
    }
    auth_table.put_item(Item=auth_item)
    user_item = {
        "uid": uid,
        "email": email,
        "nickname": nickname,
        "total": 0,
        "competition_total": 0,
        "competition_win": 0,
        "qid": [],
        "mistake": [],
    }
    user_table.put_item(Item=user_item)


def login(email: str, password: str) -> [str, int]:
    """
    登录

    :param email: 邮箱
    :param password: 密码
    :return: 用于 Cookie 的 session 值和有效期
    :raise ValueError: 参数为空或邮箱密码错误
    """
    # 检查参数是否为空
    if not email or not password:
        raise ValueError("缺少参数")

    # 定义数据表
    auth_table = dynamodb.Table(AUTH_TABLE)
    session_table = dynamodb.Table(SESSION_TABLE)
    user_table = dynamodb.Table(USER_TABLE)

    # 通过邮箱获取用户验证数据
    auth_data = auth_table.get_item(Key={"email": email}).get("Item")

    # 验证用户名和密码
    if not auth_data or not bcrypt.checkpw(
        password.encode("utf-8"), auth_data["password"].encode("utf-8")
    ):
        raise ValueError("邮箱或密码错误")

    uid = auth_data.get("uid")

    # 通过 UID 获取用户数据
    user_data = user_table.get_item(Key={"uid": uid}).get("Item")

    nickname = user_data.get("nickname")

    # 通过 UID 与时间戳和随机数生成初始 session
    timestamp = int(time.time())
    random_number = str(random.randint(1000, 9999))
    session_raw = f"{uid}{str(timestamp)}{random_number}".encode("utf-8")

    # 生成 session
    session = hashlib.sha256(session_raw).hexdigest()
    expiration = 604800  # 有效期一周

    # 将 token 存储在 DynamoDB
    session_table.put_item(
        Item={"session": session, "uid": uid, "expiration": timestamp + expiration}
    )

    return session, expiration, nickname


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
    email = body.get("email", None) if body else None
    nickname = body.get("nickname", None) if body else None
    password = body.get("password", None) if body else None

    # 注册
    if event_type == "register":
        try:
            register(email, nickname, password)
            return {
                "statusCode": 201,
                "headers": {
                    "Access-Control-Allow-Origin": FRONT_END_URL,
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "content-type",
                    "Access-Control-Allow-Credentials": True,
                },
                "body": json.dumps({"message": "Success"}),
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

    # 登录
    if event_type == "login":
        try:
            session, expiration, nickname = login(email, password)
            return {
                "statusCode": 201,
                "headers": {
                    "Access-Control-Allow-Origin": FRONT_END_URL,
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "content-type",
                    "Access-Control-Allow-Credentials": True,
                    "Set-Cookie": f"session={session}; Path=/; Max-Age={expiration}; Secure; SameSite=None",
                },
                "body": json.dumps(
                    {
                        "message": "Cookie Set",
                        "session": session,
                        "expiration": expiration,
                        "nickname": nickname,
                    }
                ),
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
