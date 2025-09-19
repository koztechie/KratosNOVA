import json
import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
contracts_table = dynamodb.Table(os.environ.get("CONTRACTS_TABLE_NAME"))
submissions_table = dynamodb.Table(os.environ.get("SUBMISSIONS_TABLE_NAME"))

def handler(event, context):
    """
    Fetches all open contracts and their corresponding submissions.
    """
    try:
        # 1. Get all OPEN contracts
        contracts_response = contracts_table.scan(
            FilterExpression=Attr('status').eq('OPEN')
        )
        contracts = contracts_response.get("Items", [])
        
        # 2. For each contract, get its submissions using the GSI
        for contract in contracts:
            subs_response = submissions_table.query(
                IndexName="contract-id-index",
                KeyConditionExpression=Key('contract_id').eq(contract['contract_id'])
            )
            contract['submissions'] = subs_response.get("Items", [])

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"marketplace_data": contracts})
        }
    except ClientError as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}