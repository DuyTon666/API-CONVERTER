import sys
sys.path.insert(0, "src")

from schema_converter.llm_client import fill_metadata

def test_fill_metadata():
    # Gọi AI với thông tin của close ticket
    result = fill_metadata(
        title="close customer ticket",
        method="PUT",
        path="/v1/users/{user_id}/tickets/{id}/close"
    )

    print(f"\nSummary: {result['summary']}")
    print(f"OperationId: {result['operationId']}")

    #Kiểm tra kết quả
    assert "summary" in result
    assert "operationId" in result
    assert len(result["operationId"]) > 0