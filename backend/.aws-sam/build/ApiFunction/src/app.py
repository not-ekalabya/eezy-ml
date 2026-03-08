import json

def handler(event, context):
    
    path = event.get("path")
    
    if path == "/health":
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok"})
        }

    if path == "/predict":
        data = json.loads(event["body"])

        result = {"prediction": 42}

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    return {
        "statusCode": 404,
        "body": "Not found"
    }