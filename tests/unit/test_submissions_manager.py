import pytest
import boto3
import json
import os
from moto import mock_aws

# Перед тим, як імпортувати наш хендлер, ми маємо "підкласти" змінні середовища,
# оскільки він намагається прочитати їх при завантаженні.
os.environ['CONTRACTS_TABLE_NAME'] = 'TestContractsTable'
os.environ['SUBMISSIONS_TABLE_NAME'] = 'TestSubmissionsTable'

# Тепер імпортуємо наш код
from src.submissions_manager import app as submissions_manager_app


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_mock(aws_credentials):
    """Creates a mock DynamoDB environment."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        
        # Create the Contracts table
        contracts_table = dynamodb.create_table(
            TableName="TestContractsTable",
            KeySchema=[{"AttributeName": "contract_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "contract_id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
        )
        # Create the Submissions table
        dynamodb.create_table(
            TableName="TestSubmissionsTable",
            KeySchema=[{"AttributeName": "submission_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "submission_id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
        )

        # Pre-populate with test data
        contracts_table.put_item(Item={"contract_id": "open-contract-123", "status": "OPEN"})
        contracts_table.put_item(Item={"contract_id": "closed-contract-456", "status": "CLOSED"})
        
        yield dynamodb


def test_submit_to_open_contract_success(dynamodb_mock):
    """
    Tests the happy path: successfully submitting to an OPEN contract.
    """
    event = {
        "pathParameters": {"contract_id": "open-contract-123"},
        "body": json.dumps({
            "agent_id": "test-artist-001",
            "submission_data": "images/test.png"
        })
    }
    
    response = submissions_manager_app.handler(event, {})
    
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert "submission_id" in body
    assert body["message"] == "Submission received successfully."

    # Verify that the item was actually written to the mock DB
    submissions_table = dynamodb_mock.Table("TestSubmissionsTable")
    items = submissions_table.scan()["Items"]
    assert len(items) == 1
    assert items[0]["contract_id"] == "open-contract-123"


def test_submit_to_closed_contract_fails(dynamodb_mock):
    """
    Tests that submitting to a CLOSED contract returns a 403 Forbidden error.
    """
    event = {
        "pathParameters": {"contract_id": "closed-contract-456"},
        "body": json.dumps({
            "agent_id": "test-artist-001",
            "submission_data": "images/test.png"
        })
    }
    
    response = submissions_manager_app.handler(event, {})
    
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "is closed" in body["error"]


def test_submit_to_non_existent_contract_fails(dynamodb_mock):
    """
    Tests that submitting to a non-existent contract returns a 404 Not Found error.
    """
    event = {
        "pathParameters": {"contract_id": "non-existent-contract"},
        "body": json.dumps({
            "agent_id": "test-artist-001",
            "submission_data": "images/test.png"
        })
    }
    
    response = submissions_manager_app.handler(event, {})
    
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in body["error"]

def test_submit_with_missing_body_fails(dynamodb_mock):
    """
    Tests that a request with a missing agent_id in the body returns a 400 Bad Request error.
    """
    event = {
        "pathParameters": {"contract_id": "open-contract-123"},
        "body": json.dumps({"submission_data": "images/test.png"}) # Missing agent_id
    }

    response = submissions_manager_app.handler(event, {})

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "agent_id" in body["error"]