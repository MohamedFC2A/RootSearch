"""
RootSearch - Comprehensive Test Suite for Network Compatibility, FastAPI & SSE
اختبارات التوافقية وإدارة الجلسات وFastAPI Validation وتوافق الـ SSE Stream
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from web.app import app
from core.net import get_global_session, get_search_engine_session, get_analyzer_session, close_global_sessions
from config import config


class TestCompatibilityAndWebAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = TestClient(app)

    async def asyncTearDown(self):
        await close_global_sessions()

    def test_status_endpoint(self):
        """Test API status endpoint /api/status."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data.get("status"), "running")



    def test_search_api_validation_too_short(self):
        """Test search API returns 400 validation error when query is too short (<20 chars)."""
        response = self.client.get("/api/search?q=short")
        self.assertEqual(response.status_code, 400)
        json_data = response.json()
        self.assertIn("error", json_data)
        self.assertEqual(json_data.get("status"), "error")

    async def test_session_lifecycle_cleanup(self):
        """Test session creation and clean shutdown without unclosed session warnings."""
        session1 = await get_global_session("example.com")
        session2 = await get_search_engine_session()
        session3 = await get_analyzer_session()
        
        self.assertFalse(session1.closed)
        self.assertFalse(session2.closed)
        self.assertFalse(session3.closed)

        await close_global_sessions()

        self.assertTrue(session1.closed)
        self.assertTrue(session2.closed)
        self.assertTrue(session3.closed)

    def test_cors_middleware_headers(self):
        """Test CORS headers permit origin requests."""
        response = self.client.options("/api/health", headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("access-control-allow-origin", response.headers)


if __name__ == '__main__':
    unittest.main()
