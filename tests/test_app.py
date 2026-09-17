import unittest
import os
import json
import sys

# Ensure my_webapp directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# DATABASE_URL must point at a Supabase/Postgres instance before app import
from app import app, init_db, get_db, execute

class TaskFlowTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

        with app.app_context():
            db = get_db()
            execute(db, 'TRUNCATE TABLE todos RESTART IDENTITY')
            db.commit()
            init_db()

    def tearDown(self):
        with app.app_context():
            db = get_db()
            execute(db, 'TRUNCATE TABLE todos RESTART IDENTITY')
            db.commit()

    def test_health_check(self):
        """서버 헬스 체크 엔드포인트 테스트"""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ok')

    def test_index_page(self):
        """메인 웹페이지 렌더링 테스트"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'TaskFlow', response.data)

    def test_create_and_get_todo(self):
        """할일 생성 및 조회 테스트"""
        new_todo = {
            'title': '새로운 테스트 할일',
            'description': '테스트 설명 내용',
            'category': '업무',
            'priority': 'high',
            'due_date': '2026-09-30'
        }
        res = self.client.post('/api/todos', json=new_todo)
        self.assertEqual(res.status_code, 201)
        created = res.get_json()
        self.assertEqual(created['title'], '새로운 테스트 할일')
        self.assertEqual(created['completed'], 0)

        # 목록에서 조회되는지 확인
        list_res = self.client.get('/api/todos')
        self.assertEqual(list_res.status_code, 200)
        todos = list_res.get_json()
        self.assertTrue(any(t['id'] == created['id'] for t in todos))

    def test_toggle_todo(self):
        """할일 완료 상태 토글 테스트"""
        # 생성
        res = self.client.post('/api/todos', json={'title': '토글 테스트'})
        todo_id = res.get_json()['id']

        # 토글 -> 완료
        toggle_res = self.client.patch(f'/api/todos/{todo_id}/toggle')
        self.assertEqual(toggle_res.status_code, 200)
        self.assertEqual(toggle_res.get_json()['completed'], 1)

        # 다시 토글 -> 진행중
        toggle_res2 = self.client.patch(f'/api/todos/{todo_id}/toggle')
        self.assertEqual(toggle_res2.status_code, 200)
        self.assertEqual(toggle_res2.get_json()['completed'], 0)

    def test_update_todo(self):
        """할일 정보 수정 테스트"""
        res = self.client.post('/api/todos', json={'title': '수정 전 제목', 'priority': 'low'})
        todo_id = res.get_json()['id']

        update_payload = {
            'title': '수정 완료된 제목',
            'priority': 'high',
            'category': '공부',
            'description': '수정된 메모'
        }
        update_res = self.client.put(f'/api/todos/{todo_id}', json=update_payload)
        self.assertEqual(update_res.status_code, 200)
        updated = update_res.get_json()
        self.assertEqual(updated['title'], '수정 완료된 제목')
        self.assertEqual(updated['priority'], 'high')
        self.assertEqual(updated['category'], '공부')

    def test_delete_todo(self):
        """할일 삭제 테스트"""
        res = self.client.post('/api/todos', json={'title': '삭제될 할일'})
        todo_id = res.get_json()['id']

        del_res = self.client.delete(f'/api/todos/{todo_id}')
        self.assertEqual(del_res.status_code, 200)

        # 조회 시 404 확인
        get_res = self.client.get(f'/api/todos/{todo_id}')
        self.assertEqual(get_res.status_code, 404)

    def test_stats_endpoint(self):
        """통계 API 정상 집계 테스트"""
        res = self.client.get('/api/stats')
        self.assertEqual(res.status_code, 200)
        stats = res.get_json()
        self.assertIn('total', stats)
        self.assertIn('completed', stats)
        self.assertIn('pending', stats)
        self.assertIn('completion_rate', stats)

if __name__ == '__main__':
    unittest.main()
