from pydantic import BaseModel
from typing import List, Optional

class CollectionInfo(BaseModel):
    name: str

class Collection(BaseModel):
    info: CollectionInfo
    item: List

class GenerateFromSpecResponse(BaseModel):
    runId: str
    testCases: List
    collection: Collection

class UpdateTestCasesResponse(BaseModel):
    status: str
    message: str

class GetCollectionResponse(BaseModel):
    runId: str
    collection: Collection

class GetTestCountResponse(BaseModel):
    runId: str
    count: int

class ExecuteBatchResponse(BaseModel):
    runId: str
    batchIndex: int
    batchSize: int
    results: List
    summary: dict
