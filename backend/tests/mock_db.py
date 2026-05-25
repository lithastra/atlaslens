"""Shared in-memory MongoDB mock for tests."""

from typing import Any


class MockCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs
        self._idx = 0

    def batch_size(self, _n: int) -> "MockCursor":
        return self

    def __aiter__(self) -> "MockCursor":
        self._idx = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._idx]
        self._idx += 1
        return doc


class MockCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def replace_one(
        self,
        filter: dict[str, Any],
        doc: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        self.docs[filter["_id"]] = doc

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[doc["_id"]] = doc

    async def find_one(
        self, filter: dict[str, Any]
    ) -> dict[str, Any] | None:
        if "_id" in filter:
            return self.docs.get(filter["_id"])
        for doc in self.docs.values():
            if _matches(doc, filter):
                return doc
        return None

    async def update_one(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        _id = filter.get("_id")
        if _id is None:
            for doc in self.docs.values():
                if _matches(doc, filter):
                    _id = doc["_id"]
                    break
        if _id is None:
            if upsert:
                _id = filter.get("_id", "auto")
                self.docs[_id] = {"_id": _id}
            else:
                return
        if _id not in self.docs:
            self.docs[_id] = {"_id": _id}
        doc = self.docs[_id]
        for key, val in update.get("$set", {}).items():
            doc[key] = val
        for key, val in update.get("$addToSet", {}).items():
            if key not in doc:
                doc[key] = []
            if val not in doc[key]:
                doc[key].append(val)

    async def delete_one(self, filter: dict[str, Any]) -> None:
        _id = filter.get("_id")
        if _id and _id in self.docs:
            del self.docs[_id]

    async def count_documents(
        self, filter: dict[str, Any]
    ) -> int:
        if not filter:
            return len(self.docs)
        return sum(
            1 for d in self.docs.values() if _matches(d, filter)
        )

    def find(
        self,
        filter: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
    ) -> MockCursor:
        if not filter:
            docs = list(self.docs.values())
        else:
            docs = [
                d
                for d in self.docs.values()
                if _matches(d, filter)
            ]
        if projection:
            projected = []
            for d in docs:
                p = {"_id": d["_id"]}
                for key in projection:
                    if key != "_id" and key in d:
                        p[key] = d[key]
                projected.append(p)
            docs = projected
        return MockCursor(docs)


class MockDB:
    def __init__(self) -> None:
        self._collections: dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self._collections:
            self._collections[name] = MockCollection()
        return self._collections[name]


def _matches(doc: dict[str, Any], filter: dict[str, Any]) -> bool:
    for key, expected in filter.items():
        val = _resolve_dotted(doc, key)
        if isinstance(expected, dict):
            if "$ne" in expected:
                if isinstance(val, list):
                    if expected["$ne"] in val:
                        return False
                elif val == expected["$ne"]:
                    return False
            if "$regex" in expected:
                import re

                flags = (
                    re.IGNORECASE
                    if expected.get("$options") == "i"
                    else 0
                )
                if val is None or not re.search(
                    expected["$regex"], str(val), flags
                ):
                    return False
        elif isinstance(val, list):
            if expected not in val:
                return False
        elif val != expected:
            return False
    return True


def _resolve_dotted(doc: dict[str, Any], key: str) -> Any:
    parts = key.split(".")
    current: Any = doc
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            results = []
            for item in current:
                if isinstance(item, dict) and part in item:
                    results.append(item[part])
            return results if results else None
        else:
            return None
    return current
