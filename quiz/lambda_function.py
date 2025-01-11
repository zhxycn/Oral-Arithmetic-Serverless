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


def save_quiz(
    uid: int,
    mode: str,
    quiz_time: int,
    questions: dict,
    question_count: int,
    correct_count: int,
    used_time: int,
    is_competition: bool,
    allow_competition: bool,
) -> None:
    """
    保存结果

    :param uid: 用户 ID
    :param mode: 模式
    :param quiz_time: 时间
    :param questions: 题目及作答情况
    :param question_count: 总题数
    :param correct_count: 正确题数
    :param used_time: 用时
    :param is_competition: 是否为PK模式
    :param allow_competition: 是否允许发起PK
    """
    # 检查参数是否为空
    if (
        uid is None
        or mode is None
        or quiz_time is None
        or questions is None
        or question_count is None
        or correct_count is None
        or used_time is None
    ):
        raise ValueError("Missing parameter")

    # 定义数据表
    user_table = dynamodb.Table(USER_TABLE)
    quiz_table = dynamodb.Table(QUIZ_TABLE)

    # 生成 QID
    while True:
        qid = str(uuid.uuid4())
        data = quiz_table.get_item(Key={"qid": qid})
        if "Item" in data:
            continue
        else:
            break

    # 存入 DynamoDB
    quiz_item = {
        "qid": qid,
        "mode": mode,
        "quiz_time": quiz_time,
        "questions": questions,
        "question_count": question_count,
        "correct_count": correct_count,
        "used_time": used_time,
        "is_competition": is_competition,
        "allow_competition": allow_competition,
        "p1_uid": uid,
        "p2_uid": [],
    }
    quiz_table.put_item(Item=quiz_item)

    # 更新用户数据，将 qid 添加到 qid 列表中，并使总场数 +1
    user_table.update_item(
        Key={"uid": uid},
        UpdateExpression="SET qid = list_append(if_not_exists(qid, :empty_list), :qid), #total = #total + :increment",
        ExpressionAttributeNames={"#total": "total"},
        ExpressionAttributeValues={":qid": [qid], ":empty_list": [], ":increment": 1},
    )


def save_mistake(
    uid: int, question: str, user_answer: str, correct_answer: str
) -> None:
    """
    保存错题

    :param uid: 用户 ID
    :param question: 题目
    :param user_answer: 用户答案
    :param correct_answer: 正确答案
    """
    # 检查参数是否为空
    if not uid or not question or not user_answer or not correct_answer:
        raise ValueError("Missing parameter")

    # 定义数据表
    user_table = dynamodb.Table(USER_TABLE)

    # 错题记录
    mistake = {
        "question": question,
        "userAnswer": user_answer,
        "correctAnswer": correct_answer,
    }

    # 更新用户数据，将错题添加到 mistake 列表中
    user_table.update_item(
        Key={"uid": uid},
        UpdateExpression="SET mistake = list_append(if_not_exists(mistake, :empty_list), :mistake)",
        ExpressionAttributeValues={":mistake": [mistake], ":empty_list": []},
    )


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

    # 保存结果
    if event_type == "save_quiz":
        try:
            uid = get_uid_from_cookie(event["cookies"])
            mode = body.get("mode", None)
            quiz_time = body.get("startTime", None)
            questions = body.get("questions", None)
            question_count = body.get("questionCount", None)
            correct_count = body.get("correctCount", None)
            used_time = body.get("elapsedTime", None)
            is_competition = body.get("isCompetition", False)
            allow_competition = body.get("allowCompetition", False)

            save_quiz(
                uid,
                mode,
                quiz_time,
                questions,
                question_count,
                correct_count,
                used_time,
                is_competition,
                allow_competition,
            )
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

    # 保存错题
    if event_type == "save_mistake":
        try:
            uid = get_uid_from_cookie(event["cookies"])
            question = body.get("question", None)
            user_answer = body.get("userAnswer", None)
            correct_answer = body.get("correctAnswer", None)

            save_mistake(uid, question, user_answer, correct_answer)
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
