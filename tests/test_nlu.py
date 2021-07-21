from app import create_app
import unittest

class TestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('Testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def test_train_nlu(self):
        rv = self.client.post('/nlu/build_models', json={}, follow_redirects=True)
        assert rv.status_code == 200

if __name__ == '__main__':
    unittest.main()